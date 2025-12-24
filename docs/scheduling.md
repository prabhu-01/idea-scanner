# Scheduling & Automation Guide

This document explains how to automate the Idea Digest pipeline for regular execution.

## Table of Contents

- [Local Cron Setup](#local-cron-setup)
- [GitHub Actions](#github-actions)
- [Choosing an Automation Method](#choosing-an-automation-method)
- [Environment Variables](#environment-variables)
- [Debugging Failed Runs](#debugging-failed-runs)
- [Testing Automation](#testing-automation)

---

## Local Cron Setup

### Prerequisites

1. A Unix-like system (Linux, macOS) with cron installed
2. Python 3.10+ installed
3. The repository cloned to a local directory
4. A `.env` file configured with your API keys

### Crontab Entry

Add the following to your crontab (`crontab -e`):

```cron
# Idea Digest - Run daily at 9 AM local time
0 9 * * * cd /path/to/idea-digest && /usr/bin/python3 main.py --limit-per-source 20 >> /var/log/idea-digest.log 2>&1
```

**Breaking down the cron expression:**

| Field | Value | Meaning |
|-------|-------|---------|
| Minute | `0` | At minute 0 |
| Hour | `9` | At 9 AM |
| Day of month | `*` | Every day |
| Month | `*` | Every month |
| Day of week | `*` | Every day of the week |

### Alternative Schedules

```cron
# Run twice daily (9 AM and 6 PM)
0 9,18 * * * cd /path/to/idea-digest && /usr/bin/python3 main.py >> /var/log/idea-digest.log 2>&1

# Run every 6 hours
0 */6 * * * cd /path/to/idea-digest && /usr/bin/python3 main.py >> /var/log/idea-digest.log 2>&1

# Run only on weekdays at 8 AM
0 8 * * 1-5 cd /path/to/idea-digest && /usr/bin/python3 main.py >> /var/log/idea-digest.log 2>&1
```

### With Virtual Environment

If using a virtual environment:

```cron
0 9 * * * cd /path/to/idea-digest && source venv/bin/activate && python main.py >> /var/log/idea-digest.log 2>&1
```

### With Environment Variables

Load environment variables explicitly:

```cron
0 9 * * * cd /path/to/idea-digest && export $(cat .env | xargs) && /usr/bin/python3 main.py >> /var/log/idea-digest.log 2>&1
```

### Viewing Logs

```bash
# View recent logs
tail -f /var/log/idea-digest.log

# View last run
tail -100 /var/log/idea-digest.log

# Search for errors
grep -i error /var/log/idea-digest.log
```

### Common Issues

| Issue | Solution |
|-------|----------|
| Script not running | Check cron service: `systemctl status cron` |
| Environment not loaded | Add explicit `source .env` or `export` |
| Wrong Python version | Use absolute path: `/usr/bin/python3.11` |
| Permission denied | Ensure script is executable and paths are absolute |

---

## GitHub Actions

### Overview

The repository includes a GitHub Actions workflow at `.github/workflows/daily-digest.yml` that:

- Runs automatically every day at 9 AM UTC
- Can be triggered manually via the Actions tab
- Supports dry-run mode for testing
- Uploads generated digests as artifacts

### Required Secrets

Configure these in your repository settings:

| Secret | Required | Description |
|--------|----------|-------------|
| `AIRTABLE_API_KEY` | Yes | Your Airtable API key |
| `AIRTABLE_BASE_ID` | Yes | Your Airtable base ID |
| `AIRTABLE_TABLE_NAME` | No | Table name (default: "Ideas") |
| `GITHUB_TOKEN_PAT` | No | GitHub PAT for higher rate limits |
| `PRODUCT_HUNT_TOKEN` | No | Product Hunt API token |

### Setting Up Secrets

1. Go to your repository on GitHub
2. Click **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Add each secret with its name and value

### Manual Execution

1. Go to **Actions** tab in your repository
2. Select **Daily Idea Digest** workflow
3. Click **Run workflow**
4. Configure options:
   - **dry_run**: Set to `true` for testing
   - **limit_per_source**: Number of items per source
   - **sources**: Comma-separated list or "all"
5. Click **Run workflow**

### Viewing Logs

1. Go to **Actions** tab
2. Click on the workflow run
3. Expand job steps to see logs
4. Download artifacts (digests) from the bottom of the page

### Customizing the Schedule

Edit `.github/workflows/daily-digest.yml`:

```yaml
on:
  schedule:
    # Run at 9 AM UTC
    - cron: '0 9 * * *'
    
    # Run at 9 AM and 6 PM UTC
    # - cron: '0 9,18 * * *'
    
    # Run every 6 hours
    # - cron: '0 */6 * * *'
```

**Note:** GitHub Actions schedules use UTC timezone.

---

## Choosing an Automation Method

| Method | Best For | Pros | Cons |
|--------|----------|------|------|
| **Local Cron** | Personal use, development | Full control, no external dependencies | Requires always-on machine |
| **GitHub Actions** | Production, teams | Managed infrastructure, logs, artifacts | Limited free minutes, public visibility |
| **Manual** | Testing, ad-hoc runs | Immediate feedback, full control | Requires human intervention |

### Decision Guide

**Use Local Cron when:**
- You have a dedicated server or always-on machine
- You need more than 2000 minutes/month of execution
- You want to keep everything private/local
- You need real-time control over execution

**Use GitHub Actions when:**
- You want managed, reliable scheduling
- You're working in a team
- You want automatic artifact storage
- You don't have a dedicated server

**Use Manual Runs when:**
- Testing changes before automation
- Running ad-hoc digest generation
- Debugging issues

---

## Environment Variables

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `AIRTABLE_API_KEY` | Airtable API authentication | `patXXXXX...` |
| `AIRTABLE_BASE_ID` | Target Airtable base | `appXXXXX...` |

### Optional Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AIRTABLE_TABLE_NAME` | `Ideas` | Table name in Airtable |
| `APP_ENV` | `development` | Environment mode |
| `DEBUG` | `false` | Enable debug logging |
| `DEFAULT_LIMIT_PER_SOURCE` | `20` | Items per source |
| `REQUEST_TIMEOUT` | `30` | HTTP timeout in seconds |
| `SCRAPE_DELAY` | `2.0` | Delay between requests |

### How Variables Flow

**Local Cron:**
```
.env file → shell environment → Python os.getenv() → config module
```

**GitHub Actions:**
```
Repository Secrets → workflow env → Python os.getenv() → config module
```

---

## Debugging Failed Runs

### Local Cron

1. **Check cron logs:**
   ```bash
   grep CRON /var/log/syslog
   # or on macOS
   log show --predicate 'process == "cron"' --last 1h
   ```

2. **Check application logs:**
   ```bash
   tail -100 /var/log/idea-digest.log
   ```

3. **Run manually with verbose output:**
   ```bash
   cd /path/to/idea-digest
   python main.py --verbose
   ```

### GitHub Actions

1. **View workflow run:**
   - Go to Actions tab
   - Click on the failed run
   - Expand failed step to see error

2. **Re-run with debug logging:**
   - Click "Re-run all jobs"
   - Or trigger manually with `--verbose` flag

3. **Check secrets are configured:**
   - Settings → Secrets → Verify all required secrets exist
   - Note: You cannot view secret values, only names

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `AIRTABLE_API_KEY is not configured` | Missing secret | Add secret to repository/environment |
| `Network error` | API unavailable | Retry, check rate limits |
| `SSL certificate error` | macOS SSL issue | Install certificates or use different Python |
| `No items fetched` | Sources down | Check individual source APIs |

---

## Testing Automation

### Dry-Run Mode

Always test with `--dry-run` first:

```bash
# Local
python main.py --dry-run --verbose --limit-per-source 5

# GitHub Actions - manual trigger with dry_run=true
```

This will:
- Fetch items from all sources
- Score and tag items
- **Skip** storage writes
- **Skip** digest generation

### Validate Configuration

```bash
python main.py --show-config
```

This displays:
- All configuration values
- Whether required secrets are set
- Any configuration warnings

### Test Single Source

```bash
# Test just Hacker News
python main.py --sources hackernews --dry-run --limit-per-source 3

# Test just GitHub
python main.py --sources github --dry-run --limit-per-source 3
```

### Simulate Full Run

```bash
# Full pipeline with small limit
python main.py --limit-per-source 3 --digest-limit 10 --verbose
```

Check:
- `digests/YYYY-MM-DD.md` was created
- No errors in output
- Items were stored (check Airtable or mock storage)

---

## Monitoring & Alerts

### GitHub Actions Notifications

GitHub can notify you of workflow failures:

1. Go to **Settings** → **Notifications**
2. Enable "Actions" notifications
3. You'll receive email on workflow failures

### Custom Alerting (Advanced)

Add a notification step to the workflow:

```yaml
- name: Notify on failure
  if: failure()
  uses: slackapi/slack-github-action@v1
  with:
    channel-id: 'C0XXXXXXX'
    slack-message: 'Idea Digest pipeline failed! Check: ${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}'
  env:
    SLACK_BOT_TOKEN: ${{ secrets.SLACK_BOT_TOKEN }}
```

