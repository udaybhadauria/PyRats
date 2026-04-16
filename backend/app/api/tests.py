"""
Test API Endpoints
REST API for test operations
Replaces test execution endpoints from RATS.c
"""

from fastapi import APIRouter, HTTPException, status, BackgroundTasks
from typing import List, Optional
from app.schemas import TestRequest, TestExecution, TestResult
from app.services import test_orchestrator, mqtt_manager, device_manager
from app.test_executors import get_executor
from app.utils import logger
import asyncio

router = APIRouter(prefix="/api/tests", tags=["tests"])


@router.get("/groups")
async def get_test_groups():
    """Get list of all test groups"""
    try:
        groups = test_orchestrator.list_test_groups()
        return {"groups": groups}
    except Exception as e:
        logger.error(f"Error getting test groups: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get test groups"
        )


@router.get("")
async def list_tests(group: Optional[str] = None):
    """
    Get list of all tests
    
    Query Parameters:
        group: Optional group filter
    """
    try:
        if group:
            tests = test_orchestrator.get_tests_by_group(group)
        else:
            tests = test_orchestrator.list_all_tests()
        
        return {
            "total": len(tests),
            "tests": tests
        }
    except Exception as e:
        logger.error(f"Error listing tests: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list tests"
        )


@router.post("/execute", status_code=status.HTTP_202_ACCEPTED)
async def execute_tests(request: TestRequest, background_tasks: BackgroundTasks):
    """
    Execute tests on a device
    
    Request Body:
        device_id: Target device ID
        test_cases: List of test IDs to run
        parameters: Optional test parameters
    
    Returns: Execution ID for tracking
    """
    try:
        # Validate device exists
        device = device_manager.get_device(request.device_id)
        if not device:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Device {request.device_id} not found"
            )
        
        # Create execution record
        execution_id = test_orchestrator.create_execution(
            device_id=request.device_id,
            test_ids=request.test_cases,
            parameters=request.parameters
        )
        
        # Run tests in background
        background_tasks.add_task(
            _run_tests,
            execution_id,
            request.device_id,
            request.test_cases,
            request.parameters
        )
        
        return {
            "execution_id": execution_id,
            "status": "accepted",
            "message": "Tests queued for execution"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error executing tests: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to execute tests"
        )


async def _run_tests(execution_id: str, device_id: str, test_ids: List[str], parameters):
    """Background task to run tests"""
    try:
        test_orchestrator.update_execution_status(execution_id, "running")
        
        for test_id in test_ids:
            try:
                test_definition = test_orchestrator.get_test(test_id)

                # Get test executor
                merged_parameters = dict(parameters or {})
                if test_definition:
                    merged_parameters["_test_definition"] = test_definition

                executor = await get_executor(test_id, device_id, merged_parameters)
                
                # Run test
                passed, output, errors = await executor.run()
                
                # Record result
                test_orchestrator.record_result(
                    execution_id,
                    test_id,
                    passed,
                    output,
                    errors
                )
                
                # Publish result via MQTT
                mqtt_payload = {
                    "execution_id": execution_id,
                    "test_id": test_id,
                    "passed": passed,
                    "device_id": device_id
                }
                await mqtt_manager.publish("test_results", mqtt_payload)
                
            except ValueError as e:
                logger.warning(f"Unknown test: {test_id} - {e}")
                test_orchestrator.record_result(
                    execution_id,
                    test_id,
                    False,
                    "",
                    [f"Unknown test: {test_id}"]
                )
        
        test_orchestrator.update_execution_status(execution_id, "completed")
        logger.info(f"Execution {execution_id} completed")
        
    except Exception as e:
        logger.error(f"Error running tests in execution {execution_id}: {e}")
        test_orchestrator.update_execution_status(execution_id, "error")


@router.get("/execution/{execution_id}")
async def get_execution(execution_id: str):
    """Get execution status and details"""
    execution = test_orchestrator.get_execution(execution_id)
    if not execution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Execution {execution_id} not found"
        )
    
    summary = test_orchestrator.get_execution_summary(execution_id)
    return {
        "execution": execution,
        "summary": summary
    }


@router.get("/execution/{execution_id}/results")
async def get_execution_results(execution_id: str):
    """Get all results for an execution"""
    execution = test_orchestrator.get_execution(execution_id)
    if not execution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Execution {execution_id} not found"
        )
    
    results = test_orchestrator.get_execution_results(execution_id)
    return {
        "execution_id": execution_id,
        "total_results": len(results),
        "results": results
    }
