"""
Environment variable loader with validation.
"""

import os
from typing import Optional


class EnvironmentError(Exception):
    """Custom exception for environment configuration errors."""
    pass


def get_required_env(var_name: str, error_message: Optional[str] = None) -> str:
    """
    Get required environment variable or raise clear error.

    Args:
        var_name: Environment variable name
        error_message: Custom error message (optional)

    Returns:
        Environment variable value

    Raises:
        EnvironmentError: If environment variable is not set
    """
    value = os.getenv(var_name)
    if not value:
        if error_message:
            raise EnvironmentError(error_message)
        raise EnvironmentError(
            f"Missing required environment variable: {var_name}\n"
            f"Please set {var_name} in your .env file"
        )
    return value


def get_optional_env(var_name: str, default: str = "") -> str:
    """
    Get optional environment variable with default value.

    Args:
        var_name: Environment variable name
        default: Default value if not set

    Returns:
        Environment variable value or default
    """
    return os.getenv(var_name, default)


def get_logic_app_url() -> str:
    """
    Get Logic App URL from environment with clear error message.

    Returns:
        Logic App URL

    Raises:
        EnvironmentError: If AZURE_LOGIC_APP_URL is not set
    """
    return get_required_env(
        "AZURE_LOGIC_APP_URL",
        "Missing AZURE_LOGIC_APP_URL environment variable.\n"
        "Please add your Logic App URL to the .env file:\n"
        "AZURE_LOGIC_APP_URL=https://prod-xx.region.logic.azure.com:443/..."
    )
