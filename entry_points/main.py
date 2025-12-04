import argparse
import sys
import os
from pathlib import Path

# Add the parent directory to Python path to access classes and config
sys.path.append(str(Path(__file__).parent.parent))

from classes.commands import AzureDevOpsCommands
from classes.AzureDevopsProjectOperations import AzureDevOpsProjectOperations
from classes.WorkItemOperations import WorkItemOperations
from config.config import Config
from dotenv import load_dotenv
import json

load_dotenv(".env")

def explain_commands():
    """
    Explains all available commands and their arguments.
    """
    explanation = """
Azure DevOps CLI Utility Inbest:

Commands:
  --list-projects
      Lists all projects in the specified Azure DevOps organization.
      Example:
        python main.py --list-projects

  --filter-tag
      Filter projects by tags in their descriptions.
      Example:
        python main.py --list-projects --filter-tag "Software Factory" "Production"

  --create-hook
      Creates a service hook for a specific project.
      Required arguments:
        --project-id : The ID of the project to create the service hook for.
        --event-type : The event type that triggers the hook (e.g., 'workitem.updated').
      Optional arguments:
        --hook-url   : The webhook URL (defaults to configured URL for event type).
        --state-changed : Only trigger on state changes for workitem.updated.
      Example:
        python main.py --create-hook --project-id <project_id> --event-type workitem.updated

  --remove-hook
      Removes service hook subscriptions.
      Required arguments:
        --project-id : The ID of the project containing the hook.
      Optional arguments:
        --subscription-id : The ID of the specific subscription to remove (removes all if not specified).
      Example:
        python main.py --remove-hook --project-id <project_id> --subscription-id <subscription_id>

  --list-subscriptions
      Lists service hook subscriptions for a project.
      Required arguments:
        --project-id : The ID of the project to list subscriptions for.
      Example:
        python main.py --list-subscriptions --project-id <project_id>

  --create-hooks-for-filtered-projects
      Creates service hooks for projects matching specified tags.
      Required arguments:
        --filter-tag : List of tags to filter projects by.
        --event-type : The event type for the service hook.
      Optional arguments:
        --hook-url : The webhook URL (defaults to configured URL for event type).
        --state-changed : Only trigger on state changes for workitem.updated.
      Example:
        python main.py --create-hooks-for-filtered-projects --filter-tag "Production" --event-type workitem.updated

  --list-and-upgrade-webhooks
      Lists projects by tag and upgrades their webhooks.
      Required arguments:
        --filter-tag : List of tags to filter projects by.
      Example:
        python main.py --list-and-upgrade-webhooks --filter-tag "Production"

  --query-work-items
      Query work items from Logic App (Fabric Data Warehouse) with KPI calculations.

      IMPORTANT: This command now uses Logic App as the default and only source.
      Legacy WIQL/Analytics methods have been removed.

      Required arguments:
        --start-date : Start date in YYYY-MM-DD format (required)
        --end-date : End date in YYYY-MM-DD format (required)

      Optional arguments:
        --assigned-to : Comma-separated list of user names or emails.
                       If omitted, queries all users from user_email_mapping.json.
                       Supports both names ("Carlos Vazquez") and emails ("carlos.vazquez@inbest.cloud").
        --no-efficiency : Skip efficiency calculations for faster results.
        --export-csv : Export results to CSV file (detailed and summary).
        --no-parallel : Disable parallel revision fetching (use sequential).
        --max-workers : Number of parallel workers (default: 10).

      Examples:
        # Query all users for October 2025
        python main.py --query-work-items --start-date 2025-10-01 --end-date 2025-10-31 --export-csv reports/october.csv

        # Query specific users
        python main.py --query-work-items --start-date 2025-10-01 --end-date 2025-10-31 --assigned-to "Carlos Vazquez,Diego Lopez"

        # Query using emails directly
        python main.py --query-work-items --start-date 2025-10-01 --end-date 2025-10-31 --assigned-to "carlos.vazquez@inbest.cloud"

        # Query without efficiency calculations (faster)
        python main.py --query-work-items --start-date 2025-10-01 --end-date 2025-10-31 --no-efficiency

  --daily-snapshot
      Generate simplified daily work item snapshot for automated tracking.

      This command creates lightweight CSV reports optimized for GitHub Actions → Logic App → SharePoint workflows.
      Generates a 12-column CSV with basic time tracking (active/blocked hours) WITHOUT complex efficiency calculations.

      Performance: 40-60% faster than --query-work-items due to simplified processing.

      Optional arguments:
        --snapshot-mode : Date range mode (default: yesterday)
                         - yesterday : Previous day only (default)
                         - today : Current day up to now
                         - month-to-date : From first day of month until today
                         - custom : User-defined range (requires --start-date and --end-date)
        --output-filename : Override default filename for automation workflows.
                           Default: daily_snapshot_YYYYMMDD_HHMM.csv (timestamped)
                           Fixed name example: --output-filename daily_snapshot.csv
                           Use fixed filename when Logic App should process the same file daily.
        --assigned-to : Comma-separated list of user names or emails (omit for all users).
        --start-date : Start date for custom mode (YYYY-MM-DD format).
        --end-date : End date for custom mode (YYYY-MM-DD format).
        --no-parallel : Disable parallel processing (use sequential).
        --max-workers : Number of parallel workers (default: 10).

      Output CSV columns (12 total):
        ID, Title, Project Name, Assigned To, State, Work Item Type,
        Start Date, Target Date, Closed Date, Estimated Hours,
        Active Time (Hours), Blocked Time (Hours)

      IMPORTANT: Active Time and Blocked Time show TOTAL ACCUMULATED hours from the entire
      work item history, NOT filtered to the date range. This means:
        - A work item active from Nov 15 → Dec 10 will show ~17 days in both November
          and December reports (running total)
        - Each daily run shows updated accumulated time as work progresses
        - Date range only filters WHICH work items to include, not the time calculation

      Examples:
        # Yesterday's snapshot (default mode) - all users
        python main.py --daily-snapshot

        # Fixed filename for automation (overwrites same file daily)
        python main.py --daily-snapshot --output-filename daily_snapshot.csv

        # Fixed filename with specific date range
        python main.py --daily-snapshot --snapshot-mode custom --start-date 2025-11-01 --end-date 2025-11-10 --output-filename monthly_snapshot.csv

        # Today's snapshot for specific users
        python main.py --daily-snapshot --snapshot-mode today --assigned-to "Carlos Vazquez,Diego Lopez"

        # Month-to-date snapshot (auto-generates monthly filename)
        python main.py --daily-snapshot --snapshot-mode month-to-date
        # Output: daily_snapshot_november.csv (or current month)
        # File is overwritten daily with month-to-date work items and their total accumulated time

        # Yesterday's snapshot with sequential processing
        python main.py --daily-snapshot --no-parallel

      Output Filenames:
        - yesterday/today/custom: daily_snapshot_YYYYMMDD_HHMM.csv (timestamped)
        - month-to-date: daily_snapshot_<monthname>.csv (monthly cumulative)
        - --output-filename: Use custom name (overrides automatic naming)

      Automation Workflow (GitHub Actions → Logic App):
        # Recommended: Monthly cumulative file (one file per month)
        python main.py --daily-snapshot --snapshot-mode month-to-date
        # Overwrites daily_snapshot_november.csv daily with:
        #   - Work items active in November (filtered by date range)
        #   - Total accumulated active/blocked time from entire history (not filtered)
        # Automatically switches to daily_snapshot_december.csv on Dec 1st

        # Alternative: Fixed filename (overwrites same file daily)
        python main.py --daily-snapshot --output-filename daily_snapshot.csv

Environment Variables:
  AZURE_DEVOPS_ORG   : Default Azure DevOps organization name.
  AZURE_DEVOPS_PAT   : Default Azure DevOps personal access token.
  AZURE_LOGIC_APP_URL : Logic App URL for work item fetching (REQUIRED for --query-work-items).
  AZURE_DEVOPS_WORKITEM_WEBHOOK_URL : Default webhook URL for workitem.updated events.
  AZURE_DEVOPS_BUILD_WEBHOOK_URL : Default webhook URL for build.complete events.
  AZURE_DEVOPS_RELEASE_WEBHOOK_URL : Default webhook URL for release.deployment.completed events.

Configuration Files:
  user_email_mapping.json : Name-to-email mapping for user resolution (REQUIRED for --query-work-items).

Use --help for a detailed usage guide.
"""
    print(explanation)


def handle_project_operations(args, project_ops):
    """
    Dispatch table for project-specific operations.
    """
    operations = {
        "list_work_items": project_ops.list_work_items,
        "create_work_item": lambda: project_ops.create_work_item(
            work_item_type=args.work_item_type,
            title=args.work_item_title,
            description=args.work_item_description
        ),
        "list_github_repos": project_ops.list_github_repositories
    }

    # Determine which operation to execute
    for operation_name, operation_func in operations.items():
        if getattr(args, operation_name, False):
            operation_func()
            return

    print("Error: No valid project-specific operation provided.")


def handle_daily_snapshot(args, organization, personal_access_token):
    """
    Handle daily snapshot generation for automated tracking.

    Generates simplified CSV files with basic time tracking data (active/blocked hours)
    without complex efficiency calculations or performance metrics.

    Optimized for GitHub Actions → Logic App → SharePoint workflows.
    """
    from datetime import datetime, timedelta

    print("📸 ========================================")
    print("📸 DAILY SNAPSHOT GENERATION")
    print("📸 ========================================")

    # Calculate date range based on snapshot mode
    snapshot_mode = args.snapshot_mode
    today = datetime.now().date()

    if snapshot_mode == "yesterday":
        target_date = today - timedelta(days=1)
        start_date = target_date.strftime("%Y-%m-%d")
        end_date = target_date.strftime("%Y-%m-%d")
        print(f"📅 Mode: Yesterday ({start_date})")
    elif snapshot_mode == "today":
        start_date = today.strftime("%Y-%m-%d")
        end_date = today.strftime("%Y-%m-%d")
        print(f"📅 Mode: Today ({start_date})")
    elif snapshot_mode == "month-to-date":
        first_day_of_month = today.replace(day=1)
        start_date = first_day_of_month.strftime("%Y-%m-%d")
        end_date = today.strftime("%Y-%m-%d")
        print(f"📅 Mode: Month-to-date ({start_date} to {end_date})")
    elif snapshot_mode == "custom":
        if not args.start_date or not args.end_date:
            print("❌ Error: Custom mode requires --start-date and --end-date")
            print("   Example: --snapshot-mode custom --start-date 2025-01-01 --end-date 2025-01-31")
            return
        start_date = args.start_date
        end_date = args.end_date
        print(f"📅 Mode: Custom ({start_date} to {end_date})")

    # Parse assigned-to filter
    assigned_to = [name.strip() for name in args.assigned_to.split(',')] if args.assigned_to else None

    # Determine output filename
    if args.output_filename:
        # Use custom filename (for automation workflows)
        filename = args.output_filename
        print(f"📁 Output file: {filename} (fixed filename)")
    elif snapshot_mode == "month-to-date":
        # Auto-generate month-based filename for month-to-date mode
        month_name = today.strftime("%B").lower()  # e.g., "november"
        filename = f"daily_snapshot_{month_name}.csv"
        print(f"📁 Output file: {filename} (monthly cumulative)")
    else:
        # Auto-generate filename with timestamp (default)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        filename = f"daily_snapshot_{timestamp}.csv"
        print(f"📁 Output file: {filename} (timestamped)")

    # Create WorkItemOperations instance (no scoring config needed for snapshots)
    work_item_ops = WorkItemOperations(organization, personal_access_token)

    # Execute snapshot generation
    try:
        result = work_item_ops.get_daily_snapshot_from_logic_app(
            from_date=start_date,
            to_date=end_date,
            assigned_to=assigned_to,
            use_parallel_processing=not args.no_parallel,
            max_workers=args.max_workers,
            output_filename=filename
        )

        # Display summary
        print("\n✅ ========================================")
        print("✅ SNAPSHOT COMPLETE")
        print("✅ ========================================")
        print(f"   Work items: {result['total_items']}")
        print(f"   Date range: {start_date} to {end_date}")
        print(f"   Output file: {filename}")
        if assigned_to:
            print(f"   Filtered to: {', '.join(assigned_to)}")
        print("✅ ========================================")

    except Exception as e:
        print(f"❌ Snapshot generation failed: {e}")
        print("\nTroubleshooting:")
        print("1. Ensure AZURE_LOGIC_APP_URL is set in .env file")
        print("2. Verify user_email_mapping.json exists with valid name→email mappings")
        print("3. Check Logic App is accessible and responding")
        return


def handle_work_item_query(args, organization, personal_access_token):
    """
    Handle work item querying with dynamic filtering and KPI calculations.

    NEW DEFAULT: Uses Logic App for work item fetching.
    Legacy WIQL/Analytics method removed per refactoring requirements.
    """
    # Parse comma-separated values (strip whitespace)
    assigned_to = [name.strip() for name in args.assigned_to.split(',')] if args.assigned_to else None
    work_item_types = [wtype.strip() for wtype in args.work_item_types.split(',')] if args.work_item_types else None
    states = [state.strip() for state in args.states.split(',')] if args.states else None
    project_names = [name.strip() for name in args.project_names.split(',')] if args.project_names else None
    productive_states = [state.strip() for state in args.productive_states.split(',')] if args.productive_states else None
    blocked_states = [state.strip() for state in args.blocked_states.split(',')] if args.blocked_states else None
    
    # Build additional filters
    additional_filters = {}
    if args.area_path:
        additional_filters['area_path'] = args.area_path
    if args.iteration_path:
        additional_filters['iteration_path'] = args.iteration_path
    
    # Build scoring configuration from arguments
    scoring_config = None
    if args.scoring_config:
        try:
            with open(args.scoring_config, 'r') as f:
                scoring_config = json.load(f)
            print(f"Loaded scoring configuration from {args.scoring_config}")
        except Exception as e:
            print(f"Error loading scoring config: {e}")
            scoring_config = {}
    else:
        scoring_config = {}
    
    # Apply individual scoring parameter overrides
    if args.completion_bonus is not None:
        scoring_config['completion_bonus_percentage'] = args.completion_bonus
    if args.max_efficiency_cap is not None:
        scoring_config['max_efficiency_cap'] = args.max_efficiency_cap
    if args.max_hours_per_day is not None:
        scoring_config['max_hours_per_day'] = args.max_hours_per_day
    
    # Apply developer score weight overrides
    if any([args.fair_efficiency_weight, args.delivery_score_weight, args.completion_rate_weight, args.on_time_delivery_weight]):
        if 'developer_score_weights' not in scoring_config:
            scoring_config['developer_score_weights'] = {}
        if args.fair_efficiency_weight is not None:
            scoring_config['developer_score_weights']['fair_efficiency'] = args.fair_efficiency_weight
        if args.delivery_score_weight is not None:
            scoring_config['developer_score_weights']['delivery_score'] = args.delivery_score_weight
        if args.completion_rate_weight is not None:
            scoring_config['developer_score_weights']['completion_rate'] = args.completion_rate_weight
        if args.on_time_delivery_weight is not None:
            scoring_config['developer_score_weights']['on_time_delivery'] = args.on_time_delivery_weight
    
    # Create WorkItemOperations instance with scoring configuration
    work_item_ops = WorkItemOperations(organization, personal_access_token, scoring_config)

    # NEW DEFAULT FLOW: Use Logic App for work item fetching
    # This replaces the previous WIQL/Analytics method
    print("🚀 Using Logic App (Fabric Data Warehouse) for work item fetching")

    # Validate required arguments for Logic App flow
    if not args.start_date or not args.end_date:
        print("❌ Error: --start-date and --end-date are required for Logic App flow")
        print("   Example: --start-date 2025-10-01 --end-date 2025-10-31")
        return

    # Execute query using Logic App
    try:
        result = work_item_ops.get_work_items_from_logic_app(
            from_date=args.start_date,
            to_date=args.end_date,
            assigned_to=assigned_to,
            calculate_efficiency=not args.no_efficiency,
            use_parallel_processing=not args.no_parallel,
            max_workers=args.max_workers,
            export_csv=args.export_csv
        )
    except Exception as e:
        print(f"❌ Failed to fetch work items from Logic App: {e}")
        print("\nTroubleshooting:")
        print("1. Ensure AZURE_LOGIC_APP_URL is set in .env file")
        print("2. Verify user_email_mapping.json exists with valid name→email mappings")
        print("3. Check Logic App is accessible and responding")
        sys.exit(1)

    # Note: CSV export is handled within get_work_items_from_logic_app if --export-csv is provided
    query_scope = f"Logic App query for {', '.join(assigned_to) if assigned_to else 'all users'}"
    
    # Display results
    print("\n" + "="*80)
    print("WORK ITEMS QUERY RESULTS")
    print("="*80)
    
    # Query info
    query_info = result.get('query_info', {})
    print(f"Query scope: {query_scope}")
    print(f"Total items found: {query_info.get('total_items', 0)}")
    
    # Show projects queried
    projects_queried = query_info.get('projects_queried', [])
    if projects_queried:
        # Handle both string and dict formats
        if projects_queried and isinstance(projects_queried[0], dict):
            project_names = [p.get('name', str(p)) for p in projects_queried]
        else:
            project_names = projects_queried
        print(f"Projects queried: {', '.join(project_names)}")
    
    filters = query_info.get('filters_applied', {})
    if filters.get('assigned_to'):
        print(f"Assigned to: {', '.join(filters['assigned_to'])}")
    if filters.get('work_item_types'):
        print(f"Work item types: {', '.join(filters['work_item_types'])}")
    if filters.get('states'):
        print(f"States: {', '.join(filters['states'])}")
    print(f"Date range: {filters.get('date_range', 'Any')}")
    
    # Enhanced KPIs with per-developer metrics
    kpis = result.get('kpis', {})
    if kpis:
        # Overall summary
        overall_summary = kpis.get('overall_summary', {})
        print(f"\nOVERALL SUMMARY:")
        print(f"  Total work items: {overall_summary.get('total_work_items', 0)}")
        print(f"  Total developers: {overall_summary.get('total_developers', 0)}")
        print(f"  Average fair efficiency: {overall_summary.get('average_fair_efficiency', 0)}%")
        print(f"  Average delivery score: {overall_summary.get('average_delivery_score', 0)}%")
        print(f"  Total active hours: {overall_summary.get('total_active_hours', 0)}")
        
        # Per-developer metrics
        developer_metrics = kpis.get('developer_metrics', {})
        if developer_metrics:
            print(f"\nPER-DEVELOPER METRICS:")
            for developer, metrics in developer_metrics.items():
                print(f"\n  📊 {developer}:")
                print(f"    • Work Items: {metrics.get('total_work_items', 0)} (Completed: {metrics.get('completed_items', 0)})")
                print(f"    • Completion Rate: {metrics.get('completion_rate', 0)}%")
                print(f"    • Fair Efficiency Score: {metrics.get('average_fair_efficiency', 0)}%")
                print(f"    • Delivery Score: {metrics.get('average_delivery_score', 0)}%")
                print(f"    • Overall Developer Score: {metrics.get('overall_developer_score', 0)}%")
                print(f"    • On-time Delivery: {metrics.get('on_time_delivery_percentage', 0)}%")
                print(f"    • Active Hours: {metrics.get('total_active_hours', 0)}h")
                print(f"    • Avg Days Ahead/Behind Target: {metrics.get('average_days_ahead_behind', 0)}")
                print(f"    • Reopened Items Handled: {metrics.get('reopened_items_handled', 0)}")
                print(f"    • Projects Worked On: {metrics.get('projects_count', 0)}")
                
                # Delivery timing breakdown
                timing = metrics.get('delivery_timing_breakdown', {})
                print(f"    • Delivery Timing: Early:{timing.get('early', 0)} | On-time:{timing.get('on_time', 0)} | Late:{timing.get('late_1_3', 0)+timing.get('late_4_7', 0)+timing.get('late_8_14', 0)+timing.get('late_15_plus', 0)}")
        
        # Bottlenecks
        bottlenecks = kpis.get('bottlenecks', [])
        if bottlenecks:
            print(f"\nTOP BOTTLENECKS:")
            for i, bottleneck in enumerate(bottlenecks[:5], 1):
                print(f"  {i}. {bottleneck['state']}: {bottleneck['average_time_hours']}h avg ({bottleneck['occurrences']} occurrences)")
    
    # Enhanced work items summary
    work_items = result.get('work_items', [])
    if work_items:
        print(f"\nWORK ITEMS DETAILED SUMMARY:")
        for item in work_items[:5]:  # Show first 5
            efficiency = item.get('efficiency', {})
            project_info = f" | Project: {item.get('project_name', 'Unknown')}" if item.get('project_name') else ""
            print(f"  ID {item['id']}: {item['title'][:50]}...")
            print(f"    Assigned: {item['assigned_to']} | State: {item['state']}{project_info}")
            if efficiency:
                print(f"    Traditional Efficiency: {efficiency.get('efficiency_percentage', 0)}%")
                print(f"    Fair Efficiency Score: {efficiency.get('fair_efficiency_score', 0)}%")
                print(f"    Delivery Score: {efficiency.get('delivery_score', 0)}%")
                print(f"    Active Time: {efficiency.get('active_time_hours', 0)}h | Estimated: {efficiency.get('estimated_time_hours', 0)}h")
                print(f"    Days Ahead/Behind Target: {efficiency.get('days_ahead_behind', 0)}")
                if efficiency.get('was_reopened', False):
                    print(f"    ↻ Reopened item (Active after reopen: {efficiency.get('active_after_reopen', 0)}h)")
            print()
        
        if len(work_items) > 5:
            print(f"... and {len(work_items) - 5} more items")
    
    # Export to CSV if requested
    if args.export_csv:
        # Use enhanced export function
        base_filename = args.export_csv.replace('.csv', '')
        work_item_ops.export_enhanced_work_items_to_csv(work_items, kpis, base_filename)
    
    print("\n" + "="*80)


def main():
    parser = argparse.ArgumentParser(description="Azure DevOps CLI Utility Inbest")
    parser.add_argument("--organization", help="Azure DevOps organization name (optional, fallback to AZURE_DEVOPS_ORG environment variable)")
    parser.add_argument("--personal-access-token", help="Azure DevOps personal access token (optional, fallback to AZURE_DEVOPS_PAT environment variable)")
    
    # Global commands
    parser.add_argument("--list-projects", action="store_true", help="List all projects in the organization")
    parser.add_argument("--filter-tag", nargs="*", help="Filter projects by tags in the description (e.g., 'Software Factory')")
    parser.add_argument("--create-hook", action="store_true", help="Create a service hook for a project")
    parser.add_argument("--remove-hook", action="store_true", help="Remove service hook subscriptions")
    parser.add_argument("--project-id", help="Project ID for the service hook or project-specific operations")
    parser.add_argument("--subscription-id", help="Subscription ID for removing specific service hooks")
    parser.add_argument("--event-type", help="Event type for the service hook (e.g., 'workitem.updated')")
    parser.add_argument("--hook-url", help="Webhook URL for the service hook (optional, fallback to configured URL)")
    parser.add_argument("--explain", action="store_true", help="Explain all commands and arguments")
    parser.add_argument("--create-hooks-for-filtered-projects", action="store_true",
                        help="Create service hooks for projects filtered by tags")
    parser.add_argument("--state-changed", action="store_true",
                        help="If set and event-type=workitem.updated, only trigger when State changes")
    parser.add_argument("--list-and-upgrade-webhooks", action="store_true", help="List projects by tag and upgrade their webhooks")
    parser.add_argument("--list-subscriptions", action="store_true",
                        help="List service hook subscriptions for the specified project")

    # Project-specific commands
    parser.add_argument("--list-work-items", action="store_true", help="List all work items in the project")
    parser.add_argument("--create-work-item", action="store_true", help="Create a new work item in the project")
    parser.add_argument("--work-item-type", help="Type of the work item to create (e.g., Bug, Task)")
    parser.add_argument("--work-item-title", help="Title of the new work item")
    parser.add_argument("--work-item-description", help="Description of the new work item")
    parser.add_argument("--list-github-repos", action="store_true", help="List GitHub repositories connected to the project")
    parser.add_argument(
        "--create-filtered-hook",
        action="store_true",
        help="Create a service hook for workitem.updated with field filters (e.g., Priority, TargetDate, CommentCount)"
    )

    # Command to create standard hooks
    parser.add_argument("--create-standard-hooks", action="store_true",
                        help="Create a standard set of three webhooks (created, updated-assigned, updated-state) for a specific project (--project-id) or filtered projects (--filter-tag)")

    # Command to export projects to CSV
    parser.add_argument("--export-projects-csv", action="store_true",
                        help="Export all projects (Name, ID, Tags) to projects_export.csv")

    # Work item querying arguments (Logic App flow)
    parser.add_argument("--query-work-items", action="store_true",
                        help="Query work items from Logic App (Fabric Data Warehouse) with KPI calculations")
    parser.add_argument("--assigned-to", help="Comma-separated list of user names or emails (omit for all users)")
    parser.add_argument("--start-date", help="Start date for filtering (YYYY-MM-DD format) - REQUIRED")
    parser.add_argument("--end-date", help="End date for filtering (YYYY-MM-DD format) - REQUIRED")
    parser.add_argument("--no-efficiency", action="store_true", help="Skip efficiency calculations")
    parser.add_argument("--export-csv", help="Export results to CSV file")

    # Daily snapshot arguments
    parser.add_argument("--daily-snapshot", action="store_true",
                        help="Generate simplified daily work item snapshot for automated tracking")
    parser.add_argument("--snapshot-mode",
                        choices=["yesterday", "today", "month-to-date", "custom"],
                        default="yesterday",
                        help="Snapshot mode: yesterday (default), today, month-to-date, or custom (requires --start-date and --end-date)")
    parser.add_argument("--output-filename",
                        help="Override default filename (default: daily_snapshot_YYYYMMDD_HHMM.csv). Use fixed name for automation workflows.")

    # Legacy arguments (kept for backward compatibility but ignored in Logic App flow)
    parser.add_argument("--work-item-types", help="(Legacy - ignored in Logic App flow)")
    parser.add_argument("--states", help="(Legacy - ignored in Logic App flow)")
    parser.add_argument("--date-field", default="ClosedDate", help="(Legacy - ignored in Logic App flow)")
    parser.add_argument("--area-path", help="(Legacy - ignored in Logic App flow)")
    parser.add_argument("--iteration-path", help="(Legacy - ignored in Logic App flow)")
    parser.add_argument("--project-names", help="(Legacy - ignored in Logic App flow)")
    parser.add_argument("--all-projects", action="store_true", help="(Legacy - ignored in Logic App flow)")
    parser.add_argument("--max-projects", type=int, default=50, help="(Legacy - ignored in Logic App flow)")
    parser.add_argument("--productive-states", help="(Legacy - ignored in Logic App flow)")
    parser.add_argument("--blocked-states", help="(Legacy - ignored in Logic App flow)")
    
    # Developer scoring configuration
    parser.add_argument("--scoring-config", help="Path to JSON file with custom scoring configuration")
    parser.add_argument("--completion-bonus", type=float, help="Completion bonus percentage (default: 0.20 = 20 percent)")
    parser.add_argument("--max-efficiency-cap", type=float, help="Maximum efficiency cap percentage (default: 150.0)")
    parser.add_argument("--max-hours-per-day", type=float, help="Maximum business hours per day (default: 10.0)")
    parser.add_argument("--fair-efficiency-weight", type=float, help="Fair efficiency weight in developer score (default: 0.4)")
    parser.add_argument("--delivery-score-weight", type=float, help="Delivery score weight in developer score (default: 0.3)")
    parser.add_argument("--completion-rate-weight", type=float, help="Completion rate weight in developer score (default: 0.2)")
    parser.add_argument("--on-time-delivery-weight", type=float, help="On-time delivery weight in developer score (default: 0.1)")
    
    # Performance optimization flags (kept for compatibility with new Logic App flow)
    parser.add_argument("--no-parallel", action="store_true", help="Disable parallel revision fetching (use sequential instead)")
    parser.add_argument("--max-workers", type=int, default=10, help="Maximum number of parallel workers for revision fetching (default: 10)")
    
    args = parser.parse_args()

    # Handle explain command
    if args.explain:
        explain_commands()
        return

    # Get organization and PAT from arguments or environment variables
    organization = args.organization or Config.AZURE_DEVOPS_ORG
    personal_access_token = args.personal_access_token or Config.AZURE_DEVOPS_PAT

    print("Using organization:", organization)
    
    
    if not organization:
        print("Error: Azure DevOps organization is required. Provide it via --organization or set AZURE_DEVOPS_ORG.")
        return
    if not personal_access_token:
        print("Error: Azure DevOps personal access token is required. Provide it via --personal-access-token or set AZURE_DEVOPS_PAT.")
        return

    az_commands = AzureDevOpsCommands(organization, personal_access_token)

    # Dispatch table for global operations
    global_operations = {
        "list_projects": lambda: az_commands.list_projects_with_tag_filter(args.filter_tag) 
            if args.filter_tag else az_commands.list_projects(),

        "list_subscriptions": lambda: az_commands.list_subscriptions(args.project_id),

        "create_hook": lambda: az_commands.create_service_hook(
            project_id=args.project_id,
            event_type=args.event_type,
            hook_url=args.hook_url,
            state_changed=args.state_changed
        ) if args.project_id and args.event_type else print(
            "Error: --project-id and --event-type are required to create a service hook."
        ),

        "remove_hook": lambda: az_commands.remove_service_hook(
            project_id=args.project_id,
            subscription_id=args.subscription_id
        ) if args.project_id else print(
            "Error: --project-id is required to remove a service hook."
        ),

        "create_hooks_for_filtered_projects": lambda: az_commands.create_hooks_for_filtered_projects(
            target_tags=args.filter_tag,
            event_type=args.event_type,
            hook_url=args.hook_url,
            state_changed=args.state_changed
        ) if args.filter_tag and args.event_type else print(
            "Error: Missing arguments for creating service hooks. Provide --filter-tag and --event-type."
        ),

        "list_work_items": lambda: AzureDevOpsProjectOperations(
            organization, personal_access_token, args.project_id
        ).list_work_items() if args.project_id else print(
            "Error: --project-id is required to list work items."
        ),

        "create_work_item": lambda: AzureDevOpsProjectOperations(
            organization, personal_access_token, args.project_id
        ).create_work_item(
            work_item_type=args.work_item_type,
            title=args.work_item_title,
            description=args.work_item_description
        ) if args.project_id and args.work_item_type and args.work_item_title else print(
            "Error: Missing required arguments for creating work item."
        ),

        "list_github_repos": lambda: AzureDevOpsProjectOperations(
            organization, personal_access_token, args.project_id
        ).list_github_repositories() if args.project_id else print(
            "Error: --project-id is required to list GitHub repositories."
        ),

        "list_and_upgrade_webhooks": lambda: az_commands.list_and_update_webhooks(args.filter_tag) if args.filter_tag else print(
            "Error: --filter-tag is required to list and upgrade webhooks."
        ),

        "create_standard_hooks": lambda: (
            print(f"Debug - main.py: Calling create_standard_hooks with project_id={args.project_id}, target_tags={args.filter_tag}"),
            az_commands.create_standard_hooks(
                project_id=args.project_id,
                target_tags=args.filter_tag
            )
        )[1],

        "export_projects_csv": lambda: az_commands.export_projects_to_csv(),

        "query_work_items": lambda: handle_work_item_query(args, organization, personal_access_token),

        "daily_snapshot": lambda: handle_daily_snapshot(args, organization, personal_access_token),
    }


    # Determine which global operation to execute
    for operation_name, operation_func in global_operations.items():
        if getattr(args, operation_name, False):
            operation_func()
            return

    # Handle project-specific operations (if no global operation matched and project_id is given)
    if args.project_id and not any(getattr(args, op, False) for op in global_operations):
        project_ops = AzureDevOpsProjectOperations(organization, personal_access_token, args.project_id)
        handle_project_operations(args, project_ops)
    elif not any(getattr(args, op, False) for op in global_operations):
        print("Error: No valid operation provided or required arguments missing.")
        parser.print_help()


if __name__ == "__main__":
    main()
