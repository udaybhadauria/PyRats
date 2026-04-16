"""
Legacy command executor.
Runs existing TestApps and Utility scripts from the legacy repository
so migration to Python backend can preserve the current test assets.
"""

import asyncio
import re
from pathlib import Path
from typing import Tuple, List, Dict, Any, Optional
from app.settings import settings
from app.services import device_manager
from .base_executor import BaseTestExecutor


class LegacyCommandExecutor(BaseTestExecutor):
    """Execute legacy LAN/WAN command templates from test_config.json."""

    def __init__(
        self,
        device_id: str,
        parameters: Optional[Dict[str, Any]] = None,
        test_definition: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(device_id, parameters)
        self.test_definition = test_definition or {}

    @property
    def test_name(self) -> str:
        return self.test_definition.get("name", "Legacy Command Test")

    @property
    def test_group(self) -> str:
        return self.test_definition.get("group", "Legacy")

    def _select_command(self) -> str:
        mode = str(self.parameters.get("mode", "LAN")).upper()
        lan_cmd = self.test_definition.get("lan_command", "NA")
        wan_cmd = self.test_definition.get("wan_command", "NA")

        if mode == "WAN" and wan_cmd != "NA":
            return wan_cmd
        if lan_cmd != "NA":
            return lan_cmd
        if wan_cmd != "NA":
            return wan_cmd
        return ""

    def _normalize_paths(self, command: str) -> str:
        testapps_dir = Path(settings.LEGACY_TESTAPPS_DIR).resolve().as_posix()
        utility_dir = Path(settings.LEGACY_UTILITY_DIR).resolve().as_posix()
        return (
            command
            .replace("{{TESTAPPS}}", testapps_dir)
            .replace("../TestApps/", f"{testapps_dir}/")
            .replace("../Utility/", f"{utility_dir}/")
        )

    def _materialize_command(self, command_template: str) -> str:
        device = device_manager.get_device(self.device_id) or {}
        test_legacy_id = str(self.test_definition.get("legacy_test_id", 0))

        substitutions = {
            "%d": test_legacy_id,
            "#MAC": str(device.get("mac_address", self.parameters.get("mac", ""))),
            "#WAN_IP": str(self.parameters.get("wan_ip", device.get("ip_address", ""))),
            "#LAN_CLIENT_IP": str(self.parameters.get("lan_client_ip", "")),
            "#LAN_CLIENT_MAC": str(self.parameters.get("lan_client_mac", "")),
            "#MGMNT_SERVER_IP": str(self.parameters.get("mgmnt_server_ip", "")),
            "#MGMNT_SERVER_IP6": str(self.parameters.get("mgmnt_server_ip6", "")),
        }

        command = command_template
        for token, value in substitutions.items():
            command = command.replace(token, value)

        # Remove unresolved legacy placeholders to avoid script syntax errors.
        command = re.sub(r"#\w+", "", command)
        return self._normalize_paths(command).strip()

    async def execute(self) -> Tuple[bool, str, List[str]]:
        command_template = self._select_command()
        if not command_template:
            error = "No LAN/WAN command configured for this legacy test"
            self.log_error(error)
            return False, self.output, self.errors

        command = self._materialize_command(command_template)
        self.log_output(f"Executing legacy command: {command}")

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=900)

            if stdout:
                self.log_output(stdout.decode(errors="replace"))
            if stderr:
                self.log_output(stderr.decode(errors="replace"))

            if proc.returncode == 0:
                return True, self.output, self.errors

            self.log_error(f"Legacy command failed with exit code {proc.returncode}")
            return False, self.output, self.errors

        except asyncio.TimeoutError:
            self.log_error("Legacy command timed out after 900 seconds")
            return False, self.output, self.errors
        except Exception as exc:
            self.log_error(f"Legacy command execution error: {exc}")
            return False, self.output, self.errors
