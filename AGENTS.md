# Repository Guidelines

## Project Structure & Module Organization
Core logic resides in `classes/`: `WorkItemOperations` handles analytics queries, `AzureDevOpsProjectOperations` covers project metadata, and `commands.py` wires CLI actions. Invoke the tool through `entry_points/main.py` (or the wrapper `run.py`). Defaults live in `config/` (`config.py`, `azure_devops_config.json`), supporting utilities in `helpers/`, reference docs in `documentation/`, and reusable SQL in `sql/`. CSV exports default to the repo root unless `--export-csv` points elsewhere.

## Build, Test, and Development Commands
- `python -m venv .venv && source .venv/bin/activate` — set up an isolated environment.
- `pip install -r requirements.txt` — install dependencies (requests, azure-devops SDK, dotenv, pyodbc, azure-identity).
- `python run.py --help` or `--explain` — review supported flags and command descriptions.
- `python run.py --list-projects` — smoke-test connectivity to the organization.
- `python run.py --query-work-items --assigned-to "Jane Doe" --start-date "2024-10-01" --end-date "2024-10-31" --export-csv reports/october.csv` — representative analytics run with CSV output.

## Coding Style & Naming Conventions
Follow standard Python style: four-space indentation, snake_case for functions and variables, PascalCase for classes, and module docstrings when modules have side effects. Prefer explicit imports from `classes` modules so CLI wiring stays readable. When extending commands, mirror the parser patterns in `entry_points/main.py` and keep user-facing logging concise.

## Testing Guidelines
No automated suite exists yet; validate changes by running representative CLI commands against a non-production Azure DevOps organization. Exercise project discovery (`--list-projects`, `--create-hooks-for-filtered-projects`) and analytics flows (`--query-work-items`, toggling `--optimized`). Capture CSV or terminal summaries to confirm metrics, and isolate reusable logic into functions or classes to keep future unit tests straightforward.

## Commit & Pull Request Guidelines
Recent commits use short, imperative subjects (for example, “Add developer summary CSV and SQL queries for estimated hours”). Keep subjects under 72 characters, expand on context and risk in the body, and reference Azure Boards items when applicable. Pull requests should describe the scenario, list touched commands or config files, attach sample output snippets or sanitized CSVs, and bundle documentation updates when behavior changes.

## Configuration & Security Tips
Store secrets in `.env` with `AZURE_DEVOPS_ORG` and `AZURE_DEVOPS_PAT`; never commit PATs or per-user overrides. Use `config/azure_devops_config.json` for shared defaults but keep credentials in environment variables. When exporting reports, route them to a dedicated folder and scrub personally identifiable information before sharing.
