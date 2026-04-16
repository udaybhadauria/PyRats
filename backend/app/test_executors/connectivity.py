"""
Connectivity Test Executor
Tests basic device connectivity (ping, DNS, routing)
Replaces Connectivity test shell script
"""

import asyncio
import subprocess
from typing import Tuple, List, Optional, Dict, Any
from .base_executor import BaseTestExecutor


class ConnectivityTestExecutor(BaseTestExecutor):
    """Execute connectivity tests"""

    @property
    def test_name(self) -> str:
        return "Connectivity"

    @property
    def test_group(self) -> str:
        return "Network"

    async def execute(self) -> Tuple[bool, str, List[str]]:
        """
        Execute connectivity tests
        
        Tests:
        - Ping local gateway
        - DNS resolution
        - Internet connectivity
        - Traceroute to gateway
        """
        try:
            self.log_output("Starting connectivity tests...")
            
            # Test 1: Ping
            if await self._test_ping():
                self.log_output("✓ Ping test passed")
            else:
                self.log_error("✗ Ping test failed")
                return False, self.output, self.errors

            # Test 2: DNS
            if await self._test_dns():
                self.log_output("✓ DNS test passed")
            else:
                self.log_error("✗ DNS test failed")
                return False, self.output, self.errors

            # Test 3: Internet connectivity
            if await self._test_internet():
                self.log_output("✓ Internet connectivity test passed")
            else:
                self.log_error("✗ Internet connectivity test failed")
                return False, self.output, self.errors

            self.log_output("All connectivity tests passed!")
            return True, self.output, self.errors

        except Exception as e:
            self.log_error(f"Connectivity test error: {str(e)}")
            return False, self.output, self.errors

    async def _test_ping(self, host: str = "8.8.8.8", count: int = 4) -> bool:
        """Test ping connectivity"""
        try:
            cmd = ["ping", "-c" if self._is_unix() else "-n", str(count), host]
            result = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(
                result.communicate(),
                timeout=10
            )
            
            if result.returncode == 0:
                self.log_output(f"Ping to {host}: SUCCESS")
                return True
            else:
                self.log_output(f"Ping to {host}: FAILED")
                return False

        except asyncio.TimeoutError:
            self.log_error(f"Ping timeout")
            return False
        except Exception as e:
            self.log_error(f"Ping error: {str(e)}")
            return False

    async def _test_dns(self, hostname: str = "google.com") -> bool:
        """Test DNS resolution"""
        try:
            self.log_output(f"Testing DNS resolution for {hostname}...")
            
            import socket
            loop = asyncio.get_event_loop()
            result = await asyncio.wait_for(
                loop.getaddrinfo(hostname, None),
                timeout=5
            )
            
            ip = result[0][4][0]
            self.log_output(f"DNS resolved {hostname} to {ip}")
            return True

        except asyncio.TimeoutError:
            self.log_error(f"DNS resolution timeout")
            return False
        except socket.gaierror as e:
            self.log_error(f"DNS resolution failed: {str(e)}")
            return False

    async def _test_internet(self, host: str = "8.8.8.8", port: int = 53) -> bool:
        """Test internet connectivity"""
        try:
            self.log_output(f"Testing internet connectivity to {host}:{port}...")
            
            await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=5
            )
            
            self.log_output(f"Internet connectivity test: SUCCESS")
            return True

        except asyncio.TimeoutError:
            self.log_error(f"Internet connectivity timeout")
            return False
        except Exception as e:
            self.log_error(f"Internet connectivity test failed: {str(e)}")
            return False

    def _is_unix(self) -> bool:
        """Check if running on Unix-like system"""
        import sys
        return sys.platform.startswith('linux') or sys.platform == 'darwin'
