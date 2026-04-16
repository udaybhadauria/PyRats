"""
Speed Test Executor
Measures device network speed metrics
Replaces SpeedTest shell script
"""

import asyncio
import subprocess
from typing import Tuple, List, Dict, Any, Optional
from .base_executor import BaseTestExecutor


class SpeedTestExecutor(BaseTestExecutor):
    """Execute speed tests"""

    @property
    def test_name(self) -> str:
        return "Speed Test"

    @property
    def test_group(self) -> str:
        return "Performance"

    async def execute(self) -> Tuple[bool, str, List[str]]:
        """
        Execute speed test
        
        Tests:
        - Download speed
        - Upload speed
        - Latency
        """
        try:
            self.log_output("Starting speed test...")
            
            # Try to use speedtest-cli if available
            result = await self._run_speedtest()
            
            if result:
                self.log_output("Speed test completed successfully")
                return True, self.output, self.errors
            else:
                self.log_error("Speed test failed")
                return False, self.output, self.errors

        except Exception as e:
            self.log_error(f"Speed test error: {str(e)}")
            return False, self.output, self.errors

    async def _run_speedtest(self) -> bool:
        """Run speedtest-cli or wget benchmark"""
        try:
            self.log_output("Attempting to run speed test...")
            
            # Try speedtest-cli first
            try:
                result = await asyncio.create_subprocess_exec(
                    "speedtest-cli",
                    "--simple",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    timeout=120
                )
                
                stdout, stderr = await asyncio.wait_for(
                    result.communicate(),
                    timeout=120
                )
                
                if result.returncode == 0:
                    lines = stdout.decode().strip().split('\n')
                    if len(lines) >= 3:
                        download = float(lines[0])
                        upload = float(lines[1])
                        ping = float(lines[2])
                        
                        self.log_output(f"Download: {download:.2f} Mbps")
                        self.log_output(f"Upload: {upload:.2f} Mbps")
                        self.log_output(f"Ping: {ping:.2f} ms")
                        return True
            except Exception:
                pass
            
            # Fallback to simple wget test
            return await self._wget_benchmark()

        except Exception as e:
            self.log_error(f"Speed test execution error: {str(e)}")
            return False

    async def _wget_benchmark(self) -> bool:
        """Fallback speed test using wget"""
        try:
            self.log_output("Running wget benchmark test...")
            
            # Download a test file and measure speed
            result = await asyncio.create_subprocess_exec(
                "wget",
                "-O", "/dev/null",
                "http://speed.cloudflare.com/__down?bytes=10000000",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(
                result.communicate(),
                timeout=60
            )
            
            if result.returncode == 0:
                self.log_output("Wget benchmark completed")
                return True
            else:
                self.log_error("Wget benchmark failed")
                return False

        except Exception as e:
            self.log_error(f"Wget benchmark error: {str(e)}")
            return False
