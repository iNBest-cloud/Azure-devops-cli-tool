"""
User email mapping utilities with validation.
"""

import json
import logging
import re
import sys
from typing import Dict, List, Optional, Tuple
from pathlib import Path


logger = logging.getLogger(__name__)


def validate_email_mapping_file(mapping_file: str = "user_email_mapping.json") -> Tuple[bool, str, Dict[str, str]]:
    """
    Validate the email mapping JSON file and return detailed error information.

    Args:
        mapping_file: Path to email mapping JSON file

    Returns:
        Tuple of (is_valid, error_message, mapping_dict)
        - is_valid: True if file is valid
        - error_message: Empty string if valid, otherwise detailed error
        - mapping_dict: The loaded mapping if valid, empty dict otherwise
    """
    mapping_path = Path(mapping_file)

    # Check file exists
    if not mapping_path.exists():
        return False, f"File not found: {mapping_file}", {}

    # Read file content
    try:
        with open(mapping_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        return False, f"Cannot read file: {e}", {}

    # Check for common JSON syntax errors
    if not content.strip():
        return False, "File is empty", {}

    # Try to parse JSON with detailed error reporting
    try:
        mapping = json.loads(content)
    except json.JSONDecodeError as e:
        # Provide helpful error message based on common issues
        error_msg = f"Invalid JSON syntax at line {e.lineno}, column {e.colno}: {e.msg}"

        # Check for trailing comma (most common issue)
        if "Expecting property name" in e.msg or "Illegal trailing comma" in str(e):
            error_msg += "\n   💡 Hint: Check for trailing comma before closing brace '}'"
            error_msg += "\n   Example fix: Remove comma after last entry"

        return False, error_msg, {}

    # Validate structure
    if not isinstance(mapping, dict):
        return False, f"Expected JSON object (dict), got {type(mapping).__name__}", {}

    if len(mapping) == 0:
        return False, "Mapping is empty - no name-to-email entries found", {}

    # Validate each entry
    invalid_entries = []
    email_pattern = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')

    for name, email in mapping.items():
        if not isinstance(name, str) or not name.strip():
            invalid_entries.append(f"Invalid name: {repr(name)}")
        elif not isinstance(email, str) or not email.strip():
            invalid_entries.append(f"Invalid email for '{name}': {repr(email)}")
        elif not email_pattern.match(email):
            invalid_entries.append(f"Invalid email format for '{name}': {email}")

    if invalid_entries:
        return False, "Invalid entries:\n   " + "\n   ".join(invalid_entries), {}

    return True, "", mapping


def load_email_mapping(mapping_file: str = "user_email_mapping.json") -> Dict[str, str]:
    """
    Load user email mapping from JSON file with validation.

    Args:
        mapping_file: Path to email mapping JSON file

    Returns:
        Dictionary mapping names to email addresses

    Raises:
        FileNotFoundError: If mapping file doesn't exist
        ValueError: If file contains invalid JSON or structure
    """
    is_valid, error_msg, mapping = validate_email_mapping_file(mapping_file)

    if not is_valid:
        if "not found" in error_msg.lower():
            raise FileNotFoundError(
                f"Email mapping file not found: {mapping_file}\n"
                f"Please create {mapping_file} with name-to-email mappings"
            )
        raise ValueError(f"Invalid email mapping file ({mapping_file}):\n   {error_msg}")

    return mapping


def resolve_emails(
    assigned_to: Optional[List[str]],
    mapping_file: str = "user_email_mapping.json",
    fail_on_error: bool = True
) -> List[str]:
    """
    Resolve user names or emails to email addresses.

    Args:
        assigned_to: List of names or emails (None = all users)
        mapping_file: Path to email mapping JSON file
        fail_on_error: If True, raise exception on validation errors (default: True)

    Returns:
        List of resolved email addresses

    Raises:
        ValueError: If fail_on_error=True and mapping file is invalid
        FileNotFoundError: If fail_on_error=True and mapping file doesn't exist
    """
    # Validate and load email mapping with clear error messages
    is_valid, error_msg, email_mapping = validate_email_mapping_file(mapping_file)

    if not is_valid:
        error_output = f"""
❌ ERROR: Invalid email mapping configuration
   File: {mapping_file}
   Problem: {error_msg}

   To fix:
   1. Open {mapping_file}
   2. Ensure valid JSON format (no trailing commas, proper quotes)
   3. Each entry should be: "Name": "email@domain.com"

   Example valid format:
   {{
       "John Doe": "john.doe@company.com",
       "Jane Smith": "jane.smith@company.com"
   }}
"""
        print(error_output)
        logger.error(f"Invalid email mapping: {error_msg}")

        if fail_on_error:
            if "not found" in error_msg.lower():
                raise FileNotFoundError(f"Email mapping file not found: {mapping_file}")
            raise ValueError(f"Invalid email mapping file: {error_msg}")
        return []

    # If no specific users requested, return all emails
    if not assigned_to:
        logger.info(f"No users specified, using all {len(email_mapping)} emails from mapping")
        return list(email_mapping.values())

    # Resolve each name/email
    resolved_emails = []
    unknown_names = []

    for identifier in assigned_to:
        identifier = identifier.strip()

        # Check if it's already an email
        if '@' in identifier:
            resolved_emails.append(identifier)
            logger.debug(f"Using email directly: {identifier}")
        # Try to resolve from mapping
        elif identifier in email_mapping:
            email = email_mapping[identifier]
            resolved_emails.append(email)
            logger.debug(f"Resolved '{identifier}' to {email}")
        else:
            unknown_names.append(identifier)
            logger.warning(f"Unknown name '{identifier}' - skipping")

    # Warn about unknown names
    if unknown_names:
        available_names = ', '.join(sorted(email_mapping.keys()))
        print(f"\n⚠️  Could not resolve {len(unknown_names)} name(s): {', '.join(unknown_names)}")
        print(f"   Available names: {available_names}\n")
        logger.warning(f"Unknown names: {unknown_names}")

    logger.info(f"Resolved {len(resolved_emails)} email(s) from {len(assigned_to)} identifier(s)")
    return resolved_emails


def get_all_emails(mapping_file: str = "user_email_mapping.json") -> List[str]:
    """
    Get all email addresses from mapping file.

    Args:
        mapping_file: Path to email mapping JSON file

    Returns:
        List of all email addresses
    """
    try:
        email_mapping = load_email_mapping(mapping_file)
        return list(email_mapping.values())
    except Exception as e:
        logger.error(f"Failed to load email mapping: {e}")
        return []


def validate_configuration_on_startup(mapping_file: str = "user_email_mapping.json") -> bool:
    """
    Validate email mapping configuration at application startup.
    Prints clear error messages and returns False if invalid.

    Call this early in your application to fail fast on configuration errors.

    Args:
        mapping_file: Path to email mapping JSON file

    Returns:
        True if configuration is valid, False otherwise
    """
    print(f"🔍 Validating {mapping_file}...")

    is_valid, error_msg, mapping = validate_email_mapping_file(mapping_file)

    if is_valid:
        print(f"✅ Email mapping valid: {len(mapping)} users configured")
        return True

    print(f"""
❌ CONFIGURATION ERROR: {mapping_file}
   {error_msg}

   The daily snapshot cannot run without a valid email mapping.
   Please fix the configuration and try again.
""")
    return False
