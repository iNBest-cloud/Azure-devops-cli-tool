"""
Logic App client for fetching work items from Fabric Data Warehouse.
Supports date range queries with email filtering.
"""

import requests
import logging
import time
from typing import List, Dict, Any, Optional
from datetime import datetime


class LogicAppClient:
    """Client for calling Logic App endpoint to fetch work items with date ranges."""

    def __init__(self, logic_app_url: str, timeout: int = 60, max_retries: int = 3):
        """
        Initialize Logic App client.

        Args:
            logic_app_url: The HTTP trigger URL of the Azure Logic App
            timeout: Request timeout in seconds (default: 60)
            max_retries: Maximum number of retry attempts (default: 3)
        """
        self.logic_app_url = logic_app_url
        self.timeout = timeout
        self.max_retries = max_retries
        self.logger = logging.getLogger(__name__)

    def get_work_items_by_date_range(
        self,
        from_date: str,
        to_date: str,
        emails: List[str]
    ) -> Dict[str, Any]:
        """
        Fetch work items from Logic App for specified date range and users.

        Args:
            from_date: Start date in YYYY-MM-DD format
            to_date: End date in YYYY-MM-DD format
            emails: List of email addresses to filter by

        Returns:
            Dictionary containing ResultSets.Table1 with work items

        Raises:
            requests.exceptions.RequestException: If request fails after retries
        """
        if not emails:
            self.logger.warning("No emails provided, returning empty result")
            return {"ResultSets": {"Table1": []}}

        # Validate date format
        try:
            datetime.strptime(from_date, "%Y-%m-%d")
            datetime.strptime(to_date, "%Y-%m-%d")
        except ValueError as e:
            self.logger.error(f"Invalid date format: {e}")
            raise ValueError(f"Dates must be in YYYY-MM-DD format: {e}")

        payload = {
            "fromDate": from_date,
            "toDate": to_date,
            "emails": emails
        }

        self.logger.info(
            f"Fetching work items for {len(emails)} users from {from_date} to {to_date}"
        )

        # Retry logic with exponential backoff
        last_exception = None
        for attempt in range(1, self.max_retries + 1):
            try:
                response = requests.post(
                    self.logic_app_url,
                    json=payload,
                    headers={'Content-Type': 'application/json'},
                    timeout=self.timeout
                )

                response.raise_for_status()
                result = response.json()

                # Parse response - handle both direct and body-wrapped formats
                if 'ResultSets' in result:
                    work_items = result['ResultSets'].get('Table1', [])
                    self.logger.info(
                        f"✅ Retrieved {len(work_items)} work items from Logic App"
                    )
                    return result
                elif 'body' in result and 'ResultSets' in result['body']:
                    work_items = result['body']['ResultSets'].get('Table1', [])
                    self.logger.info(
                        f"✅ Retrieved {len(work_items)} work items from Logic App (body-wrapped)"
                    )
                    return result['body']
                else:
                    self.logger.warning(
                        f"Unexpected response format from Logic App: {result}"
                    )
                    return {"ResultSets": {"Table1": []}}

            except requests.exceptions.Timeout as e:
                last_exception = e
                self.logger.warning(
                    f"Attempt {attempt}/{self.max_retries}: Request timeout after {self.timeout}s"
                )

            except requests.exceptions.HTTPError as e:
                last_exception = e
                self.logger.error(
                    f"Attempt {attempt}/{self.max_retries}: HTTP error {e.response.status_code}: {e}"
                )

            except requests.exceptions.RequestException as e:
                last_exception = e
                self.logger.error(
                    f"Attempt {attempt}/{self.max_retries}: Request failed: {e}"
                )

            except Exception as e:
                last_exception = e
                self.logger.error(
                    f"Attempt {attempt}/{self.max_retries}: Unexpected error: {e}"
                )

            # Exponential backoff before retry (except on last attempt)
            if attempt < self.max_retries:
                backoff_time = 2 ** attempt  # 2, 4, 8 seconds
                self.logger.info(f"Retrying in {backoff_time} seconds...")
                time.sleep(backoff_time)

        # All retries exhausted
        error_msg = f"Failed to fetch work items after {self.max_retries} attempts"
        self.logger.error(f"{error_msg}: {last_exception}")
        raise requests.exceptions.RequestException(
            f"{error_msg}: {last_exception}"
        ) from last_exception


def create_logic_app_client(
    logic_app_url: str,
    timeout: int = 60,
    max_retries: int = 3
) -> LogicAppClient:
    """
    Create configured LogicAppClient instance.

    Args:
        logic_app_url: Logic App HTTP trigger URL
        timeout: Request timeout in seconds (default: 60)
        max_retries: Maximum retry attempts (default: 3)

    Returns:
        Configured LogicAppClient instance
    """
    return LogicAppClient(logic_app_url, timeout, max_retries)
