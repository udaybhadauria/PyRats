"""
Base Test Executor - Abstract base for all test implementations
Replaces individual test shell scripts
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Tuple, List, Optional
import json
from app.utils import logger


class BaseTestExecutor(ABC):
    """Abstract base class for test executors"""

    def __init__(self, device_id: str, parameters: Optional[Dict[str, Any]] = None):
        """
        Initialize test executor
        
        Args:
            device_id: ID of device to test
            parameters: Optional test parameters
        """
        self.device_id = device_id
        self.parameters = parameters or {}
        self.output = ""
        self.errors = []

    @property
    @abstractmethod
    def test_name(self) -> str:
        """Return test name"""
        pass

    @property
    @abstractmethod
    def test_group(self) -> str:
        """Return test group"""
        pass

    @abstractmethod
    async def execute(self) -> Tuple[bool, str, List[str]]:
        """
        Execute the test
        
        Returns:
            Tuple of (passed: bool, output: str, errors: List[str])
        """
        pass

    async def setup(self) -> bool:
        """
        Setup test environment
        
        Returns:
            True if setup successful, False otherwise
        """
        logger.debug(f"Setup for {self.test_name}")
        return True

    async def teardown(self) -> bool:
        """
        Cleanup test environment
        
        Returns:
            True if cleanup successful, False otherwise
        """
        logger.debug(f"Teardown for {self.test_name}")
        return True

    async def run(self) -> Tuple[bool, str, List[str]]:
        """
        Full test lifecycle: setup -> execute -> teardown
        
        Returns:
            Tuple of (passed: bool, output: str, errors: List[str])
        """
        try:
            # Setup
            if not await self.setup():
                return False, self.output, ["Setup failed"]

            # Execute
            passed, output, errors = await self.execute()
            self.output = output
            self.errors = errors

            # Teardown
            await self.teardown()

            return passed, self.output, self.errors

        except Exception as e:
            error_msg = f"Unexpected error in {self.test_name}: {str(e)}"
            logger.error(error_msg)
            return False, self.output, [error_msg]

    async def check_connectivity(self) -> bool:
        """Check if device is reachable"""
        logger.debug(f"Checking connectivity to device {self.device_id}")
        # This would be implemented based on actual device connectivity check
        return True

    def log_output(self, message: str):
        """Add message to test output"""
        self.output += f"{message}\n"
        logger.debug(f"[{self.test_name}] {message}")

    def log_error(self, error: str):
        """Add error to errors list"""
        self.errors.append(error)
        logger.error(f"[{self.test_name}] {error}")

    def get_metadata(self) -> Dict[str, str]:
        """Get test metadata"""
        return {
            'name': self.test_name,
            'group': self.test_group,
            'device_id': self.device_id
        }
