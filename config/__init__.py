"""Configuration management."""

from .settings import Settings, get_settings

# Create global settings instance
settings = get_settings()

__all__ = ["Settings", "get_settings", "settings"]
