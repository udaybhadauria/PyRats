"""Test executors - Pluggable test implementations"""

from .base_executor import BaseTestExecutor
from .connectivity import ConnectivityTestExecutor
from .speed_test import SpeedTestExecutor
from .port_forward import PortForwardTestExecutor
from .legacy_command import LegacyCommandExecutor

# Registry of available test executors
EXECUTOR_REGISTRY = {
    'connectivity': ConnectivityTestExecutor,
    'speed_test': SpeedTestExecutor,
    'port_forward': PortForwardTestExecutor,
    # Add more test executors here
}


async def get_executor(test_id: str, device_id: str, parameters=None):
    """
    Factory function to get appropriate test executor
    
    Args:
        test_id: Test identifier
        device_id: Device ID
        parameters: Optional test parameters
        
    Returns:
        Instance of test executor
    """
    test_key = test_id.lower()
    executor_class = EXECUTOR_REGISTRY.get(test_key)

    if executor_class is not None:
        return executor_class(device_id, parameters)

    test_definition = parameters.get("_test_definition") if isinstance(parameters, dict) else None
    has_legacy_command = isinstance(test_definition, dict) and (
        test_definition.get("lan_command") or test_definition.get("wan_command")
    )

    if has_legacy_command:
        return LegacyCommandExecutor(
            device_id,
            parameters,
            test_definition=test_definition,
        )

    raise ValueError(f"Unknown test executor: {test_id}")


__all__ = [
    "BaseTestExecutor",
    "ConnectivityTestExecutor",
    "SpeedTestExecutor",
    "PortForwardTestExecutor",
    "LegacyCommandExecutor",
    "EXECUTOR_REGISTRY",
    "get_executor"
]
