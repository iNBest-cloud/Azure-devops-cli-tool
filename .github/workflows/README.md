# GitHub Actions Workflow Documentation

## Monthly Developer Report Workflow

Automated workflow that generates developer performance reports from Azure DevOps work items.

### Features

- **Scheduled Execution**: Automatically runs on the 30th of every month at 23:00 UTC
- **Manual Trigger**: Run on-demand with custom date ranges and developer filters
- **Automatic Artifact Storage**: Reports saved for 90 days
- **Performance Optimized**: Uses `--optimized` flag for faster execution

---

## Setup Instructions

### 1. Configure GitHub Secrets

The workflow requires two secrets to be configured in the `main` environment:

1. Go to your GitHub repository
2. Navigate to **Settings** → **Environments** → **main** (create if it doesn't exist)
3. Add the following secrets:

| Secret Name | Description | Example |
|-------------|-------------|---------|
| `AZURE_DEVOPS_ORG` | Your Azure DevOps organization name | `MyCompany` |
| `AZURE_DEVOPS_PAT` | Personal Access Token with Work Items: Read permission | `a1b2c3d4...` |

**To create a PAT:**
- Go to Azure DevOps → User Settings → Personal Access Tokens
- Click "New Token"
- Set expiration and scope: **Work Items: Read**
- Copy the generated token immediately

### 2. Enable GitHub Actions

1. Go to **Settings** → **Actions** → **General**
2. Ensure "Allow all actions and reusable workflows" is selected
3. Save changes

---

## Usage

### Automatic Monthly Reports

The workflow automatically runs on the **30th of each month at 23:00 UTC** and generates a report for:
- **Start Date**: 1st of the current month
- **End Date**: 30th of the current month
- **Developers**: Uses default list from `config/azure_devops_config.json`

**Default Developers** (from config):
- Luis Nocedal
- Carlos Vazquez
- Fernando Alcaraz
- Rodrigo Mendoza
- Jorge Hernandez

**Output Files:**
- `developer_report_YYYY-MM.csv` (detailed work items)
- `developer_report_YYYY-MM_developer_summary.csv` (aggregated metrics)

### Manual Execution

Run the workflow manually with custom parameters:

1. Go to **Actions** tab in your repository
2. Select **"Monthly Developer Report"** workflow
3. Click **"Run workflow"** button
4. Fill in the parameters:

#### Parameters

| Parameter | Required | Description | Example |
|-----------|----------|-------------|---------|
| `start_date` | Yes | Start date for the report | `2025-09-01` |
| `end_date` | Yes | End date for the report | `2025-09-30` |
| `assigned_to` | No | Comma-separated developer names (leave empty for all) | `John Doe,Jane Smith` |

5. Click **"Run workflow"**

### Example Manual Runs

**Generate report for September 2025:**
- start_date: `2025-09-01`
- end_date: `2025-09-30`
- assigned_to: *(leave empty)*

**Generate report for specific developers:**
- start_date: `2025-10-01`
- end_date: `2025-10-15`
- assigned_to: `Developer1,Developer2`

**Generate quarterly report:**
- start_date: `2025-07-01`
- end_date: `2025-09-30`
- assigned_to: *(leave empty)*

---

## Output Files

### File Naming Convention

**Scheduled runs:**
- `developer_report_YYYY-MM.csv`
- `developer_report_YYYY-MM_developer_summary.csv`

**Manual runs:**
- `developer_report_YYYY-MM-DD_to_YYYY-MM-DD.csv`
- `developer_report_YYYY-MM-DD_to_YYYY-MM-DD_developer_summary.csv`

### Downloading Reports

1. Go to the **Actions** tab
2. Click on the workflow run
3. Scroll to **Artifacts** section
4. Download `developer-report-[date-range].zip`
5. Extract to access CSV files

### Artifact Retention

Reports are stored for **90 days** after generation. Download important reports before they expire.

---

## Workflow Details

### Scheduled Execution

```yaml
schedule:
  - cron: '0 23 30 * *'  # 23:00 UTC on the 30th of every month
```

**Note:** GitHub Actions cron uses UTC timezone. Adjust if needed for your timezone.

### Manual Trigger

```yaml
workflow_dispatch:
  inputs:
    start_date: YYYY-MM-DD (required)
    end_date: YYYY-MM-DD (required)
    assigned_to: Comma-separated names (optional)
```

### Workflow Steps

1. **Checkout repository** - Clone the code
2. **Set up Python** - Install Python 3.11 with pip caching
3. **Install dependencies** - Install from `requirements.txt`
4. **Calculate date range** - Determine dates based on trigger type
5. **Generate report** - Run the CLI tool with optimized settings
6. **Upload artifacts** - Save reports for download
7. **Create summary** - Display execution summary in GitHub UI

---

## Troubleshooting

### Workflow Fails with Authentication Error

**Problem:** `Authentication failed` or `401 Unauthorized`

**Solution:**
1. Verify `AZURE_DEVOPS_PAT` secret is correctly set
2. Ensure PAT has not expired
3. Confirm PAT has `Work Items: Read` permission
4. Check `AZURE_DEVOPS_ORG` matches your organization name exactly

### No Reports Generated

**Problem:** Workflow completes but no artifacts uploaded

**Solution:**
1. Check workflow logs for Python errors
2. Verify date range contains work items
3. Ensure developers have work items assigned in that period
4. Check `run.py` script exists in repository root

### Scheduled Run Doesn't Execute

**Problem:** Workflow doesn't run on the 30th

**Solution:**
1. Verify GitHub Actions are enabled in repository settings
2. Check if the repository is active (GitHub may disable Actions on inactive repos)
3. Note: Scheduled runs may be delayed during high GitHub load
4. Manually trigger the workflow to verify it works

### Reports Are Empty or Incomplete

**Problem:** CSV files are generated but contain no data

**Solution:**
1. Check date range matches actual work item activity
2. Verify work items are in the expected states (Closed, Done, etc.)
3. Ensure developers are correctly assigned to work items
4. Try using `--all-projects` flag (requires workflow modification)

---

## Customization

### Modify Default Developer List

Edit `config/azure_devops_config.json`:

```json
{
  "work_item_query": {
    ...
    "default_developers": [
      "Developer Name 1",
      "Developer Name 2",
      "Developer Name 3"
    ]
  }
}
```

The workflow will automatically use this list for scheduled runs. Manual runs can still override with custom developer names.

### Modify Scheduled Time

Edit `.github/workflows/monthly-developer-report.yml`:

```yaml
schedule:
  - cron: '0 9 1 * *'  # 09:00 UTC on the 1st of every month
```

Cron syntax: `minute hour day-of-month month day-of-week`

### Change Date Range for Scheduled Runs

Edit the "Calculate date range" step:

```bash
# Example: Generate report for previous month
START_DATE=$(date -d "last month" +%Y-%m-01)
END_DATE=$(date -d "last month" +%Y-%m-%d)
```

### Add Additional CLI Options

Edit the "Generate developer report" step:

```bash
CMD="python run.py --query-work-items \
  --start-date ${{ steps.dates.outputs.start_date }} \
  --end-date ${{ steps.dates.outputs.end_date }} \
  --optimized \
  --max-workers 15 \
  --work-item-types 'Task,Bug' \
  --export-csv developer_report_${{ steps.dates.outputs.filename_suffix }}.csv"
```

### Enable Email Notifications

Add a notification step at the end of the workflow:

```yaml
- name: Send email notification
  uses: dawidd6/action-send-mail@v3
  with:
    server_address: smtp.gmail.com
    server_port: 465
    username: ${{ secrets.EMAIL_USERNAME }}
    password: ${{ secrets.EMAIL_PASSWORD }}
    subject: Monthly Developer Report - ${{ steps.dates.outputs.filename_suffix }}
    body: Report generated successfully. Download from GitHub Actions artifacts.
    to: team@company.com
    from: noreply@company.com
```

---

## Advanced Configuration

### Run for Multiple Developer Groups

Create separate workflow files for different teams:

```yaml
# .github/workflows/team-frontend-report.yml
- name: Generate frontend team report
  run: |
    python run.py --query-work-items \
      --assigned-to "FrontendDev1,FrontendDev2,FrontendDev3" \
      --start-date ${{ steps.dates.outputs.start_date }} \
      --end-date ${{ steps.dates.outputs.end_date }} \
      --export-csv frontend_team_report.csv
```

### Store Reports in Cloud Storage

Add a step to upload to AWS S3, Azure Blob, or Google Cloud Storage:

```yaml
- name: Upload to Azure Blob Storage
  uses: azure/CLI@v1
  with:
    inlineScript: |
      az storage blob upload \
        --account-name ${{ secrets.STORAGE_ACCOUNT }} \
        --container-name reports \
        --name developer_report_${{ steps.dates.outputs.filename_suffix }}.csv \
        --file developer_report_${{ steps.dates.outputs.filename_suffix }}.csv
```

### Create GitHub Release with Reports

Automatically create a release with attached reports:

```yaml
- name: Create Release
  uses: softprops/action-gh-release@v1
  with:
    tag_name: report-${{ steps.dates.outputs.filename_suffix }}
    name: Developer Report - ${{ steps.dates.outputs.filename_suffix }}
    files: |
      developer_report_${{ steps.dates.outputs.filename_suffix }}.csv
      developer_report_${{ steps.dates.outputs.filename_suffix }}_developer_summary.csv
```

---

## Monitoring

### View Workflow Execution History

1. Go to **Actions** tab
2. Select **"Monthly Developer Report"** workflow
3. View all past runs with status and duration

### Check Workflow Status

- **Green checkmark**: Successful execution
- **Red X**: Failed execution (check logs)
- **Yellow dot**: Currently running
- **Gray circle**: Queued or waiting

### Workflow Logs

Click on any workflow run to view detailed logs for each step, including:
- Python dependency installation
- Report generation output
- File sizes and developer counts
- Error messages (if any)

---

## Security Best Practices

1. **Never commit PAT tokens** to the repository
2. **Use environment protection rules** to restrict who can run workflows
3. **Rotate PATs regularly** (recommended: every 90 days)
4. **Use minimal PAT permissions** (only Work Items: Read)
5. **Enable audit logging** for sensitive operations
6. **Review workflow run logs** for suspicious activity

---

## Support

For issues with the workflow:
1. Check the **Troubleshooting** section above
2. Review workflow run logs in the Actions tab
3. Verify secrets are correctly configured
4. Test the CLI command locally first

For issues with the Azure DevOps CLI tool itself:
- Refer to the main [README.md](../../README.md)
- Check [documentation/](../../documentation/) folder
