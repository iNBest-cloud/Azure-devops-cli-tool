"""
User email mapping utilities.
"""

import json
import logging
from typing import Dict, List, Optional
from pathlib import Path


logger = logging.getLogger(__name__)


def load_email_mapping(mapping_file: str = "user_email_mapping.json") -> Dict[str, str]:
    """
    Load user email mapping from JSON file.

    Args:
        mapping_file: Path to email mapping JSON file

    Returns:
        Dictionary mapping names to email addresses

    Raises:
        FileNotFoundError: If mapping file doesn't exist
        json.JSONDecodeError: If file contains invalid JSON
    """
    mapping_path = Path(mapping_file)
    if not mapping_path.exists():
        raise FileNotFoundError(
            f"Email mapping file not found: {mapping_file}\n"
            f"Please create {mapping_file} with name-to-email mappings"
        )

    with open(mapping_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def resolve_emails(
    assigned_to: Optional[List[str]],
    mapping_file: str = "user_email_mapping.json"
) -> List[str]:
    """
    Resolve user names or emails to email addresses.

    Args:
        assigned_to: List of names or emails (None = all users)
        mapping_file: Path to email mapping JSON file

    Returns:
        List of resolved email addresses
    """
    # Load email mapping
    try:
        email_mapping = load_email_mapping(mapping_file)
    except FileNotFoundError as e:
        logger.error(str(e))
        return []
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in {mapping_file}: {e}")
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
        logger.warning(
            f"⚠️  Could not resolve {len(unknown_names)} name(s): {', '.join(unknown_names)}\n"
            f"   Available names in {mapping_file}: {', '.join(email_mapping.keys())}"
        )

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
