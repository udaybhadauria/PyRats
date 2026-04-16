"""
Configuration file management for RATS
Handles JSON-based config for devices and tests
"""

import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from app.settings import settings
from app.utils import logger


class ConfigManager:
    """Manages configuration files"""

    @staticmethod
    def load_json_config(config_file: Path) -> Dict[str, Any]:
        """
        Load JSON configuration file
        
        Args:
            config_file: Path to config file
            
        Returns:
            Dictionary containing config data
        """
        try:
            if not config_file.exists():
                logger.warning(f"Config file not found: {config_file}")
                return {}
            
            with open(config_file, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in {config_file}: {e}")
            return {}
        except Exception as e:
            logger.error(f"Error loading config {config_file}: {e}")
            return {}

    @staticmethod
    def save_json_config(config_file: Path, data: Dict[str, Any]) -> bool:
        """
        Save JSON configuration file
        
        Args:
            config_file: Path to config file
            data: Data to save
            
        Returns:
            True if successful, False otherwise
        """
        try:
            config_file.parent.mkdir(parents=True, exist_ok=True)
            with open(config_file, 'w') as f:
                json.dump(data, f, indent=2)
            logger.info(f"Config saved to {config_file}")
            return True
        except Exception as e:
            logger.error(f"Error saving config {config_file}: {e}")
            return False

    @staticmethod
    def load_devices() -> Dict[str, Any]:
        """Load device configuration"""
        return ConfigManager.load_json_config(settings.DEVICE_CONFIG)

    @staticmethod
    def save_devices(devices: Dict[str, Any]) -> bool:
        """Save device configuration"""
        return ConfigManager.save_json_config(settings.DEVICE_CONFIG, devices)

    @staticmethod
    def load_tests() -> Dict[str, Any]:
        """Load test configuration"""
        return ConfigManager.load_json_config(settings.TEST_CONFIG)

    @staticmethod
    def save_tests(tests: Dict[str, Any]) -> bool:
        """Save test configuration"""
        return ConfigManager.save_json_config(settings.TEST_CONFIG, tests)

    @staticmethod
    def load_repo_url() -> Optional[str]:
        """Load repository URL from config file"""
        try:
            if settings.REPO_CONFIG.exists():
                with open(settings.REPO_CONFIG, 'r') as f:
                    return f.read().strip()
        except Exception as e:
            logger.error(f"Error loading repo URL: {e}")
        return None

    @staticmethod
    def save_repo_url(url: str) -> bool:
        """Save repository URL to config file"""
        try:
            settings.REPO_CONFIG.parent.mkdir(parents=True, exist_ok=True)
            with open(settings.REPO_CONFIG, 'w') as f:
                f.write(url)
            logger.info(f"Repo URL saved: {url}")
            return True
        except Exception as e:
            logger.error(f"Error saving repo URL: {e}")
            return False
