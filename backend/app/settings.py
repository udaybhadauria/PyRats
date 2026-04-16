"""
Configuration management for RATS backend
Loads from environment variables and config files
"""

import os
import json
from typing import Optional
from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment and .env file"""

    # Application
    APP_NAME: str = "RATS"
    APP_VERSION: str = "2.0.0"
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # Server
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", 8888))
    RELOAD: bool = os.getenv("RELOAD", "false").lower() == "true"

    # MQTT Configuration
    MQTT_BROKER: str = os.getenv("MQTT_BROKER", "localhost")
    MQTT_PORT: int = int(os.getenv("MQTT_PORT", 1883))
    MQTT_USERNAME: Optional[str] = os.getenv("MQTT_USERNAME")
    MQTT_PASSWORD: Optional[str] = os.getenv("MQTT_PASSWORD")
    MQTT_KEEPALIVE: int = 60
    MQTT_QOS: int = 1

    # Topics
    MQTT_DEVICE_DATA_TOPIC: str = "device_data"
    MQTT_SERVER_INFO_TOPIC: str = "server_info"
    MQTT_TEST_COMMAND_TOPIC: str = "test_commands"
    MQTT_TEST_RESULT_TOPIC: str = "test_results"

    # SSL/TLS
    USE_SSL: bool = os.getenv("USE_SSL", "false").lower() == "true"
    CERT_FILE: Optional[str] = os.getenv("CERT_FILE", "ssl/cert.pem")
    KEY_FILE: Optional[str] = os.getenv("KEY_FILE", "ssl/key.pem")
    VERIFY_CERT: bool = os.getenv("VERIFY_CERT", "false").lower() == "true"

    # Configuration Files
    CONFIG_DIR: Path = Path(os.getenv("CONFIG_DIR", "./config"))
    DEVICE_CONFIG: Path = CONFIG_DIR / "devices.json"
    TEST_CONFIG: Path = CONFIG_DIR / "tests.json"
    REPO_CONFIG: Path = CONFIG_DIR / "repo.txt"
    # Legacy assets now embedded in RATS-Dev-Python/backend/
    LEGACY_BACKEND_DIR: Path = Path(
        os.getenv("LEGACY_BACKEND_DIR", "./backend")
    )
    LEGACY_TEST_CONFIG: Path = Path(
        os.getenv("LEGACY_TEST_CONFIG", "./config/test_config.json")
    )
    LEGACY_TESTAPPS_DIR: Path = Path(
        os.getenv("LEGACY_TESTAPPS_DIR", "./backend/TestApps")
    )
    LEGACY_UTILITY_DIR: Path = Path(
        os.getenv("LEGACY_UTILITY_DIR", "./backend/Utility")
    )
    JAR_PATH_FILE: Path = Path(
        os.getenv("JAR_PATH_FILE", "./backend/Utility/jar_path.txt")
    )
    REPO_URL_CONFIG: Path = Path(
        os.getenv("REPO_URL_CONFIG", "./backend/Utility/sw_dl/repourl.txt")
    )

    # Logging
    LOG_DIR: Path = Path(os.getenv("LOG_DIR", "./logs"))
    LOG_FILE: Path = LOG_DIR / "rats.log"

    # Reports
    REPORT_DIR: Path = Path(os.getenv("REPORT_DIR", "./reports"))
    REPORT_FORMAT: str = "html"  # 'html' or 'json'

    # Timeouts
    DEVICE_TIMEOUT: int = 30
    TEST_TIMEOUT: int = 300
    SSH_TIMEOUT: int = 30
    CONNECTION_TIMEOUT: int = 10

    # Features
    ENABLE_ASYNC: bool = True
    ASYNC_WORKERS: int = 4
    MAX_CONCURRENT_TESTS: int = 5

    class Config:
        env_file = ".env"
        case_sensitive = True


# Create singleton settings instance
settings = Settings()

# Ensure required directories exist
settings.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
settings.LOG_DIR.mkdir(parents=True, exist_ok=True)
settings.REPORT_DIR.mkdir(parents=True, exist_ok=True)
