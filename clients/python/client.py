"""
RATS Client - Device-side test executor
Replaces RATS_Client.c C implementation
Runs on target devices, subscribes to test_commands MQTT topic,
executes real legacy LAN test scripts, and publishes results.
"""

import asyncio
import json
import logging
import os
import re
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime
import paho.mqtt.client as mqtt


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("RATS-Client")

# ---------------------------------------------------------------------------
# Path resolution: when TESTAPPS_DIR env var is set the client resolves real
# commands; defaults to the bundled backend/TestApps directory.
# ---------------------------------------------------------------------------
_TESTAPPS_DIR = os.environ.get(
    "RATS_TESTAPPS_DIR",
    str(Path(__file__).parent.parent.parent / "backend" / "TestApps")
)
_UTILITY_DIR = os.environ.get(
    "RATS_UTILITY_DIR",
    str(Path(__file__).parent.parent.parent / "backend" / "Utility")
)


def _resolve_command(cmd_template: str, job_id: str, mac: str, extra: dict) -> str:
    """Materialize a legacy command template with real device values."""
    if not cmd_template or cmd_template == "NA":
        return ""
    substitutions = {
        "%d":              job_id,
        "#MAC":            mac,
        "#WAN_IP":         extra.get("wan_ip", ""),
        "#LAN_CLIENT_IP":  extra.get("lan_client_ip", ""),
        "#LAN_CLIENT_MAC": extra.get("lan_client_mac", ""),
        "#MGMNT_SERVER_IP":  extra.get("mgmnt_server_ip", ""),
        "#MGMNT_SERVER_IP6": extra.get("mgmnt_server_ip6", ""),
        "{{TESTAPPS}}":    _TESTAPPS_DIR,
        "../TestApps/":    _TESTAPPS_DIR + "/",
        "../Utility/":     _UTILITY_DIR + "/",
    }
    cmd = cmd_template
    for token, val in substitutions.items():
        cmd = cmd.replace(token, val)
    # Strip unresolved placeholders
    cmd = re.sub(r"#\w+", "", cmd)
    return cmd.strip()


async def _execute_command(cmd: str, timeout: int = 300) -> tuple[bool, str]:
    """Run a shell command, return (passed, output)."""
    if not cmd:
        return False, "No command to run"
    try:
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        output = stdout.decode(errors="replace")
        return proc.returncode == 0, output
    except asyncio.TimeoutError:
        return False, f"Command timed out after {timeout}s"
    except Exception as exc:
        return False, f"Execution error: {exc}"


@dataclass
class ClientConfig:
    """RATS Client configuration"""
    client_id: str
    device_name: str
    device_mac: str
    mqtt_broker: str = "localhost"
    mqtt_port: int = 1883
    mqtt_username: Optional[str] = None
    mqtt_password: Optional[str] = None
    device_info_file: str = "/var/tmp/device_info.json"
    # Extra device info that command templates may need
    extra: dict = field(default_factory=dict)


class RATSClient:
    """RATS Client for device-side test execution"""

    def __init__(self, config: ClientConfig):
        self.config = config
        self.mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, client_id=config.client_id)
        self.connected = False
        self._pending: asyncio.Queue = asyncio.Queue()
        self._setup_callbacks()

    def _setup_callbacks(self):
        self.mqtt_client.on_connect = self._on_connect
        self.mqtt_client.on_disconnect = self._on_disconnect
        self.mqtt_client.on_message = self._on_message

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.connected = True
            logger.info(f"Connected to MQTT broker at {self.config.mqtt_broker}:{self.config.mqtt_port}")
            client.subscribe("test_commands", qos=1)
            logger.info("Subscribed to test_commands topic")
            self._publish_device_info()
        else:
            logger.error(f"Connection failed with return code {rc}")

    def _on_disconnect(self, client, userdata, rc):
        self.connected = False
        if rc != 0:
            logger.warning(f"Unexpected disconnection (code: {rc})")

    def _on_message(self, client, userdata, msg):
        try:
            command = json.loads(msg.payload.decode('utf-8'))
            logger.info(f"Received command: {command.get('command_id')}")
            # Hand off to async queue so asyncio event loop handles it
            asyncio.get_event_loop().call_soon_threadsafe(
                self._pending.put_nowait, command
            )
        except json.JSONDecodeError as exc:
            logger.error(f"Invalid JSON in message: {exc}")
        except Exception as exc:
            logger.error(f"Error queuing message: {exc}")

    async def _handle_command(self, command: Dict[str, Any]):
        """Execute a test command received via MQTT."""
        command_id = command.get('command_id')
        test_id    = command.get('test_id')
        test_type  = command.get('test_type', 'LAN').upper()
        lan_cmd    = command.get('lan_command', '')
        wan_cmd    = command.get('wan_command', '')
        timeout    = int(command.get('timeout', 300))

        logger.info(f"Executing test: {test_id} (command: {command_id}, type: {test_type})")

        # Pick the right command template based on test_type
        cmd_template = lan_cmd if test_type != 'WAN' else wan_cmd
        if not cmd_template or cmd_template == 'NA':
            cmd_template = lan_cmd or wan_cmd  # fallback to whatever is available

        cmd = _resolve_command(
            cmd_template,
            job_id=str(command.get('job_id', command_id or '0')),
            mac=self.config.device_mac,
            extra={**self.config.extra, **command.get('extra', {})},
        )

        passed, output = await _execute_command(cmd, timeout=timeout)

        result = {
            'command_id': command_id,
            'test_id': test_id,
            'device_id': self.config.device_mac,
            'passed': passed,
            'output': output[:4096],  # cap to avoid oversized MQTT messages
            'timestamp': datetime.now().isoformat(),
        }
        self.mqtt_client.publish("test_results", json.dumps(result), qos=1)
        logger.info(f"Published result for command: {command_id} – {'PASS' if passed else 'FAIL'}")

    def _publish_device_info(self):
        device_info = {
            'client_id': self.config.client_id,
            'device_name': self.config.device_name,
            'device_mac': self.config.device_mac,
            'timestamp': datetime.now().isoformat(),
            'status': 'online',
        }
        self.mqtt_client.publish("device_data", json.dumps(device_info), qos=1)
        logger.info("Published device info")

    async def connect(self) -> bool:
        try:
            if self.config.mqtt_username and self.config.mqtt_password:
                self.mqtt_client.username_pw_set(
                    self.config.mqtt_username, self.config.mqtt_password
                )
            self.mqtt_client.connect(self.config.mqtt_broker, self.config.mqtt_port, keepalive=60)
            self.mqtt_client.loop_start()
            for _ in range(50):
                if self.connected:
                    return True
                await asyncio.sleep(0.1)
            logger.error("Connection timeout")
            return False
        except Exception as exc:
            logger.error(f"Connection error: {exc}")
            return False

    async def disconnect(self):
        self.mqtt_client.loop_stop()
        self.mqtt_client.disconnect()
        logger.info("Disconnected from MQTT broker")

    async def run(self):
        """Run client - connect and process commands via async queue."""
        logger.info(f"Starting RATS Client - {self.config.device_name}")
        connected = await self.connect()
        if not connected:
            logger.error("Failed to connect to broker")
            return
        try:
            while self.connected:
                try:
                    command = await asyncio.wait_for(self._pending.get(), timeout=1.0)
                    await self._handle_command(command)
                except asyncio.TimeoutError:
                    pass  # keep looping
        except KeyboardInterrupt:
            logger.info("Received interrupt signal")
        finally:
            await self.disconnect()


async def main():
    """Main entry point.

    Override any value via environment variables:
       RATS_CLIENT_ID   RATS_DEVICE_NAME  RATS_DEVICE_MAC
       RATS_MQTT_BROKER RATS_MQTT_PORT
       RATS_WAN_IP      RATS_LAN_CLIENT_IP  RATS_MGMNT_SERVER_IP
       RATS_TESTAPPS_DIR  RATS_UTILITY_DIR
    """
    config = ClientConfig(
        client_id   = os.environ.get("RATS_CLIENT_ID",   "RATS_Client_01"),
        device_name = os.environ.get("RATS_DEVICE_NAME", "Gateway-01"),
        device_mac  = os.environ.get("RATS_DEVICE_MAC",  "00:11:22:33:44:55"),
        mqtt_broker = os.environ.get("RATS_MQTT_BROKER", "localhost"),
        mqtt_port   = int(os.environ.get("RATS_MQTT_PORT", 1883)),
        extra={
            "wan_ip":          os.environ.get("RATS_WAN_IP", ""),
            "lan_client_ip":   os.environ.get("RATS_LAN_CLIENT_IP", ""),
            "lan_client_mac":  os.environ.get("RATS_LAN_CLIENT_MAC", ""),
            "mgmnt_server_ip": os.environ.get("RATS_MGMNT_SERVER_IP", ""),
            "mgmnt_server_ip6":os.environ.get("RATS_MGMNT_SERVER_IP6", ""),
        },
    )
    client = RATSClient(config)
    await client.run()


if __name__ == "__main__":
    asyncio.run(main())
