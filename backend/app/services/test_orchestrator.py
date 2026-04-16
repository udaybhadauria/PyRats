"""
Test Orchestrator Service - Handles test execution and scheduling
Replaces TestSuits_mapping.h and test execution logic
"""

import asyncio
import json
from uuid import uuid4
from datetime import datetime
from typing import Dict, List, Optional, Any
from app.models import ConfigManager
from app.settings import settings
from app.utils import logger


class TestOrchestrator:
    """Manages test execution and scheduling"""

    def __init__(self):
        self.tests: Dict[str, Dict[str, Any]] = {}
        self.executions: Dict[str, Dict[str, Any]] = {}
        self.results: Dict[str, Dict[str, Any]] = {}
        self._load_tests()

    def _load_tests(self):
        """Load test definitions from configuration.
        
        Primary source: config/tests.json (now generated from legacy test_config.json
        and pre-populated with all TestApps).  Fallback: raw test_config.json.
        """
        try:
            testapps_dir = str(settings.LEGACY_TESTAPPS_DIR.resolve())
            utility_dir  = str(settings.LEGACY_UTILITY_DIR.resolve())

            def _resolve_cmd(cmd: str) -> str:
                if not cmd or cmd == "NA":
                    return cmd
                return (
                    cmd
                    .replace("{{TESTAPPS}}", testapps_dir)
                    .replace("../TestApps/", testapps_dir + "/")
                    .replace("../Utility/",  utility_dir  + "/")
                )

            config = ConfigManager.load_tests()
            if isinstance(config, dict) and 'test_groups' in config:
                for group_name, tests in config['test_groups'].items():
                    for test in tests:
                        test_id = str(test.get('id', f"{group_name}_{test.get('name', '')}"))
                        test_copy = dict(test)
                        test_copy.setdefault('group', group_name)
                        test_copy['lan_command'] = _resolve_cmd(test_copy.get('lan_command', 'NA'))
                        test_copy['wan_command'] = _resolve_cmd(test_copy.get('wan_command', 'NA'))
                        self.tests[test_id] = test_copy

            # Fallback: ingest raw legacy test_config.json if present
            legacy_config = ConfigManager.load_json_config(settings.LEGACY_TEST_CONFIG)
            if isinstance(legacy_config, dict) and 'testCases' in legacy_config:
                for legacy_test in legacy_config['testCases']:
                    legacy_id = legacy_test.get('testID')
                    test_id = f"legacy_{legacy_id}" if legacy_id is not None else str(uuid4())
                    if test_id in self.tests:
                        continue  # already loaded from tests.json
                    groups = [
                        g.strip()
                        for g in str(legacy_test.get('Group', '')).split(',')
                        if g.strip()
                    ]
                    self.tests[test_id] = {
                        'id': test_id,
                        'legacy_test_id': legacy_id,
                        'name': legacy_test.get('testCase', test_id),
                        'description': f"Legacy {legacy_test.get('TestType', 'NA')} command execution",
                        'group': groups[0] if groups else 'Legacy',
                        'groups': groups,
                        'test_type': legacy_test.get('TestType', 'LAN'),
                        'lan_command': _resolve_cmd(legacy_test.get('LANTestCmd', 'NA')),
                        'wan_command': _resolve_cmd(legacy_test.get('WANTestCmd', 'NA')),
                        'on_device_test': str(legacy_test.get('onDeviceTest', 'false')).lower() == 'true',
                        'legacy': True,
                    }

            logger.info(f"Loaded {len(self.tests)} test definitions")
        except Exception as e:
            logger.error(f"Error loading tests: {e}")

    def get_test(self, test_id: str) -> Optional[Dict[str, Any]]:
        """Get test definition by ID"""
        return self.tests.get(test_id)

    def get_tests_by_group(self, group: str) -> List[Dict[str, Any]]:
        """Get all tests in a group"""
        filtered = []
        for test in self.tests.values():
            groups = test.get('groups') or [test.get('group')]
            if group in groups:
                filtered.append(test)
        return filtered

    def list_test_groups(self) -> List[str]:
        """List all test groups"""
        groups = set()
        for test in self.tests.values():
            test_groups = test.get('groups') or [test.get('group')]
            for group in test_groups:
                if group:
                    groups.add(group)
        return sorted(list(groups))

    def list_all_tests(self) -> List[Dict[str, Any]]:
        """List all available tests"""
        return list(self.tests.values())

    def create_execution(self, device_id: str, test_ids: List[str], 
                        parameters: Optional[Dict] = None) -> str:
        """
        Create test execution batch
        
        Args:
            device_id: Target device ID
            test_ids: List of test IDs to execute
            parameters: Optional test parameters
            
        Returns:
            Execution ID
        """
        execution_id = str(uuid4())
        execution = {
            'id': execution_id,
            'device_id': device_id,
            'test_ids': test_ids,
            'status': 'pending',
            'created_at': datetime.now().isoformat(),
            'started_at': None,
            'completed_at': None,
            'results': [],
            'parameters': parameters or {}
        }
        
        self.executions[execution_id] = execution
        logger.info(f"Created execution {execution_id} for device {device_id} with {len(test_ids)} tests")
        
        return execution_id

    def get_execution(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """Get execution details"""
        return self.executions.get(execution_id)

    def update_execution_status(self, execution_id: str, status: str):
        """Update execution status"""
        if execution_id in self.executions:
            execution = self.executions[execution_id]
            execution['status'] = status
            
            if status == 'running' and not execution['started_at']:
                execution['started_at'] = datetime.now().isoformat()
            elif status in ['completed', 'failed', 'cancelled']:
                execution['completed_at'] = datetime.now().isoformat()

    def record_result(self, execution_id: str, test_id: str, 
                     passed: bool, output: str = "", errors: List[str] = None) -> str:
        """
        Record test result
        
        Args:
            execution_id: Execution ID
            test_id: Test ID
            passed: Test passed flag
            output: Test output
            errors: List of errors if any
            
        Returns:
            Result ID
        """
        result_id = str(uuid4())
        result = {
            'id': result_id,
            'execution_id': execution_id,
            'test_id': test_id,
            'passed': passed,
            'output': output,
            'errors': errors or [],
            'timestamp': datetime.now().isoformat()
        }
        
        self.results[result_id] = result
        
        # Add to execution results
        if execution_id in self.executions:
            self.executions[execution_id]['results'].append(result_id)
        
        logger.info(f"Recorded result for test {test_id}: {'PASSED' if passed else 'FAILED'}")
        
        return result_id

    def get_result(self, result_id: str) -> Optional[Dict[str, Any]]:
        """Get test result"""
        return self.results.get(result_id)

    def get_execution_results(self, execution_id: str) -> List[Dict[str, Any]]:
        """Get all results for an execution"""
        if execution_id not in self.executions:
            return []
        
        result_ids = self.executions[execution_id]['results']
        return [self.results[rid] for rid in result_ids if rid in self.results]

    def get_execution_summary(self, execution_id: str) -> Dict[str, Any]:
        """Get execution summary statistics"""
        execution = self.get_execution(execution_id)
        if not execution:
            return {}
        
        results = self.get_execution_results(execution_id)
        total = len(results)
        passed = sum(1 for r in results if r['passed'])
        failed = total - passed
        
        return {
            'execution_id': execution_id,
            'device_id': execution['device_id'],
            'status': execution['status'],
            'total_tests': total,
            'passed': passed,
            'failed': failed,
            'pass_rate': (passed / total * 100) if total > 0 else 0,
            'duration': self._calculate_duration(execution)
        }

    def _calculate_duration(self, execution: Dict) -> Optional[float]:
        """Calculate execution duration in seconds"""
        if execution['started_at'] and execution['completed_at']:
            start = datetime.fromisoformat(execution['started_at'])
            end = datetime.fromisoformat(execution['completed_at'])
            return (end - start).total_seconds()
        return None


# Global test orchestrator instance
test_orchestrator = TestOrchestrator()
