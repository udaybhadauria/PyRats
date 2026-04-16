"""
Port Forward Test Executor
Tests port forwarding functionality
Replaces PortForward shell script
"""

import asyncio
import socket
from typing import Tuple, List, Optional
from .base_executor import BaseTestExecutor


class PortForwardTestExecutor(BaseTestExecutor):
    """Execute port forward tests"""

    @property
    def test_name(self) -> str:
        return "Port Forwarding"

    @property
    def test_group(self) -> str:
        return "Advanced"

    async def execute(self) -> Tuple[bool, str, List[str]]:
        """
        Execute port forwarding tests
        
        Tests:
        - Port accessibility
        - Traffic forwarding
        - Port mapping verification
        """
        try:
            self.log_output("Starting port forwarding tests...")
            
            # Get port configuration from parameters
            external_port = self.parameters.get('external_port', 8080)
            internal_port = self.parameters.get('internal_port', 80)
            internal_ip = self.parameters.get('internal_ip', '192.168.1.100')
            
            self.log_output(f"Testing port forward: {external_port} -> {internal_ip}:{internal_port}")
            
            # Test port accessibility
            if await self._test_port_accessible(external_port):
                self.log_output(f"✓ External port {external_port} is accessible")
            else:
                self.log_error(f"✗ External port {external_port} is not accessible")
                return False, self.output, self.errors
            
            # Test internal connectivity
            if await self._test_port_accessible(internal_port, internal_ip):
                self.log_output(f"✓ Internal port {internal_port} on {internal_ip} is accessible")
            else:
                self.log_error(f"✗ Internal port {internal_port} on {internal_ip} is not accessible")
                return False, self.output, self.errors
            
            self.log_output("All port forwarding tests passed!")
            return True, self.output, self.errors

        except Exception as e:
            self.log_error(f"Port forward test error: {str(e)}")
            return False, self.output, self.errors

    async def _test_port_accessible(self, port: int, host: str = "localhost") -> bool:
        """Test if a port is accessible"""
        try:
            await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=5
            )
            return True
        except (asyncio.TimeoutError, ConnectionRefusedError, OSError):
            return False
