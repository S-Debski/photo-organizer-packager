# Role: Central configuration (see Stability Contract)

"""
Configuration module for Photo Organizer
Supports .env files and environment variables
"""

import os
from pathlib import Path
from typing import Optional


class Config:
    """Configuration management"""

    # Default values
    DEFAULT_PICTURES_BASE = None  # Will use ~/Pictures
    DEFAULT_NAS_SHARE = "backups"
    DEFAULT_FLASK_HOST = "0.0.0.0"
    DEFAULT_FLASK_PORT = 5000
    DEFAULT_LOG_LEVEL = "INFO"

    def __init__(self):
        """Load configuration from .env and environment"""
        self.load_env()

    @staticmethod
    def load_env():
        """Load .env file if it exists"""
        env_path = Path(".env")
        if env_path.exists():
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        if "=" in line:
                            key, value = line.split("=", 1)
                            os.environ[key.strip()] = value.strip()

    @property
    def pictures_base(self) -> Optional[str]:
        """Get pictures base directory"""
        return os.getenv("PICTURES_BASE", self.DEFAULT_PICTURES_BASE)

    @property
    def nas_default_address(self) -> Optional[str]:
        """Get default NAS address"""
        return os.getenv("NAS_DEFAULT_ADDRESS")

    @property
    def nas_default_share(self) -> str:
        """Get default NAS share"""
        return os.getenv("NAS_DEFAULT_SHARE", self.DEFAULT_NAS_SHARE)

    @property
    def nas_default_username(self) -> Optional[str]:
        """Get default NAS username"""
        return os.getenv("NAS_DEFAULT_USERNAME")

    @property
    def nas_default_password(self) -> Optional[str]:
        """Get default NAS password"""
        return os.getenv("NAS_DEFAULT_PASSWORD")

    @property
    def flask_host(self) -> str:
        """Get Flask host"""
        return os.getenv("FLASK_HOST", self.DEFAULT_FLASK_HOST)

    @property
    def flask_port(self) -> int:
        """Get Flask port"""
        try:
            return int(os.getenv("FLASK_PORT", self.DEFAULT_FLASK_PORT))
        except ValueError:
            return self.DEFAULT_FLASK_PORT

    @property
    def flask_debug(self) -> bool:
        """Get Flask debug mode"""
        return os.getenv("FLASK_DEBUG", "True").lower() in ("true", "1", "yes")

    @property
    def log_level(self) -> str:
        """Get log level"""
        return os.getenv("LOG_LEVEL", self.DEFAULT_LOG_LEVEL)

    @property
    def log_file(self) -> Optional[str]:
        """Get log file path"""
        return os.getenv("LOG_FILE")

    def __repr__(self):
        """String representation"""
        return f"""
Configuration:
  Pictures Base: {self.pictures_base}
  NAS Address: {self.nas_default_address}
  NAS Share: {self.nas_default_share}
  Flask Host: {self.flask_host}
  Flask Port: {self.flask_port}
  Flask Debug: {self.flask_debug}
  Log Level: {self.log_level}
"""


# Global config instance
config = Config()
