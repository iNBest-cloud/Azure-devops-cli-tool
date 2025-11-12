from classes.AzureDevOps import AzureDevOps
from classes.efficiency_calculator import EfficiencyCalculator
from classes.project_discovery import ProjectDiscovery
from config.config_loader import ConfigLoader
from helpers.fabric_logic_app_helper import create_fabric_helper
from helpers.logic_app_client import create_logic_app_client
from helpers.env_loader import get_logic_app_url, EnvironmentError
from helpers.email_mapping import resolve_emails
from helpers.timezone_utils import get_date_boundaries_mexico_city
from datetime import datetime, timedelta
import json
from typing import List, Dict, Optional, Any, Tuple
import csv
import os
import concurrent.futures
import time
import requests
import logging


class WorkItemOperations(AzureDevOps):
    """
    A class for handling work item querying and KPI calculations.
    """
    
    def __init__(self, organization=None, personal_access_token=None, scoring_config=None, config_file=None):
        super().__init__(organization, personal_access_token)

        # Initialize logger
        self.logger = logging.getLogger(__name__)

        # Initialize configuration loader
        self.config_loader = ConfigLoader(config_file or "config/azure_devops_config.json")

        # Merge scoring config with loaded config
        if scoring_config:
            efficiency_config = self.config_loader.get_efficiency_scoring_config()
            efficiency_config.update(scoring_config)
            developer_config = self.config_loader.get_developer_scoring_config()
            if 'developer_score_weights' in scoring_config:
                developer_config['weights'].update(scoring_config['developer_score_weights'])

        # Initialize helper modules
        combined_config = {
            **self.config_loader.get_efficiency_scoring_config(),
            **self.config_loader.get_developer_scoring_config(),
            **self.config_loader.get_business_hours_config()
        }
        self.efficiency_calculator = EfficiencyCalculator(combined_config)
        self.project_discovery = ProjectDiscovery(self)

        # Initialize Fabric Logic App helper (legacy estimated hours)
        logic_app_url = "https://prod-10.northcentralus.logic.azure.com:443/workflows/9e4bccaa8aab448083f7b95d55db8660/triggers/When_an_HTTP_request_is_received/paths/invoke?api-version=2016-10-01&sp=%2Ftriggers%2FWhen_an_HTTP_request_is_received%2Frun&sv=1.0&sig=PgB2Drl6tRQ7Ki418LzCop5QV3wtpVhpVBoiW3I2mS4"
        self.fabric_helper = create_fabric_helper(logic_app_url)

        # Initialize Logic App client for work item fetching (new)
        try:
            work_items_logic_app_url = get_logic_app_url()
            self.logic_app_client = create_logic_app_client(work_items_logic_app_url)
            self.logger.info("✅ Logic App client initialized successfully")
        except EnvironmentError as e:
            self.logger.warning(f"⚠️  Logic App client not initialized: {e}")
            self.logic_app_client = None

        # Project caching
        self.projects_cache_file = "projects_cache.json"

    def _enrich_work_items_with_fabric_estimates(self, work_items: List[Dict]) -> None:
        """
        Set original_estimate for work items using Fabric Logic App as the only source.
        No fallback to DevOps API - Fabric Logic App is the single source of truth.
        """
        if not work_items:
            return

        # Extract work item IDs
        work_item_ids = [str(item['id']) for item in work_items]

        print(f"   Fetching estimated hours for {len(work_item_ids)} work items from Logic App...")

        try:
            # Call Logic App to get estimated hours
            fabric_response = self.fabric_helper.get_estimated_hours_by_ids(work_item_ids)

            # Parse Logic App response - handle both direct and body-wrapped formats
            fabric_work_items = None
            if fabric_response and 'ResultSets' in fabric_response:
                # Direct format: {'ResultSets': {'Table1': [...]}}
                fabric_work_items = fabric_response['ResultSets']['Table1']
            elif fabric_response and 'body' in fabric_response and 'ResultSets' in fabric_response['body']:
                # Wrapped format: {'body': {'ResultSets': {'Table1': [...]}}}
                fabric_work_items = fabric_response['body']['ResultSets']['Table1']

            if fabric_work_items is not None:
                # Create lookup dictionary: WorkItemId -> estimated hours
                fabric_estimates = {}
                for fabric_item in fabric_work_items:
                    work_item_id = str(fabric_item.get('WorkItemId', ''))
                    estimated_hours = fabric_item.get('OriginalEstimate')

                    # Store all estimates from Fabric (including 0 and null)
                    fabric_estimates[work_item_id] = estimated_hours

                # Set original_estimate from Fabric only (including 0, null, or any value)
                enriched_count = 0
                for item in work_items:
                    work_item_id = str(item['id'])
                    if work_item_id in fabric_estimates:
                        item['original_estimate'] = fabric_estimates[work_item_id]
                        item['fabric_enriched'] = True
                        enriched_count += 1

                print(f"   ✅ Set estimates for {enriched_count} work items from Fabric Logic App")
            else:
                print(f"   ⚠️ Unexpected Logic App response format: {fabric_response}")
                print(f"   Expected: {{'ResultSets': {{'Table1': [...]}}}} or {{'body': {{'ResultSets': {{'Table1': [...]}} }}}}")
                print(f"   Make sure Logic App returns data in ResultSets.Table1 or body.ResultSets.Table1 format")

        except Exception as e:
            print(f"   ❌ Error fetching from Logic App: {e}")
            print(f"   Continuing with DevOps API estimates...")


    def get_all_projects(self) -> List[Dict]:
        """Delegate to project discovery module."""
        return self.project_discovery.get_all_projects()
    
    def filter_projects_by_name(self, projects: List[Dict], project_names: List[str]) -> List[Dict]:
        """Delegate to project discovery module."""
        return self.project_discovery.filter_projects_by_name(projects, project_names)
    
    
    def find_projects_with_user_activity(self, 
                                        assigned_to: List[str], 
                                        work_item_types: Optional[List[str]] = None,
                                        states: Optional[List[str]] = None,
                                        start_date: Optional[str] = None,
                                        end_date: Optional[str] = None,
                                        date_field: str = "ClosedDate",
                                        max_projects: int = None) -> List[Dict]:
        """Delegate to project discovery module."""
        return self.project_discovery.find_projects_with_user_activity(
            assigned_to, work_item_types, states, start_date, end_date, date_field, max_projects
        )
    
    
    def get_all_projects_cached(self, refresh_cache: bool = False) -> List[Dict]:
        """Delegate to project discovery module."""
        return self.project_discovery.get_all_projects_cached(refresh_cache)
    
        
    def build_wiql_query(self, 
                        assigned_to: Optional[List[str]] = None,
                        work_item_types: Optional[List[str]] = None,
                        states: Optional[List[str]] = None,
                        start_date: Optional[str] = None,
                        end_date: Optional[str] = None,
                        date_field: str = "ClosedDate",
                        additional_filters: Optional[Dict[str, str]] = None) -> str:
        """
        Build a dynamic WIQL query based on provided parameters.
        
        Args:
            assigned_to: List of users to filter by
            work_item_types: List of work item types to include
            states: List of states to filter by
            start_date: Start date for filtering (YYYY-MM-DD format)
            end_date: End date for filtering (YYYY-MM-DD format)
            date_field: Field to use for date filtering
            additional_filters: Additional filters (area_path, iteration_path, etc.) (optional)
            
        Returns:
            str: WIQL query string
        """
        query = """SELECT [System.Id], [System.Title], [System.AssignedTo], [System.State],
                   [System.WorkItemType], [System.CreatedDate], [System.ChangedDate],
                   [Microsoft.VSTS.Scheduling.StartDate], 
                   [Microsoft.VSTS.Scheduling.TargetDate],
                   [Microsoft.VSTS.Common.ClosedDate],
                   [System.AreaPath], [System.IterationPath]
                   FROM WorkItems WHERE """
        
        conditions = []
        
        # Work item types filter
        if work_item_types:
            types_str = "', '".join(work_item_types)
            conditions.append(f"[System.WorkItemType] IN ('{types_str}')")
        
        # Assigned to filter
        if assigned_to:
            assigned_str = "', '".join(assigned_to)
            conditions.append(f"[System.AssignedTo] IN ('{assigned_str}')")
        
        # States filter (will be handled in date conditions if date filtering is enabled)
        if states and not (start_date or end_date):
            states_str = "', '".join(states)
            conditions.append(f"[System.State] IN ('{states_str}')")
        
        # Enhanced date filtering with strict target date priority (no margin)
        if start_date or end_date:
            date_conditions = []
            
            print(f"🗓️  Using strict date filtering: {start_date} to {end_date} (no margin)")
            
            # Priority 1: Always use target date for primary filtering (prevents old items)
            # This ensures items are only included if their target date is within exact scope
            all_states = (states or [])
            if all_states:
                states_str = "', '".join(all_states)
                target_condition_parts = [f"[System.State] IN ('{states_str}')"]
                
                # Primary filter: Start date OR Target date must be within EXACT range (no margin)
                date_filter_parts = []
                if start_date and end_date:
                    date_filter_parts.append(f"""(
                        ([Microsoft.VSTS.Scheduling.StartDate] >= '{start_date}' AND [Microsoft.VSTS.Scheduling.StartDate] <= '{end_date}') OR
                        ([Microsoft.VSTS.Scheduling.TargetDate] >= '{start_date}' AND [Microsoft.VSTS.Scheduling.TargetDate] <= '{end_date}')
                    )""")
                elif start_date:
                    date_filter_parts.append(f"""(
                        [Microsoft.VSTS.Scheduling.StartDate] >= '{start_date}' OR
                        [Microsoft.VSTS.Scheduling.TargetDate] >= '{start_date}'
                    )""")
                elif end_date:
                    date_filter_parts.append(f"""(
                        [Microsoft.VSTS.Scheduling.StartDate] <= '{end_date}' OR
                        [Microsoft.VSTS.Scheduling.TargetDate] <= '{end_date}'
                    )""")

                if date_filter_parts:
                    target_condition_parts.extend(date_filter_parts)
                
                if len(target_condition_parts) > 1:
                    date_conditions.append(f"({' AND '.join(target_condition_parts)})")
            
            # Priority 2: For closed items without target dates, allow closed date as fallback
            # But only if closed date is within the original range (strict)
            closed_states = ['Closed', 'Done']
            if any(state in closed_states for state in all_states) and date_field == "ClosedDate":
                closed_condition_parts = []
                closed_states_str = "', '".join(closed_states)
                
                # Only include closed items if:
                # 1. They have NO target date (NULL or empty), AND
                # 2. Their closed date is within the original range (strict)
                closed_condition_parts.append(f"[System.State] IN ('{closed_states_str}')")
                closed_condition_parts.append("[Microsoft.VSTS.Scheduling.TargetDate] = ''")  # No target date
                
                if start_date:
                    closed_condition_parts.append(f"[Microsoft.VSTS.Common.ClosedDate] >= '{start_date}'")
                if end_date:
                    closed_condition_parts.append(f"[Microsoft.VSTS.Common.ClosedDate] <= '{end_date}'")
                
                if len(closed_condition_parts) > 1:
                    date_conditions.append(f"({' AND '.join(closed_condition_parts)})")
            
            # Combine date conditions with OR
            if date_conditions:
                # Remove the states filter from main conditions since it's handled in date conditions
                conditions = [c for c in conditions if not c.startswith('[System.State]')]
                conditions.append(f"({' OR '.join(date_conditions)})")
        else:
            # No date filtering - don't add any date conditions
            # The states filter (if any) will be applied normally
            pass
        
        # Additional filters
        if additional_filters:
            for field, value in additional_filters.items():
                if field == "area_path":
                    conditions.append(f"[System.AreaPath] UNDER '{value}'")
                elif field == "iteration_path":
                    conditions.append(f"[System.IterationPath] UNDER '{value}'")
                else:
                    conditions.append(f"[{field}] = '{value}'")
        
        if not conditions:
            conditions.append("1=1")  # Default condition if no filters provided
        
        query += " AND ".join(conditions)
        query += " ORDER BY [System.Id]"
        
        return query
    
    def execute_wiql_query(self, project_id: str, query: str) -> List[int]:
        """
        Execute a WIQL query and return work item IDs with pagination support.
        
        Args:
            project_id: Project ID to query
            query: WIQL query string
            
        Returns:
            List of work item IDs
        """
        print(f"Executing WIQL query with pagination for project: {project_id}")
        base_endpoint = f"{project_id}/_apis/wit/wiql?api-version={self.get_api_version('wiql')}"
        
        # Collect all work items using pagination
        all_work_item_ids = []
        continuation_token = None
        page_count = 0
        
        while True:
            page_count += 1
            
            # Build endpoint with continuation token if available
            if continuation_token:
                endpoint = f"{base_endpoint}&continuationToken={continuation_token}"
                print(f"  Fetching page {page_count} with continuation token...")
            else:
                endpoint = base_endpoint
                print(f"  Fetching page {page_count}...")
            
            # Execute WIQL query
            data = {"query": query}
            response = self.handle_request("POST", endpoint, data)
            
            # Extract work items and continuation token
            page_work_items = response.get("workItems", [])
            continuation_token = response.get("continuationToken")
            
            if page_work_items:
                page_ids = [wi["id"] for wi in page_work_items]
                all_work_item_ids.extend(page_ids)
                print(f"    Found {len(page_ids)} work items on page {page_count}")
            else:
                print(f"    No work items found on page {page_count}")
            
            # Break if no continuation token (last page)
            if not continuation_token:
                print(f"  Pagination complete after {page_count} pages")
                break
                
            # Safety check to prevent infinite loops
            if page_count > 100:
                print(f"  WARNING: Stopping after {page_count} pages to prevent infinite loop")
                break
        
        print(f"Total work items found across all pages: {len(all_work_item_ids)}")
        return all_work_item_ids
    
    def execute_optimized_wiql_query(self, project_id: str, query: str, include_revisions: bool = True) -> Tuple[List[int], Dict]:
        """
        Enhanced WIQL query execution with performance optimization and metrics.
        
        Args:
            project_id: Project ID to query
            query: WIQL query string
            include_revisions: Whether to attempt to fetch revisions in the same call
            
        Returns:
            Tuple of (work_item_ids, performance_metrics)
        """
        start_time = time.time()
        performance_metrics = {
            "wiql_calls": 0,
            "total_api_calls": 0,
            "items_found": 0,
            "optimization_used": None,
            "execution_time": 0
        }
        
        print(f"🚀 Executing optimized WIQL query for project: {project_id}")
        
        # Try enhanced WIQL with $expand parameter first
        base_endpoint = f"{project_id}/_apis/wit/wiql?api-version={self.get_api_version('wiql')}"
        
        if include_revisions:
            try:
                # Attempt to use $expand=all to get additional data in one call
                enhanced_endpoint = f"{base_endpoint}&$expand=all"
                print("  Attempting enhanced WIQL with $expand=all...")
                
                data = {"query": query}
                response = self.handle_request("POST", enhanced_endpoint, data)
                performance_metrics["wiql_calls"] = 1
                performance_metrics["total_api_calls"] = 1
                
                # Check if we got expanded data
                if self._has_expanded_data(response):
                    print("  ✅ Enhanced WIQL successful - got expanded data in single call!")
                    work_item_ids = self._extract_ids_from_expanded_response(response)
                    performance_metrics["items_found"] = len(work_item_ids)
                    performance_metrics["optimization_used"] = "enhanced_wiql_expand"
                    performance_metrics["execution_time"] = time.time() - start_time
                    return work_item_ids, performance_metrics
                else:
                    print("  ⚠️ $expand parameter not supported, falling back to standard WIQL")
                    
            except Exception as e:
                print(f"  ⚠️ Enhanced WIQL failed: {e}, falling back to standard approach")
        
        # Fallback to standard WIQL with pagination
        print("  Using standard WIQL with pagination...")
        all_work_item_ids = []
        continuation_token = None
        page_count = 0
        
        while True:
            page_count += 1
            
            if continuation_token:
                endpoint = f"{base_endpoint}&continuationToken={continuation_token}"
                print(f"    Fetching page {page_count} with continuation token...")
            else:
                endpoint = base_endpoint
                print(f"    Fetching page {page_count}...")
            
            data = {"query": query}
            response = self.handle_request("POST", endpoint, data)
            performance_metrics["wiql_calls"] += 1
            performance_metrics["total_api_calls"] += 1
            
            page_work_items = response.get("workItems", [])
            continuation_token = response.get("continuationToken")
            
            if page_work_items:
                page_ids = [wi["id"] for wi in page_work_items]
                all_work_item_ids.extend(page_ids)
                print(f"      Found {len(page_ids)} work items on page {page_count}")
            else:
                print(f"      No work items found on page {page_count}")
            
            if not continuation_token:
                print(f"    Pagination complete after {page_count} pages")
                break
                
            if page_count > 100:
                print(f"    WARNING: Stopping after {page_count} pages to prevent infinite loop")
                break
        
        performance_metrics["items_found"] = len(all_work_item_ids)
        performance_metrics["optimization_used"] = "standard_wiql_pagination"
        performance_metrics["execution_time"] = time.time() - start_time
        
        print(f"  📊 Performance: {len(all_work_item_ids)} items, {performance_metrics['wiql_calls']} WIQL calls, {performance_metrics['execution_time']:.2f}s")
        return all_work_item_ids, performance_metrics
    
    def _has_expanded_data(self, response: Dict) -> bool:
        """Check if WIQL response contains expanded data like revisions."""
        # Check for common expanded data indicators
        if not response or "workItems" not in response:
            return False
            
        # Look for expanded fields in the response structure
        work_items = response.get("workItems", [])
        if not work_items:
            return False
            
        # Check if any work item has expanded data (revisions, fields, etc.)
        sample_item = work_items[0] if work_items else {}
        expanded_indicators = ["revisions", "fields", "relations", "_links"]
        
        return any(indicator in sample_item for indicator in expanded_indicators)
    
    def _extract_ids_from_expanded_response(self, response: Dict) -> List[int]:
        """Extract work item IDs from expanded WIQL response."""
        work_items = response.get("workItems", [])
        return [wi.get("id") for wi in work_items if wi.get("id")]
    
    def get_work_item_details_batch(self, project_id: str, work_item_ids: List[int],
                                  project_name: str = None, batch_size: int = 200) -> Tuple[List[Dict], Dict]:
        """
        Get detailed information for work items using batch processing and organization-level API.

        Args:
            project_id: Project ID (unused, kept for backward compatibility)
            work_item_ids: List of work item IDs
            project_name: Project name (unused, kept for backward compatibility)
            batch_size: Number of items to fetch per API call (max 200)

        Returns:
            Tuple of (work_items, performance_metrics)
        """
        if not work_item_ids:
            return [], {"batch_calls": 0, "items_processed": 0, "execution_time": 0}

        start_time = time.time()
        performance_metrics = {
            "batch_calls": 0,
            "items_processed": 0,
            "execution_time": 0,
            "average_batch_size": 0
        }

        print(f"🔄 Fetching details for {len(work_item_ids)} work items in batches of {batch_size}")

        all_simplified_items = []

        # Process in batches to optimize API calls
        for i in range(0, len(work_item_ids), batch_size):
            batch = work_item_ids[i:i + batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = ((len(work_item_ids) - 1) // batch_size) + 1

            print(f"  Processing batch {batch_num}/{total_batches}: {len(batch)} items")

            ids_str = ",".join(map(str, batch))
            # Use organization-level API to avoid project name URL encoding issues
            endpoint = f"_apis/wit/workitems?ids={ids_str}&api-version={self.get_api_version('work_items')}"
            
            try:
                response = self.handle_request("GET", endpoint)
                work_items = response.get("value", [])
                performance_metrics["batch_calls"] += 1
                
                # Transform to simpler format with enhanced field extraction
                for wi in work_items:
                    fields = wi.get("fields", {})
                    simplified_item = {
                        "id": wi["id"],
                        "title": fields.get("System.Title", ""),
                        "assigned_to": fields.get("System.AssignedTo", {}).get("displayName", "Unassigned"),
                        "state": fields.get("System.State", ""),
                        "work_item_type": fields.get("System.WorkItemType", ""),
                        "created_date": fields.get("System.CreatedDate", ""),
                        "changed_date": fields.get("System.ChangedDate", ""),
                        "start_date": fields.get("Microsoft.VSTS.Scheduling.StartDate", ""),
                        "target_date": fields.get("Microsoft.VSTS.Scheduling.TargetDate", ""),
                        "closed_date": fields.get("Microsoft.VSTS.Common.ClosedDate", ""),
                        "resolved_date": fields.get("Microsoft.VSTS.Common.ResolvedDate", ""),
                        "area_path": fields.get("System.AreaPath", ""),
                        "iteration_path": fields.get("System.IterationPath", ""),
                        # Enhanced fields from schema
                        "original_estimate": None,  # Will be set by Fabric Logic App only
                        "priority": fields.get("Microsoft.VSTS.Common.Priority", 0),
                        "reason": fields.get("System.Reason", ""),
                        "resolved_by": fields.get("Microsoft.VSTS.Common.ResolvedBy", {}).get("displayName", ""),
                        "created_by": fields.get("System.CreatedBy", {}).get("displayName", ""),
                        "changed_by": fields.get("System.ChangedBy", {}).get("displayName", ""),
                        # Custom fields (if available)
                        "custom_fecha_planificada": fields.get("Custom.FechaPlanificada", ""),
                        "custom_tipo_actividad": fields.get("Custom.TipoActividad", "")
                    }
                    all_simplified_items.append(simplified_item)
                    
                performance_metrics["items_processed"] += len(work_items)
                print(f"    ✅ Batch {batch_num} processed: {len(work_items)} items")
                
            except Exception as e:
                print(f"    ❌ Batch {batch_num} failed: {e}")
                continue
        
        performance_metrics["execution_time"] = time.time() - start_time
        performance_metrics["average_batch_size"] = len(work_item_ids) / max(performance_metrics["batch_calls"], 1)
        
        print(f"  📊 Batch processing complete: {performance_metrics['items_processed']} items, "
              f"{performance_metrics['batch_calls']} API calls, {performance_metrics['execution_time']:.2f}s")
        
        return all_simplified_items, performance_metrics

    def get_work_item_revisions(self, project_id: str, work_item_id: int, project_name: str = None) -> List[Dict]:
        """
        Get revision history for a work item using organization-level API.

        Args:
            project_id: Project ID (unused, kept for backward compatibility)
            work_item_id: Work item ID
            project_name: Project name (unused, kept for backward compatibility)
        Returns:
            List of revisions with state and date information
        """
        # Use organization-level API to avoid project name URL encoding issues
        endpoint = f"_apis/wit/workitems/{work_item_id}/revisions?api-version={self.get_api_version('work_items')}"
        response = self.handle_request("GET", endpoint)
        revisions = response.get("value", [])
        # Transform revisions to simpler format
        simplified_revisions = []
        for revision in revisions:
            fields = revision.get("fields", {})
            simplified_revision = {
                "revision": revision.get("rev", 0),
                "state": fields.get("System.State", ""),
                "changed_date": fields.get("System.ChangedDate", ""),
                "changed_by": fields.get("System.ChangedBy", {}).get("displayName", "Unknown"),
                "reason": fields.get("System.Reason", ""),
                # Include fields for historical estimate retrieval
                "fields": {
                    "Microsoft.VSTS.Scheduling.OriginalEstimate": fields.get("Microsoft.VSTS.Scheduling.OriginalEstimate", 0),
                    "System.State": fields.get("System.State", ""),
                    "System.Reason": fields.get("System.Reason", "")
                }
            }
            simplified_revisions.append(simplified_revision)
        return simplified_revisions
    
    def get_work_item_revisions_parallel(self, work_items: List[Dict], max_workers: int = 10, 
                                       batch_size: int = 50) -> Tuple[List[Dict], Dict]:
        """
        Get revision history for multiple work items using parallel processing with connection pooling.
        
        Args:
            work_items: List of work items with project_id, id, and project_name
            max_workers: Maximum number of concurrent threads
            batch_size: Number of items to process per batch
            
        Returns:
            Tuple of (work_items_with_revisions, performance_metrics)
        """
        if not work_items:
            return [], {"revision_calls": 0, "items_processed": 0, "execution_time": 0, "failed_items": 0}
        
        start_time = time.time()
        performance_metrics = {
            "revision_calls": 0,
            "items_processed": 0,
            "execution_time": 0,
            "failed_items": 0,
            "parallel_batches": 0,
            "average_revisions_per_item": 0
        }
        
        print(f"⚡ Fetching revisions for {len(work_items)} work items using parallel processing...")
        print(f"  Configuration: {max_workers} workers, batch size {batch_size}")
        
        # Create a session for connection pooling
        def create_session():
            session = requests.Session()
            session.headers.update({
                "Authorization": f"Basic {self.encoded_pat}",
                "Content-Type": "application/json"
            })
            return session
        
        def fetch_revisions_for_item(session, item):
            """Fetch revisions for a single work item using organization-level API."""
            try:
                # Use organization-level API to avoid project name URL encoding issues
                url = f"{self.base_url}_apis/wit/workitems/{item['id']}/revisions?api-version={self.get_api_version('work_items')}"

                response = session.get(url, timeout=30)
                response.raise_for_status()
                
                revisions_data = response.json()
                revisions = revisions_data.get("value", [])
                
                # Transform revisions to simpler format
                simplified_revisions = []
                for revision in revisions:
                    fields = revision.get("fields", {})
                    simplified_revision = {
                        "revision": revision.get("rev", 0),
                        "state": fields.get("System.State", ""),
                        "changed_date": fields.get("System.ChangedDate", ""),
                        "changed_by": fields.get("System.ChangedBy", {}).get("displayName", "Unknown"),
                        "reason": fields.get("System.Reason", ""),
                        # Include fields for historical estimate retrieval
                        "fields": {
                            "Microsoft.VSTS.Scheduling.OriginalEstimate": fields.get("Microsoft.VSTS.Scheduling.OriginalEstimate", 0),
                            "System.State": fields.get("System.State", ""),
                            "System.Reason": fields.get("System.Reason", "")
                        }
                    }
                    simplified_revisions.append(simplified_revision)
                
                item["revisions"] = simplified_revisions
                return {"item": item, "success": True, "revision_count": len(simplified_revisions)}
                
            except Exception as e:
                print(f"    ❌ Failed to get revisions for item {item['id']}: {e}")
                item["revisions"] = []
                return {"item": item, "success": False, "revision_count": 0}
        
        def process_batch(batch_items):
            """Process a batch of items with a dedicated session."""
            session = create_session()
            batch_results = []
            batch_revision_calls = 0
            batch_failed = 0
            total_revisions = 0
            
            try:
                for item in batch_items:
                    result = fetch_revisions_for_item(session, item)
                    batch_results.append(result["item"])
                    batch_revision_calls += 1
                    total_revisions += result["revision_count"]
                    
                    if not result["success"]:
                        batch_failed += 1
                        
                return {
                    "items": batch_results,
                    "calls": batch_revision_calls,
                    "failed": batch_failed,
                    "total_revisions": total_revisions
                }
            finally:
                session.close()
        
        # Process work items in batches using parallel execution
        batches = [work_items[i:i + batch_size] for i in range(0, len(work_items), batch_size)]
        performance_metrics["parallel_batches"] = len(batches)
        
        all_items_with_revisions = []
        total_revisions_fetched = 0
        
        print(f"  Processing {len(batches)} batches in parallel...")
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all batches for parallel processing
            future_to_batch = {executor.submit(process_batch, batch): i for i, batch in enumerate(batches)}
            
            for future in concurrent.futures.as_completed(future_to_batch):
                batch_idx = future_to_batch[future]
                try:
                    batch_result = future.result()
                    
                    all_items_with_revisions.extend(batch_result["items"])
                    performance_metrics["revision_calls"] += batch_result["calls"]
                    performance_metrics["failed_items"] += batch_result["failed"]
                    total_revisions_fetched += batch_result["total_revisions"]
                    
                    success_count = batch_result["calls"] - batch_result["failed"]
                    print(f"    ✅ Batch {batch_idx + 1}/{len(batches)} complete: "
                          f"{success_count}/{batch_result['calls']} successful, "
                          f"{batch_result['total_revisions']} revisions fetched")
                    
                except Exception as e:
                    print(f"    ❌ Batch {batch_idx + 1} failed: {e}")
                    # Add items without revisions to maintain order
                    for item in batches[batch_idx]:
                        item["revisions"] = []
                        all_items_with_revisions.append(item)
                        performance_metrics["failed_items"] += 1
        
        performance_metrics["items_processed"] = len(all_items_with_revisions)
        performance_metrics["execution_time"] = time.time() - start_time
        performance_metrics["average_revisions_per_item"] = total_revisions_fetched / max(len(work_items), 1)
        
        success_rate = ((performance_metrics["items_processed"] - performance_metrics["failed_items"]) / 
                       max(performance_metrics["items_processed"], 1)) * 100
        
        print(f"  📊 Parallel revision fetching complete:")
        print(f"    • {performance_metrics['items_processed']} items processed")
        print(f"    • {performance_metrics['revision_calls']} API calls made")
        print(f"    • {total_revisions_fetched} total revisions fetched")
        print(f"    • {success_rate:.1f}% success rate")
        print(f"    • {performance_metrics['execution_time']:.2f}s execution time")
        print(f"    • {performance_metrics['average_revisions_per_item']:.1f} avg revisions per item")
        
        return all_items_with_revisions, performance_metrics

    def calculate_fair_efficiency_metrics(self, 
                                         work_item: Dict,
                                         state_history: List[Dict], 
                                         state_config: Optional[Dict] = None,
                                         timeframe_start: Optional[str] = None,
                                         timeframe_end: Optional[str] = None) -> Dict:
        """Delegate to efficiency calculator module with state configuration."""
        return self.efficiency_calculator.calculate_fair_efficiency_metrics(
            work_item, state_history, state_config, timeframe_start, timeframe_end
        )
    
    
    
    
    def _get_total_assigned_items_by_developer(self, target_projects: List[Dict], 
                                              assigned_to: List[str], 
                                              work_item_types: List[str],
                                              start_date: Optional[str] = None,
                                              end_date: Optional[str] = None) -> Dict[str, int]:
        """
        Get total count of assigned items per developer regardless of state,
        filtered by start/target dates within the specified timeframe.
        
        Args:
            target_projects: List of projects to query
            assigned_to: List of developers to count items for
            work_item_types: List of work item types to include
            start_date: Start date for filtering (YYYY-MM-DD format)
            end_date: End date for filtering (YYYY-MM-DD format)
            
        Returns:
            Dictionary mapping developer name to total assigned item count
        """
        # Build query to count ALL assigned items (no state filter)
        assigned_counts = {}
        
        for developer in assigned_to:
            total_count = 0
            
            # Query each project for this developer's total assigned items
            for project in target_projects:
                try:
                    # Build query to get assigned items with date filtering
                    work_item_types_str = "', '".join(work_item_types)
                    conditions = [
                        f"[System.AssignedTo] = '{developer}'",
                        f"[System.WorkItemType] IN ('{work_item_types_str}')"
                    ]
                    
                    # Add date filtering for start_date or target_date within timeframe
                    if start_date and end_date:
                        date_condition = f"""(
                            ([Microsoft.VSTS.Scheduling.StartDate] >= '{start_date}' AND [Microsoft.VSTS.Scheduling.StartDate] <= '{end_date}') OR
                            ([Microsoft.VSTS.Scheduling.TargetDate] >= '{start_date}' AND [Microsoft.VSTS.Scheduling.TargetDate] <= '{end_date}')
                        )"""
                        conditions.append(date_condition)
                    elif start_date:
                        date_condition = f"""(
                            [Microsoft.VSTS.Scheduling.StartDate] >= '{start_date}' OR
                            [Microsoft.VSTS.Scheduling.TargetDate] >= '{start_date}'
                        )"""
                        conditions.append(date_condition)
                    elif end_date:
                        date_condition = f"""(
                            [Microsoft.VSTS.Scheduling.StartDate] <= '{end_date}' OR
                            [Microsoft.VSTS.Scheduling.TargetDate] <= '{end_date}'
                        )"""
                        conditions.append(date_condition)
                    
                    count_query = f"SELECT [System.Id] FROM WorkItems WHERE {' AND '.join(conditions)}"
                    
                    endpoint = f"{project['id']}/_apis/wit/wiql?api-version=7.0"
                    response = self.handle_request(
                        "POST",
                        endpoint,
                        data={"query": count_query}
                    )
                    
                    if response and 'workItemRelations' in response:
                        total_count += len(response['workItemRelations'])
                    elif response and 'workItems' in response:
                        total_count += len(response['workItems'])
                        
                except Exception as e:
                    print(f"Warning: Failed to get assigned count for {developer} in project {project['name']}: {e}")
                    continue
            
            assigned_counts[developer] = total_count
            
        return assigned_counts

    def calculate_comprehensive_kpi_per_developer(self, work_items: List[Dict], 
                                                  assigned_counts: Dict[str, int] = None) -> Dict:
        """
        Calculate comprehensive KPIs separated by developer with fair efficiency metrics.
        
        Args:
            work_items: List of work items with enhanced efficiency data (filtered by query states)
            assigned_counts: Dictionary mapping developer to total assigned items count (all states)
        Returns:
            Dictionary with per-developer KPI metrics and overall summary
        """
        if not work_items:
            return {
                "overall_summary": {
                    "total_work_items": 0,
                    "total_developers": 0,
                    "average_fair_efficiency": 0,
                    "average_delivery_score": 0,
                    "total_active_hours": 0
                },
                "developer_metrics": {},
                "bottlenecks": []
            }
        
        # Group work items by developer
        developer_items = {}
        for item in work_items:
            assigned_to = item.get('assigned_to', 'Unassigned')
            if assigned_to not in developer_items:
                developer_items[assigned_to] = []
            developer_items[assigned_to].append(item)
        
        # Calculate metrics for each developer
        developer_metrics = {}
        all_state_occurrences = {}
        total_fair_efficiency = 0
        total_delivery_score = 0
        total_active_hours = 0
        total_developers = len(developer_items)
        
        for developer, items in developer_items.items():
            # Get total assigned count for this developer (all states)
            total_assigned = assigned_counts.get(developer) if assigned_counts else None
            metrics = self._calculate_developer_metrics(items, total_assigned)
            developer_metrics[developer] = metrics
            
            # Aggregate for overall summary
            total_fair_efficiency += metrics['average_fair_efficiency']
            total_delivery_score += metrics['average_delivery_score']
            total_active_hours += metrics['total_active_hours']
            
            # Collect state data for bottleneck analysis
            for item in items:
                efficiency_data = item.get('efficiency', {})
                for state, hours in efficiency_data.get('state_breakdown', {}).items():
                    if state not in all_state_occurrences:
                        all_state_occurrences[state] = {'count': 0, 'total_hours': 0}
                    all_state_occurrences[state]['count'] += 1
                    all_state_occurrences[state]['total_hours'] += hours
        
        # Calculate overall bottlenecks
        bottlenecks = []
        for state, data in all_state_occurrences.items():
            avg_time = data['total_hours'] / data['count'] if data['count'] > 0 else 0
            bottlenecks.append({
                'state': state,
                'average_time_hours': round(avg_time, 2),
                'occurrences': data['count']
            })
        bottlenecks.sort(key=lambda x: x['average_time_hours'], reverse=True)
        
        # Overall summary
        overall_summary = {
            'total_work_items': len(work_items),
            'total_developers': total_developers,
            'average_fair_efficiency': round(total_fair_efficiency / total_developers, 2) if total_developers > 0 else 0,
            'average_delivery_score': round(total_delivery_score / total_developers, 2) if total_developers > 0 else 0,
            'total_active_hours': round(total_active_hours, 2)
        }
        
        return {
            'overall_summary': overall_summary,
            'developer_metrics': developer_metrics,
            'bottlenecks': bottlenecks[:5]
        }
    
    def _calculate_developer_metrics(self, work_items: List[Dict], total_assigned_items: int = None) -> Dict:
        """
        Calculate detailed metrics for a single developer.
        
        Args:
            work_items: List of work items for one developer (filtered by query states)
            total_assigned_items: Total number of items assigned to developer (all states)
            
        Returns:
            Dictionary with developer-specific metrics
        """
        if not work_items:
            return self._empty_developer_metrics(total_assigned_items)
        
        # Use provided total or fallback to filtered items count
        total_items = total_assigned_items if total_assigned_items is not None else len(work_items)
        completed_items = 0
        items_with_efficiency = 0  # Only items with active_time > 0 AND estimated_hours > 0
        items_with_estimated = 0  # Items with estimated_hours > 0 (for confidence calculation)
        items_with_data = 0  # All completed items with efficiency data
        on_time_count = 0
        total_fair_efficiency = 0
        total_delivery_score = 0
        total_active_hours = 0
        total_estimated_hours = 0
        total_days_ahead_behind = 0
        reopened_items = 0
        work_item_types = set()
        projects = set()

        delivery_timing_counts = {
            'early': 0, 'on_time': 0, 'late_1_3': 0,
            'late_4_7': 0, 'late_8_14': 0, 'late_15_plus': 0
        }

        for item in work_items:
            # Basic counts
            work_item_types.add(item.get('work_item_type', 'Unknown'))
            projects.add(item.get('project_name', 'Unknown'))

            if item.get('state', '').lower() in ['closed', 'done', 'resolved']:
                completed_items += 1

            # All metrics except efficiency (for all completed items)
            efficiency_data = item.get('efficiency', {})
            if efficiency_data and any(efficiency_data.values()):  # Has meaningful efficiency data
                items_with_data += 1
                active_time = efficiency_data.get('active_time_hours', 0)
                estimated_hours_item = efficiency_data.get('estimated_time_hours', 0)

                # Track items with estimated hours > 0 for confidence calculation
                if estimated_hours_item > 0:
                    items_with_estimated += 1

                # Efficiency calculation: ONLY for items with active_time > 0 AND estimated_hours > 0
                if active_time > 0 and estimated_hours_item > 0:
                    items_with_efficiency += 1
                    total_fair_efficiency += efficiency_data.get('fair_efficiency_score', 0)

                # Everything else: ALL items with efficiency data
                total_delivery_score += efficiency_data.get('delivery_score', 100)
                total_active_hours += active_time
                total_estimated_hours += efficiency_data.get('estimated_time_hours', 0)
                total_days_ahead_behind += efficiency_data.get('days_ahead_behind', 0)

                if efficiency_data.get('was_reopened', False):
                    reopened_items += 1

                # Delivery timing analysis: items with efficiency data only
                days_diff = efficiency_data.get('days_ahead_behind', 0)
                if days_diff <= 0:
                    if days_diff <= -1:
                        delivery_timing_counts['early'] += 1
                    else:
                        delivery_timing_counts['on_time'] += 1
                    on_time_count += 1
                elif days_diff <= 3:
                    delivery_timing_counts['late_1_3'] += 1
                elif days_diff <= 7:
                    delivery_timing_counts['late_4_7'] += 1
                elif days_diff <= 14:
                    delivery_timing_counts['late_8_14'] += 1
                else:
                    delivery_timing_counts['late_15_plus'] += 1

        # Calculate averages and percentages
        completion_rate = (completed_items / total_items) * 100 if total_items > 0 else 0

        # Efficiency: ONLY from items with active_time > 0 AND estimated_hours > 0
        if items_with_efficiency > 0:
            avg_fair_efficiency = total_fair_efficiency / items_with_efficiency

            # Apply confidence adjustment to efficiency based on sample size
            # Confidence = items with active time / items with estimated hours > 0
            confidence = items_with_efficiency / items_with_estimated if items_with_estimated > 0 else 0
            confidence_factor = min(1.0, confidence * 3)  # Factor of 3, capped at 100%
            avg_fair_efficiency = avg_fair_efficiency * confidence_factor
        else:
            avg_fair_efficiency = 0
            confidence = 0

        # Everything else: from ALL items with efficiency data
        if items_with_data > 0:
            on_time_delivery = (on_time_count / items_with_data) * 100
            avg_delivery_score = total_delivery_score / items_with_data
            avg_days_ahead_behind = total_days_ahead_behind / items_with_data
            reopened_rate = (reopened_items / items_with_data) * 100
        else:
            on_time_delivery = 0
            avg_delivery_score = 0
            avg_days_ahead_behind = 0
            reopened_rate = 0
        
        # Overall developer score (using configurable weights)
        overall_score = self.efficiency_calculator.calculate_developer_score(
            completion_rate, avg_fair_efficiency, avg_delivery_score, on_time_delivery
        )
        
        return {
            'total_work_items': total_items,
            'completed_items': completed_items,
            'items_with_efficiency': items_with_efficiency,
            'sample_confidence': round(confidence * 100, 2) if items_with_efficiency > 0 else 0,
            'completion_rate': round(completion_rate, 2),
            'on_time_delivery_percentage': round(on_time_delivery, 2),
            'average_fair_efficiency': round(avg_fair_efficiency, 2),
            'average_delivery_score': round(avg_delivery_score, 2),
            'overall_developer_score': round(overall_score, 2),
            'total_active_hours': round(total_active_hours, 2),
            'total_estimated_hours': round(total_estimated_hours, 2),
            'average_days_ahead_behind': round(avg_days_ahead_behind, 2),
            'reopened_items_handled': reopened_items,
            'reopened_rate': round(reopened_rate, 2),
            'work_item_types_count': len(work_item_types),
            'work_item_types': list(work_item_types),
            'projects_count': len(projects),
            'projects': list(projects),
            'delivery_timing_breakdown': delivery_timing_counts
        }
    
    def _empty_developer_metrics(self, total_assigned_items: int = 0) -> Dict:
        """Return empty metrics structure for developers with no work items."""
        return {
            'total_work_items': total_assigned_items or 0,
            'completed_items': 0,
            'items_with_efficiency': 0,
            'sample_confidence': 0,
            'completion_rate': 0,
            'on_time_delivery_percentage': 0,
            'average_fair_efficiency': 0,
            'average_delivery_score': 0,
            'overall_developer_score': 0,
            'total_active_hours': 0,
            'total_estimated_hours': 0,
            'average_days_ahead_behind': 0,
            'reopened_items_handled': 0,
            'reopened_rate': 0,
            'work_item_types_count': 0,
            'work_item_types': [],
            'projects_count': 0,
            'projects': [],
            'delivery_timing_breakdown': {
                'early': 0, 'on_time': 0, 'late_1_3': 0,
                'late_4_7': 0, 'late_8_14': 0, 'late_15_plus': 0
            }
        }
    
    def execute_organization_wiql_query(self, 
                                       query: str, 
                                       target_projects: Optional[List[Dict]] = None,
                                       project_names: Optional[List[str]] = None) -> List[Dict]:
        print("Executing organization-level WIQL query with pagination...")
        base_endpoint = f"_apis/wit/wiql?api-version={self.get_api_version('wiql')}"
        
        # Apply project filtering if specified
        if target_projects and len(target_projects) < 20:
            project_names = [p['name'] for p in target_projects]
            project_filter = "', '".join(project_names)
            if "WHERE" in query.upper():
                query = query.replace("WHERE", f"WHERE [System.TeamProject] IN ('{project_filter}') AND")
            else:
                query = query.replace("FROM WorkItems", f"FROM WorkItems WHERE [System.TeamProject] IN ('{project_filter}')")
        
        print(f"Organization query: {query}")
        
        # Collect all work items using pagination
        all_work_item_ids = []
        continuation_token = None
        page_count = 0
        
        while True:
            page_count += 1
            
            # Build endpoint with continuation token if available
            if continuation_token:
                endpoint = f"{base_endpoint}&continuationToken={continuation_token}"
                print(f"  Fetching page {page_count} with continuation token...")
            else:
                endpoint = base_endpoint
                print(f"  Fetching page {page_count}...")
            
            # Execute WIQL query
            data = {"query": query}
            response = self.handle_request("POST", endpoint, data)
            
            # Extract work items and continuation token
            page_work_items = response.get("workItems", [])
            continuation_token = response.get("continuationToken")
            
            if page_work_items:
                all_work_item_ids.extend(page_work_items)
                print(f"    Found {len(page_work_items)} work items on page {page_count}")
            else:
                print(f"    No work items found on page {page_count}")
            
            # Break if no continuation token (last page)
            if not continuation_token:
                print(f"  Pagination complete after {page_count} pages")
                break
                
            # Safety check to prevent infinite loops
            if page_count > 100:
                print(f"  WARNING: Stopping after {page_count} pages to prevent infinite loop")
                break
        
        if not all_work_item_ids:
            print("No work items found across all pages")
            return []
            
        print(f"Total work items found across all pages: {len(all_work_item_ids)}")
        print("Fetching detailed work item information...")
        
        all_work_items = []
        batch_size = 200
        # Build a mapping from project id and name to project info for later use
        project_id_to_name = {}
        project_name_to_id = {}
        if target_projects:
            for proj in target_projects:
                project_id_to_name[proj['id']] = proj['name']
                project_name_to_id[proj['name'].strip()] = proj['id']
        for i in range(0, len(all_work_item_ids), batch_size):
            batch = all_work_item_ids[i:i + batch_size]
            ids = [str(item['id']) for item in batch]
            ids_str = ",".join(ids)
            # Use organization-level work items endpoint
            details_endpoint = f"_apis/wit/workitems?ids={ids_str}&api-version={self.get_api_version('work_items')}"
            details_response = self.handle_request("GET", details_endpoint)
            batch_items = details_response.get("value", [])
            for wi in batch_items:
                fields = wi.get("fields", {})
                # Try to get project id, else resolve from project name
                project_id = fields.get("System.TeamProjectId")
                project_name = fields.get("System.TeamProject", "Unknown")
                if not project_id and project_name != "Unknown" and project_name_to_id:
                    # Strict match: strip and case-sensitive
                    project_id = project_name_to_id.get(project_name.strip())
                simplified_item = {
                    "id": wi["id"],
                    "title": fields.get("System.Title", ""),
                    "assigned_to": fields.get("System.AssignedTo", {}).get("displayName", "Unassigned"),
                    "state": fields.get("System.State", ""),
                    "work_item_type": fields.get("System.WorkItemType", ""),
                    "created_date": fields.get("System.CreatedDate", ""),
                    "changed_date": fields.get("System.ChangedDate", ""),
                    "start_date": fields.get("Microsoft.VSTS.Scheduling.StartDate", ""),
                    "target_date": fields.get("Microsoft.VSTS.Scheduling.TargetDate", ""),
                    "closed_date": fields.get("Microsoft.VSTS.Common.ClosedDate", ""),
                    "resolved_date": fields.get("Microsoft.VSTS.Common.ResolvedDate", ""),
                    "area_path": fields.get("System.AreaPath", ""),
                    "iteration_path": fields.get("System.IterationPath", ""),
                    "project_id": project_id if project_id else "Unknown",
                    "project_name": project_name,
                    # Enhanced fields
                    "original_estimate": None,  # Will be set by Fabric Logic App only
                    "priority": fields.get("Microsoft.VSTS.Common.Priority", 0),
                    "reason": fields.get("System.Reason", ""),
                    "resolved_by": fields.get("Microsoft.VSTS.Common.ResolvedBy", {}).get("displayName", ""),
                    "created_by": fields.get("System.CreatedBy", {}).get("displayName", ""),
                    "changed_by": fields.get("System.ChangedBy", {}).get("displayName", "")
                }
                all_work_items.append(simplified_item)
        return all_work_items



    def get_work_items_from_logic_app(self,
                                       from_date: str,
                                       to_date: str,
                                       assigned_to: Optional[List[str]] = None,
                                       calculate_efficiency: bool = True,
                                       use_parallel_processing: bool = True,
                                       max_workers: int = 10,
                                       export_csv: Optional[str] = None) -> Dict:
        """
        🚀 NEW DEFAULT METHOD: Fetch work items from Logic App and calculate efficiency.

        This is the new default flow for --query-work-items that replaces WIQL/Analytics fetching.

        Flow:
        1. Resolve user names/emails from user_email_mapping.json
        2. Call Logic App with date range and emails
        3. Parse ResultSets.Table1 into work items list
        4. For each unique (WorkItemId, AssignedToUser): fetch DevOps activity log
        5. Calculate productivity time using existing efficiency calculator
        6. Produce same CSVs and summaries as before

        Args:
            from_date: Start date in YYYY-MM-DD format
            to_date: End date in YYYY-MM-DD format
            assigned_to: List of user names or emails (None = all users from mapping)
            calculate_efficiency: Whether to calculate efficiency metrics (default: True)
            use_parallel_processing: Enable parallel revision fetching (default: True)
            max_workers: Number of parallel workers (default: 10)
            export_csv: CSV filename for export (optional)

        Returns:
            Dictionary with work items, KPIs, and query info
        """
        overall_start_time = time.time()

        print("🚀 ========================================")
        print("🚀 LOGIC APP WORK ITEM FETCHING")
        print("🚀 ========================================")

        # Validate Logic App client
        if not self.logic_app_client:
            raise EnvironmentError(
                "Logic App client not initialized. Please set AZURE_LOGIC_APP_URL in .env file."
            )

        # Phase 1: Resolve emails
        phase_start = time.time()
        print(f"\n📧 Phase 1: Resolving emails...")

        emails = resolve_emails(assigned_to)
        if not emails:
            print("❌ No valid emails resolved. Please check user_email_mapping.json")
            return self._empty_result()

        print(f"✅ Resolved {len(emails)} email(s): {', '.join(emails)}")
        resolution_time = time.time() - phase_start

        # Phase 2: Fetch from Logic App
        phase_start = time.time()
        print(f"\n🔄 Phase 2: Fetching work items from Logic App...")
        print(f"   Date range: {from_date} to {to_date}")

        try:
            logic_app_response = self.logic_app_client.get_work_items_by_date_range(
                from_date=from_date,
                to_date=to_date,
                emails=emails
            )
        except requests.exceptions.RequestException as e:
            print(f"❌ Failed to fetch from Logic App: {e}")
            raise

        # Parse response
        work_items_raw = logic_app_response.get('ResultSets', {}).get('Table1', [])
        print(f"✅ Retrieved {len(work_items_raw)} work item assignments from Logic App")
        logic_app_time = time.time() - phase_start

        if not work_items_raw:
            print("📭 No work items found for specified criteria")
            return self._empty_result()

        # Phase 3: Process and deduplicate
        phase_start = time.time()
        print(f"\n🔧 Phase 3: Processing work items...")

        work_items = self._process_logic_app_work_items(work_items_raw, from_date, to_date)
        print(f"✅ Processed {len(work_items)} unique work items")
        processing_time = time.time() - phase_start

        # Phase 4: Fetch activity logs and calculate efficiency
        if calculate_efficiency:
            phase_start = time.time()
            print(f"\n📊 Phase 4: Fetching activity logs and calculating efficiency...")

            self._fetch_activity_logs_and_calculate_efficiency(
                work_items,
                from_date,
                to_date,
                use_parallel_processing,
                max_workers
            )
            efficiency_time = time.time() - phase_start
        else:
            efficiency_time = 0
            print(f"\n⏭️  Phase 4: Skipped efficiency calculation (--no-efficiency)")

        # Phase 5: Calculate KPIs
        phase_start = time.time()
        print(f"\n📈 Phase 5: Calculating KPIs...")

        kpis = self.calculate_comprehensive_kpi_per_developer(work_items, {})
        kpi_time = time.time() - phase_start

        # Summary
        total_time = time.time() - overall_start_time
        print(f"\n✅ ========================================")
        print(f"✅ COMPLETE - Total time: {total_time:.2f}s")
        print(f"✅ ========================================")
        print(f"   Email resolution: {resolution_time:.2f}s")
        print(f"   Logic App fetch: {logic_app_time:.2f}s")
        print(f"   Processing: {processing_time:.2f}s")
        print(f"   Efficiency calc: {efficiency_time:.2f}s")
        print(f"   KPI calculation: {kpi_time:.2f}s")

        result = {
            "work_items": work_items,
            "kpis": kpis,
            "query_info": {
                "total_items": len(work_items),
                "source": "Logic App (Fabric Data Warehouse)",
                "filters_applied": {
                    "assigned_to": assigned_to or ["All users"],
                    "emails": emails,
                    "date_range": f"{from_date} to {to_date}"
                }
            }
        }

        # Export to CSV if requested
        if export_csv:
            base_filename = export_csv.replace('.csv', '')
            self.export_enhanced_work_items_to_csv(work_items, kpis, base_filename)

        return result

    def _process_logic_app_work_items(self, work_items_raw: List[Dict], from_date: str, to_date: str) -> List[Dict]:
        """
        Process raw work items from Logic App ResultSets.Table1.

        Deduplicates by (WorkItemId, AssignedToUser) and converts to standardized format.

        Expected fields from Logic App:
        - WorkItemId: Work item ID
        - AssignedToUser: Assigned user email
        - Title: Work item title
        - StartDate: Start date
        - TargetDate: Target date
        - OriginalEstimate: Estimated hours
        - Project_Name: Azure DevOps project name (REQUIRED for revision fetching)
        """
        seen_keys = set()
        work_items = []

        for item in work_items_raw:
            work_item_id = item.get('WorkItemId')
            assigned_to = item.get('AssignedToUser', '').strip()

            if not work_item_id or not assigned_to:
                continue

            # Deduplicate by (WorkItemId, AssignedToUser)
            key = (work_item_id, assigned_to)
            if key in seen_keys:
                continue
            seen_keys.add(key)

            # Extract project name from Logic App response (note: underscore in field name)
            project_name = item.get('Project_Name', '').strip()

            # Convert to standardized format
            work_item = {
                'id': work_item_id,
                'title': item.get('Title', ''),
                'assigned_to': assigned_to,
                'start_date': item.get('StartDate'),
                'target_date': item.get('TargetDate'),
                'original_estimate': item.get('OriginalEstimate'),
                'fabric_enriched': True,
                'revisions': [],
                'project_id': project_name if project_name else None,  # Use project name as identifier
                'project_name': project_name if project_name else None,
                'state': None,  # Will be determined from revisions or current state
                'work_item_type': None  # Will be determined from revisions
            }

            work_items.append(work_item)

        return work_items

    def _fetch_activity_logs_and_calculate_efficiency(self,
                                                       work_items: List[Dict],
                                                       from_date: str,
                                                       to_date: str,
                                                       use_parallel: bool,
                                                       max_workers: int):
        """
        Fetch Azure DevOps activity logs for work items and calculate efficiency.

        Uses existing revision fetching and efficiency calculation logic.
        Requires project_name to be populated in work items from Logic App.
        """
        # Get date boundaries in Mexico City timezone
        start_boundary, _ = get_date_boundaries_mexico_city(from_date)
        _, end_boundary = get_date_boundaries_mexico_city(to_date)

        print(f"   Fetching activity logs from {start_boundary} to {end_boundary} (America/Mexico_City)")

        # Check how many work items have project names
        items_with_project = sum(1 for item in work_items if item.get('project_id'))
        items_without_project = len(work_items) - items_with_project

        if items_without_project > 0:
            print(f"   ⚠️  Warning: {items_without_project} work items missing Project_Name")
            print(f"   These items will be skipped for efficiency calculations")
            print(f"   Please ensure Logic App returns 'Project_Name' field for all work items")

        if use_parallel and max_workers > 1:
            print(f"   Using parallel processing with {max_workers} workers...")
            work_items_with_revisions, _ = self.get_work_item_revisions_parallel(
                work_items,
                max_workers=max_workers,
                batch_size=50
            )
        else:
            print(f"   Using sequential processing...")
            for item in work_items:
                try:
                    # Fetch revisions using project_name from Logic App
                    if item.get('project_id') and item.get('project_name'):
                        state_history = self.get_work_item_revisions(
                            item['project_id'],  # This is the project name from Logic App
                            item['id'],
                            item['project_name']
                        )
                        item['revisions'] = state_history
                    else:
                        self.logger.warning(f"Skipping item {item['id']}: missing project name")
                        item['revisions'] = []
                except Exception as e:
                    self.logger.error(f"Failed to get revisions for item {item['id']}: {e}")
                    item['revisions'] = []

        # Update state and work_item_type from revisions
        for item in work_items:
            revisions = item.get('revisions', [])
            if revisions:
                # Get the latest state and work_item_type from most recent revision
                latest_revision = revisions[-1]
                if not item.get('state'):
                    item['state'] = latest_revision.get('state', 'Unknown')
                if not item.get('work_item_type'):
                    item['work_item_type'] = latest_revision.get('work_item_type', 'Unknown')

        # Calculate efficiency for each work item
        state_config = self.config_loader.get_state_categories()

        for item in work_items:
            try:
                if not self.config_loader.should_include_work_item_with_history(item, item.get("revisions", [])):
                    continue

                efficiency = self.calculate_fair_efficiency_metrics(
                    item,
                    item.get("revisions", []),
                    state_config,
                    from_date,
                    to_date
                )
                item["efficiency"] = efficiency
            except Exception as e:
                self.logger.error(f"Error calculating efficiency for item {item['id']}: {e}")
                item["efficiency"] = {}

    def _get_work_item_details_simple(self, work_item_id: int) -> Dict:
        """
        Get basic work item details to determine project and current state.
        """
        try:
            endpoint = f"_apis/wit/workitems/{work_item_id}?api-version=7.1-preview.3"
            response = self.handle_request("GET", endpoint)

            fields = response.get('fields', {})
            return {
                'project_id': fields.get('System.TeamProject'),  # Project name, not ID
                'project_name': fields.get('System.TeamProject'),
                'state': fields.get('System.State'),
                'work_item_type': fields.get('System.WorkItemType')
            }
        except Exception as e:
            self.logger.error(f"Failed to get details for work item {work_item_id}: {e}")
            return {}

    def _empty_result(self) -> Dict:
        """Return empty result structure."""
        return {
            "work_items": [],
            "kpis": {},
            "query_info": {
                "total_items": 0,
                "source": "Logic App (Fabric Data Warehouse)",
                "filters_applied": {}
            }
        }

    def get_daily_snapshot_from_logic_app(self,
                                          from_date: str,
                                          to_date: str,
                                          assigned_to: Optional[List[str]] = None,
                                          use_parallel_processing: bool = True,
                                          max_workers: int = 10,
                                          output_filename: str = "daily_snapshot.csv") -> Dict:
        """
        Generate simplified daily snapshot from Logic App with basic time tracking.

        This method is optimized for automated tracking workflows:
        - Skips complex efficiency calculations and KPI aggregation
        - Only calculates active and blocked time
        - Exports directly to simplified 12-column CSV
        - 40-60% faster than full query method

        Args:
            from_date: Start date in YYYY-MM-DD format
            to_date: End date in YYYY-MM-DD format
            assigned_to: List of user names or emails (None = all users from mapping)
            use_parallel_processing: Enable parallel revision fetching (default: True)
            max_workers: Number of parallel workers (default: 10)
            output_filename: Output CSV filename

        Returns:
            Dictionary with total_items count and output_filename
        """
        overall_start_time = time.time()

        print("🚀 Fetching work items from Logic App...")

        # Validate Logic App client
        if not self.logic_app_client:
            raise EnvironmentError(
                "Logic App client not initialized. Please set AZURE_LOGIC_APP_URL in .env file."
            )

        # Phase 1: Resolve emails
        print(f"\n📧 Resolving emails...")
        emails = resolve_emails(assigned_to)
        if not emails:
            print("❌ No valid emails resolved. Please check user_email_mapping.json")
            return {"total_items": 0, "output_filename": output_filename}

        print(f"✅ Resolved {len(emails)} email(s): {', '.join(emails)}")

        # Phase 2: Fetch from Logic App
        print(f"\n🔄 Fetching from Logic App (date range: {from_date} to {to_date})...")
        try:
            logic_app_response = self.logic_app_client.get_work_items_by_date_range(
                from_date=from_date,
                to_date=to_date,
                emails=emails
            )
        except Exception as e:
            print(f"❌ Failed to fetch from Logic App: {e}")
            raise

        # Parse response
        work_items_raw = logic_app_response.get('ResultSets', {}).get('Table1', [])
        print(f"✅ Retrieved {len(work_items_raw)} work item assignments")

        if not work_items_raw:
            print("📭 No work items found for specified criteria")
            return {"total_items": 0, "output_filename": output_filename}

        # Phase 3: Process and deduplicate
        print(f"\n🔧 Processing work items...")
        work_items = self._process_logic_app_work_items(work_items_raw, from_date, to_date)
        print(f"✅ Processed {len(work_items)} unique work items")

        # Phase 4: Fetch activity logs and calculate basic times
        print(f"\n📊 Fetching activity logs and calculating basic times...")
        self._fetch_activity_logs_basic_times(
            work_items,
            from_date,
            to_date,
            use_parallel_processing,
            max_workers
        )

        # Phase 5: Export to CSV
        print(f"\n💾 Exporting to CSV...")
        self.export_simplified_snapshot_csv(work_items, output_filename)

        total_time = time.time() - overall_start_time
        print(f"\n✅ Snapshot complete in {total_time:.2f}s")

        return {
            "total_items": len(work_items),
            "output_filename": output_filename
        }

    def _fetch_activity_logs_basic_times(self,
                                          work_items: List[Dict],
                                          from_date: str,
                                          to_date: str,
                                          use_parallel: bool,
                                          max_workers: int):
        """
        Fetch Azure DevOps activity logs and calculate ONLY basic time metrics.

        This method skips all complex scoring algorithms and only extracts:
        - Active time hours
        - Blocked time hours

        Performance: 50-60% faster than full efficiency calculation.
        """
        from helpers.timezone_utils import get_date_boundaries_mexico_city

        # Get date boundaries in Mexico City timezone
        start_boundary, _ = get_date_boundaries_mexico_city(from_date)
        _, end_boundary = get_date_boundaries_mexico_city(to_date)

        print(f"   Fetching activity logs from {start_boundary} to {end_boundary}")

        # Check project names
        items_with_project = sum(1 for item in work_items if item.get('project_id'))
        items_without_project = len(work_items) - items_with_project

        if items_without_project > 0:
            print(f"   ⚠️  Warning: {items_without_project} work items missing Project_Name")
            print(f"   These items will have 0 hours for time tracking")

        # Fetch revisions
        if use_parallel and max_workers > 1:
            print(f"   Using parallel processing with {max_workers} workers...")
            work_items_with_revisions, _ = self.get_work_item_revisions_parallel(
                work_items,
                max_workers=max_workers,
                batch_size=50
            )
        else:
            print(f"   Using sequential processing...")
            for item in work_items:
                try:
                    if item.get('project_id') and item.get('project_name'):
                        state_history = self.get_work_item_revisions(
                            item['project_id'],
                            item['id'],
                            item['project_name']
                        )
                        item['revisions'] = state_history
                    else:
                        self.logger.warning(f"Skipping item {item['id']}: missing project name")
                        item['revisions'] = []
                except Exception as e:
                    self.logger.error(f"Failed to get revisions for item {item['id']}: {e}")
                    item['revisions'] = []

        # Update state and work_item_type from revisions
        for item in work_items:
            revisions = item.get('revisions', [])
            if revisions:
                latest_revision = revisions[-1]
                if not item.get('state'):
                    item['state'] = latest_revision.get('state', 'Unknown')
                if not item.get('work_item_type'):
                    item['work_item_type'] = latest_revision.get('work_item_type', 'Unknown')

        # Calculate basic times (extract only time fields from efficiency calculator)
        state_config = self.config_loader.get_state_categories()

        for item in work_items:
            try:
                if not self.config_loader.should_include_work_item_with_history(item, item.get("revisions", [])):
                    item["basic_times"] = {"active_time_hours": 0, "blocked_time_hours": 0}
                    continue

                # Call efficiency calculator but extract only time fields
                efficiency = self.calculate_fair_efficiency_metrics(
                    item,
                    item.get("revisions", []),
                    state_config,
                    from_date,
                    to_date
                )

                # Extract only the time fields we need
                item["basic_times"] = {
                    "active_time_hours": efficiency.get("active_time_hours", 0),
                    "blocked_time_hours": efficiency.get("blocked_time_hours", 0)
                }
            except Exception as e:
                self.logger.error(f"Error calculating times for item {item['id']}: {e}")
                item["basic_times"] = {"active_time_hours": 0, "blocked_time_hours": 0}

    def export_simplified_snapshot_csv(self, work_items: List[Dict], filename: str):
        """
        Export work items to simplified 12-column CSV format for automated tracking.

        CSV Structure (12 columns):
        - ID, Title, Project Name, Assigned To, State, Work Item Type
        - Start Date, Target Date, Closed Date
        - Estimated Hours, Active Time (Hours), Blocked Time (Hours)

        This is a simplified version of the full export (20 columns → 12 columns).
        """
        if not work_items:
            print("   ⚠️  No work items to export")
            return

        try:
            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = [
                    'ID', 'Title', 'Project Name', 'Assigned To', 'State', 'Work Item Type',
                    'Start Date', 'Target Date', 'Closed Date', 'Estimated Hours',
                    'Active Time (Hours)', 'Blocked Time (Hours)'
                ]
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()

                for item in work_items:
                    basic_times = item.get("basic_times", {})
                    writer.writerow({
                        'ID': item['id'],
                        'Title': item.get('title', ''),
                        'Project Name': item.get('project_name', ''),
                        'Assigned To': item.get('assigned_to', ''),
                        'State': item.get('state', ''),
                        'Work Item Type': item.get('work_item_type', ''),
                        'Start Date': item.get('start_date', ''),
                        'Target Date': item.get('target_date', ''),
                        'Closed Date': item.get('closed_date', ''),
                        'Estimated Hours': item.get('original_estimate', 0) or 0,
                        'Active Time (Hours)': basic_times.get('active_time_hours', 0),
                        'Blocked Time (Hours)': basic_times.get('blocked_time_hours', 0)
                    })

            print(f"   ✅ Exported {len(work_items)} items to {filename}")

        except IOError as e:
            print(f"   ❌ Failed to write CSV file: {e}")
            print("   Check file path and permissions")
            raise
        except Exception as e:
            print(f"   ❌ Unexpected error during CSV export: {e}")
            raise

    def get_work_items_with_efficiency_optimized(self,
                                     project_id: Optional[str] = None,
                                     project_names: Optional[List[str]] = None,
                                     assigned_to: Optional[List[str]] = None,
                                     work_item_types: Optional[List[str]] = None,
                                     states: Optional[List[str]] = None,
                                     start_date: Optional[str] = None,
                                     end_date: Optional[str] = None,
                                     date_field: str = "ClosedDate",
                                     additional_filters: Optional[Dict[str, str]] = None,
                                     calculate_efficiency: bool = True,
                                     productive_states: Optional[List[str]] = None,
                                     blocked_states: Optional[List[str]] = None,
                                     all_projects: bool = False,
                                     max_projects: int = None,
                                     refresh_projects_cache: bool = False,
                                     use_parallel_processing: bool = True,
                                     max_workers: int = 10,
                                     batch_size: int = 200,
                                     ultra_mode: bool = False) -> Dict:
        """
        🚀 OPTIMIZED method to get work items with efficiency calculations using batch processing and parallel execution.
        
        Performance improvements:
        - Enhanced WIQL queries with $expand parameter
        - Batch processing for work item details (200 items per call)
        - Parallel revision fetching with connection pooling
        - Ultra mode: bypasses project discovery completely
        - Comprehensive performance metrics and monitoring
        
        Args:
            project_id: Single project ID to query (optional)
            project_names: List of project names to filter by (optional)
            assigned_to: List of users to filter by
            work_item_types: List of work item types
            states: List of states to filter by
            start_date: Start date for filtering
            end_date: End date for filtering
            date_field: Field to use for date filtering
            additional_filters: Additional filters (optional)
            calculate_efficiency: Whether to calculate efficiency metrics
            productive_states: States considered productive (optional)
            blocked_states: States considered blocked (optional)
            all_projects: Query all projects flag
            max_projects: Maximum projects to query
            refresh_projects_cache: Refresh project cache
            use_parallel_processing: Enable parallel revision fetching
            max_workers: Number of parallel workers for revision fetching
            batch_size: Batch size for work item details fetching
            ultra_mode: Enable ultra-optimized mode (bypasses project discovery)
            
        Returns:
            Dictionary with work items, KPIs, and comprehensive performance metrics
        """
        overall_start_time = time.time()
        
        # Initialize comprehensive performance tracking
        performance_summary = {
            "total_execution_time": 0,
            "optimization_strategies_used": ["ultra_optimized" if ultra_mode else "optimized"],
            "api_call_breakdown": {
                "wiql_calls": 0,
                "work_item_detail_calls": 0,
                "revision_calls": 0,
                "total_api_calls": 0
            },
            "performance_gains": {
                "estimated_original_calls": 0,
                "actual_calls": 0,
                "call_reduction_percentage": 0
            },
            "processing_phases": {}
        }
        
        if ultra_mode:
            print("🚀 ========================================")
            print("🚀 ULTRA-OPTIMIZED WORK ITEM FETCHING")
            print("🚀 ========================================")
            print("⚡ Bypassing project discovery for maximum speed!")
        else:
            print("🚀 ========================================")
            print("🚀 OPTIMIZED WORK ITEM FETCHING STARTED")
            print("🚀 ========================================")
        
        # Phase 1: Setup and project discovery (or skip for ultra mode)
        phase_start = time.time()
        
        # Default values with priority: parameters → config → fallback
        if work_item_types is None:
            # Try to get work_item_types from config file
            config_work_item_types = self.config_loader.get_work_item_types()
            if config_work_item_types:
                work_item_types = config_work_item_types
            else:
                # Fallback to hardcoded default
                work_item_types = ["Task", "User Story", "Bug"]
        if states is None:
            # Try to get states from config file
            config_states = self.config_loader.get_states_to_fetch()
            if config_states:
                states = config_states
            else:
                # Fallback to hardcoded default
                states = ["Closed", "Done", "Resolved", "Active", "New", "To Do", "In Progress"]
            
        if start_date is None and end_date is None and date_field == "ClosedDate":
            end_date = datetime.now().strftime("%Y-%m-%d")
            start_date = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
            print(f"📅 Auto-set date range: {start_date} to {end_date}")
        
        # Project discovery logic - skip for ultra mode
        if ultra_mode:
            print("⚡ Skipping project discovery - using direct organization query")
            target_projects = None  # Will be used to signal direct org query
            performance_summary["optimization_strategies_used"].append("skip_project_discovery")
        else:
            # Normal project discovery logic
            if project_id:
                target_projects = [{'id': project_id, 'name': f'Project {project_id}'}]
            else:
                if project_names:
                    all_projects_list = self.get_all_projects()
                    target_projects = self.filter_projects_by_name(all_projects_list, project_names)
                elif assigned_to and not all_projects:
                    print("🔍 Using smart project discovery...")
                    target_projects = self.find_projects_with_user_activity(
                        assigned_to=assigned_to, work_item_types=work_item_types,
                        states=states, start_date=start_date, end_date=end_date,
                        date_field=date_field, max_projects=max_projects
                    )
                else:
                    print("⚠️ WARNING: Querying all projects without user filtering may be slow")
                    target_projects = self.get_all_projects()
            
            if not target_projects and not ultra_mode:
                print("❌ No projects found to query.")
                return self._empty_result_with_performance(performance_summary)
        
        performance_summary["processing_phases"]["project_discovery"] = time.time() - phase_start
        
        # Phase 2: Enhanced WIQL Query
        phase_start = time.time()
        query = self.build_wiql_query(
            assigned_to=assigned_to, work_item_types=work_item_types,
            states=states, start_date=start_date, end_date=end_date,
            date_field=date_field, additional_filters=additional_filters
        )
        
        print(f"📋 Generated WIQL Query:\n{query}\n")
        
        # Try organization-level optimized query first
        try:
            print("🌐 Attempting organization-level optimized WIQL query...")
            
            # In ultra mode, we need project mapping for organization-level queries
            projects_for_mapping = target_projects
            if ultra_mode and not target_projects:
                print("⚡ Ultra mode: Getting all projects for ID mapping...")
                projects_for_mapping = self.get_all_projects()
            
            all_work_items = self._execute_organization_wiql_optimized(
                query, projects_for_mapping, project_names, performance_summary
            )
            performance_summary["optimization_strategies_used"].append("organization_level_wiql")
            
        except Exception as e:
            print(f"⚠️ Organization-level query failed: {e}")
            print("🔄 Falling back to project-by-project optimized approach...")
            all_work_items = self._execute_project_by_project_optimized(
                query, target_projects, performance_summary, batch_size
            )
            performance_summary["optimization_strategies_used"].append("project_by_project_optimized")
        
        performance_summary["processing_phases"]["wiql_execution"] = time.time() - phase_start
        
        if not all_work_items:
            print("📭 No work items found matching criteria.")
            return self._empty_result_with_performance(performance_summary)
        
        print(f"✅ Found {len(all_work_items)} work items total")
        
        # Phase 3: Parallel Revision Fetching
        if calculate_efficiency and use_parallel_processing:
            phase_start = time.time()
            print(f"\n⚡ Phase 3: Parallel revision fetching for {len(all_work_items)} items...")
            
            all_work_items, revision_metrics = self.get_work_item_revisions_parallel(
                all_work_items, max_workers=max_workers, batch_size=50
            )
            
            performance_summary["api_call_breakdown"]["revision_calls"] = revision_metrics["revision_calls"]
            performance_summary["optimization_strategies_used"].append("parallel_revision_fetching")
            performance_summary["processing_phases"]["revision_fetching"] = time.time() - phase_start
            
        elif calculate_efficiency:
            # Fallback to sequential revision fetching
            phase_start = time.time()
            print(f"\n🔄 Phase 3: Sequential revision fetching for {len(all_work_items)} items...")
            
            for item in all_work_items:
                try:
                    state_history = self.get_work_item_revisions(
                        item['project_id'], item["id"], item['project_name']
                    )
                    item["revisions"] = state_history
                    performance_summary["api_call_breakdown"]["revision_calls"] += 1
                except Exception as e:
                    print(f"❌ Failed to get revisions for item {item['id']}: {e}")
                    item["revisions"] = []
            
            performance_summary["optimization_strategies_used"].append("sequential_revision_fetching")
            performance_summary["processing_phases"]["revision_fetching"] = time.time() - phase_start
        
        # Phase 3.5: Enrich with Fabric Logic App estimated hours
        if calculate_efficiency:
            phase_start = time.time()
            print(f"\n📊 Phase 3.5: Enriching with estimated hours from Fabric...")
            self._enrich_work_items_with_fabric_estimates(all_work_items)
            performance_summary["processing_phases"]["fabric_enrichment"] = time.time() - phase_start
            performance_summary["optimization_strategies_used"].append("fabric_estimated_hours")

        # Phase 4: Efficiency Calculation
        if calculate_efficiency:
            phase_start = time.time()
            print(f"\n🧮 Phase 4: Calculating efficiency metrics...")

            state_config = self.config_loader.get_state_categories()

            for item in all_work_items:
                try:
                    if not self.config_loader.should_include_work_item_with_history(item, item.get("revisions", [])):
                        continue
                        
                    efficiency = self.calculate_fair_efficiency_metrics(
                        item, item.get("revisions", []), state_config, start_date, end_date
                    )
                    item["efficiency"] = efficiency
                    
                except Exception as e:
                    print(f"❌ Error calculating efficiency for item {item['id']}: {e}")
                    item["efficiency"] = {}
            
            performance_summary["processing_phases"]["efficiency_calculation"] = time.time() - phase_start
        
        # Phase 5: KPI Calculation (optimized for ultra mode)
        phase_start = time.time()
        print(f"\n📊 Phase 5: Calculating KPIs...")
        
        # Get total assigned items count if needed (skip for ultra mode to save time)
        assigned_counts = {}
        if assigned_to and not ultra_mode:
            print("    📊 Getting total assigned items count per developer...")
            assigned_counts = self._get_total_assigned_items_by_developer(
                target_projects, assigned_to, work_item_types, start_date, end_date
            )
        elif ultra_mode:
            print("    ⚡ Skipping expensive total assigned items calculation for speed")
        
        kpis = self.calculate_comprehensive_kpi_per_developer(all_work_items, assigned_counts)
        performance_summary["processing_phases"]["kpi_calculation"] = time.time() - phase_start
        
        # Finalize performance metrics
        performance_summary["total_execution_time"] = time.time() - overall_start_time
        
        # Calculate performance gains
        estimated_original_calls = 1 + len(all_work_items) * 2  # 1 WIQL + N details + N revisions
        actual_calls = performance_summary["api_call_breakdown"]["total_api_calls"]
        performance_summary["performance_gains"]["estimated_original_calls"] = estimated_original_calls
        performance_summary["performance_gains"]["actual_calls"] = actual_calls
        performance_summary["performance_gains"]["call_reduction_percentage"] = (
            ((estimated_original_calls - actual_calls) / estimated_original_calls) * 100
            if estimated_original_calls > 0 else 0
        )
        
        self._print_performance_summary(performance_summary)
        
        return {
            "work_items": all_work_items,
            "kpis": kpis,
            "query_info": {
                "total_items": len(all_work_items),
                "projects_queried": [p.get('name', 'Unknown') for p in (target_projects or [])] if not ultra_mode else ["All projects (ultra mode)"],
                "filters_applied": {
                    "assigned_to": assigned_to,
                    "work_item_types": work_item_types,
                    "states": states,
                    "date_range": f"{start_date or 'Any'} to {end_date or 'Any'}",
                    "date_field": date_field
                }
            },
            "performance_summary": performance_summary
        }
    
    def _execute_organization_wiql_optimized(self, query: str, target_projects: List[Dict], 
                                           project_names: Optional[List[str]], 
                                           performance_summary: Dict) -> List[Dict]:
        """Execute organization-level WIQL with optimizations."""
        work_items_with_projects = self.execute_organization_wiql_query(
            query=query,
            target_projects=target_projects if not project_names else None,
            project_names=project_names
        )
        
        performance_summary["api_call_breakdown"]["wiql_calls"] += 1
        performance_summary["api_call_breakdown"]["total_api_calls"] += 1
        
        if work_items_with_projects:
            # Filter out items with unknown project IDs
            filtered_items = [
                item for item in work_items_with_projects
                if item.get('project_id', None) not in (None, '', 'Unknown')
            ]
            
            if len(filtered_items) < len(work_items_with_projects):
                skipped = len(work_items_with_projects) - len(filtered_items)
                print(f"⚠️ Skipped {skipped} items with unknown project IDs")
            
            return filtered_items
        
        return []
    
    def _execute_project_by_project_optimized(self, query: str, target_projects: List[Dict], 
                                            performance_summary: Dict, batch_size: int) -> List[Dict]:
        """Execute project-by-project queries with batch optimization."""
        all_work_items = []
        
        for project in target_projects:
            proj_id = project['id']
            proj_name = project['name']
            
            if not proj_id or proj_id == "Unknown":
                print(f"⚠️ Skipping project with unknown ID: {proj_name}")
                continue
                
            try:
                print(f"🔍 Querying project: {proj_name} ({proj_id})")
                
                # Use optimized WIQL query
                work_item_ids, wiql_metrics = self.execute_optimized_wiql_query(
                    proj_id, query, include_revisions=False
                )
                
                performance_summary["api_call_breakdown"]["wiql_calls"] += wiql_metrics["wiql_calls"]
                performance_summary["api_call_breakdown"]["total_api_calls"] += wiql_metrics["total_api_calls"]
                
                if work_item_ids:
                    # Use batch processing for work item details
                    work_items, detail_metrics = self.get_work_item_details_batch(
                        proj_id, work_item_ids, proj_name, batch_size
                    )
                    
                    performance_summary["api_call_breakdown"]["work_item_detail_calls"] += detail_metrics["batch_calls"]
                    performance_summary["api_call_breakdown"]["total_api_calls"] += detail_metrics["batch_calls"]
                    
                    # Add project info to items
                    for item in work_items:
                        item['project_id'] = proj_id
                        item['project_name'] = proj_name
                    
                    all_work_items.extend(work_items)
                    print(f"✅ Found {len(work_items)} items in {proj_name}")
                else:
                    print(f"📭 No work items found in {proj_name}")
                    
            except Exception as e:
                print(f"❌ Error querying project {proj_name}: {e}")
                continue
        
        return all_work_items
    
    def _empty_result_with_performance(self, performance_summary: Dict) -> Dict:
        """Return empty result with performance metrics."""
        performance_summary["total_execution_time"] = 0
        
        return {
            "work_items": [],
            "kpis": self.calculate_comprehensive_kpi_per_developer([]),
            "query_info": {
                "total_items": 0,
                "projects_queried": [],
                "filters_applied": {}
            },
            "performance_summary": performance_summary
        }
    
    def _print_performance_summary(self, performance_summary: Dict):
        """Print comprehensive performance summary."""
        print(f"\n🚀 ========================================")
        print(f"🚀 PERFORMANCE SUMMARY")
        print(f"🚀 ========================================")
        
        print(f"⏱️  Total Execution Time: {performance_summary['total_execution_time']:.2f}s")
        print(f"🎯 Optimization Strategies: {', '.join(performance_summary['optimization_strategies_used'])}")
        
        print(f"\n📞 API Call Breakdown:")
        breakdown = performance_summary["api_call_breakdown"]
        print(f"   • WIQL calls: {breakdown['wiql_calls']}")
        print(f"   • Work item detail calls: {breakdown['work_item_detail_calls']}")
        print(f"   • Revision calls: {breakdown['revision_calls']}")
        print(f"   • Total API calls: {breakdown['total_api_calls']}")
        
        gains = performance_summary["performance_gains"]
        print(f"\n📈 Performance Gains:")
        print(f"   • Estimated original calls: {gains['estimated_original_calls']}")
        print(f"   • Actual calls made: {gains['actual_calls']}")
        print(f"   • Call reduction: {gains['call_reduction_percentage']:.1f}%")
        
        print(f"\n⏳ Phase Timing:")
        for phase, duration in performance_summary["processing_phases"].items():
            print(f"   • {phase.replace('_', ' ').title()}: {duration:.2f}s")
        
        print(f"🚀 ========================================\n")
    
    def export_enhanced_work_items_to_csv(self, 
                                        work_items: List[Dict],
                                        kpis: Dict,
                                        base_filename: str = "work_items_export") -> None:
        """
        Export enhanced work items data and per-developer metrics to CSV files.
        
        Args:
            work_items: List of work items with enhanced efficiency data
            kpis: KPI data with per-developer metrics
            base_filename: Base filename for exports (without extension)
        """
        if not work_items:
            print("No work items to export.")
            return
        
        try:
            # Export detailed work items
            items_filename = f"{base_filename}_detailed.csv"
            with open(items_filename, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = [
                    'ID', 'Title', 'Project Name', 'Assigned To', 'State', 'Work Item Type',
                    'Start Date', 'Target Date', 'Closed Date', 'Estimated Hours',
                    'Active Time (Hours)', 'Blocked Time (Hours)', 'Efficiency %',
                    'Delivery Score', 'Days Ahead/Behind Target',
                    'Completion Bonus', 'Timing Bonus', 'Was Reopened', 'Active After Reopen'
                ]
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()

                for item in work_items:
                    efficiency = item.get("efficiency", {})
                    writer.writerow({
                        'ID': item['id'],
                        'Title': item['title'],
                        'Project Name': item.get('project_name', ''),
                        'Assigned To': item['assigned_to'],
                        'State': item['state'],
                        'Work Item Type': item['work_item_type'],
                        'Start Date': item.get('start_date', ''),
                        'Target Date': item.get('target_date', ''),
                        'Closed Date': item.get('closed_date', ''),
                        'Estimated Hours': efficiency.get('estimated_time_hours', 0),
                        'Active Time (Hours)': efficiency.get('active_time_hours', 0),
                        'Blocked Time (Hours)': efficiency.get('blocked_time_hours', 0),
                        'Efficiency %': efficiency.get('efficiency_percentage', 0),
                        'Delivery Score': efficiency.get('delivery_score', 0),
                        'Days Ahead/Behind Target': efficiency.get('days_ahead_behind', 0),
                        'Completion Bonus': efficiency.get('completion_bonus', 0),
                        'Timing Bonus': efficiency.get('delivery_timing_bonus', 0),
                        'Was Reopened': efficiency.get('was_reopened', False),
                        'Active After Reopen': efficiency.get('active_after_reopen', 0)
                    })
            
            print(f"Successfully exported {len(work_items)} detailed work items to {items_filename}")
            
            # Export developer summary
            summary_filename = f"{base_filename}_developer_summary.csv"
            developer_metrics = kpis.get('developer_metrics', {})
            
            if developer_metrics:
                with open(summary_filename, 'w', newline='', encoding='utf-8') as csvfile:
                    fieldnames = [
                        'Developer', 'Total Work Items', 'Completed Items', 'Items With Active Time',
                        'Sample Confidence %', 'Completion Rate %', 'On-Time Delivery %',
                        'Average Efficiency %', 'Average Delivery Score', 'Overall Developer Score',
                        'Total Active Hours', 'Total Estimated Hours', 'Avg Days Ahead/Behind',
                        'Reopened Items Handled', 'Reopened Rate %', 'Work Item Types', 'Projects Count',
                        'Early Deliveries', 'On-Time Deliveries', 'Late 1-3 Days', 'Late 4-7 Days',
                        'Late 8-14 Days', 'Late 15+ Days'
                    ]
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    writer.writeheader()

                    for developer, metrics in developer_metrics.items():
                        timing = metrics.get('delivery_timing_breakdown', {})
                        writer.writerow({
                            'Developer': developer,
                            'Total Work Items': metrics.get('total_work_items', 0),
                            'Completed Items': metrics.get('completed_items', 0),
                            'Items With Active Time': metrics.get('items_with_efficiency', 0),
                            'Sample Confidence %': metrics.get('sample_confidence', 0),
                            'Completion Rate %': metrics.get('completion_rate', 0),
                            'On-Time Delivery %': metrics.get('on_time_delivery_percentage', 0),
                            'Average Efficiency %': metrics.get('average_fair_efficiency', 0),
                            'Average Delivery Score': metrics.get('average_delivery_score', 0),
                            'Overall Developer Score': metrics.get('overall_developer_score', 0),
                            'Total Active Hours': metrics.get('total_active_hours', 0),
                            'Total Estimated Hours': metrics.get('total_estimated_hours', 0),
                            'Avg Days Ahead/Behind': metrics.get('average_days_ahead_behind', 0),
                            'Reopened Items Handled': metrics.get('reopened_items_handled', 0),
                            'Reopened Rate %': metrics.get('reopened_rate', 0),
                            'Work Item Types': len(metrics.get('work_item_types', [])),
                            'Projects Count': metrics.get('projects_count', 0),
                            'Early Deliveries': timing.get('early', 0),
                            'On-Time Deliveries': timing.get('on_time', 0),
                            'Late 1-3 Days': timing.get('late_1_3', 0),
                            'Late 4-7 Days': timing.get('late_4_7', 0),
                            'Late 8-14 Days': timing.get('late_8_14', 0),
                            'Late 15+ Days': timing.get('late_15_plus', 0)
                        })
                
                print(f"Successfully exported developer summary to {summary_filename}")
            
        except IOError as e:
            print(f"Error writing to CSV files: {e}")
        except Exception as e:
            print(f"An unexpected error occurred during CSV export: {e}")