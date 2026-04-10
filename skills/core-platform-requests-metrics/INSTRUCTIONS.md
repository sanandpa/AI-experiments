# Core Platform Requests Metrics Report — Instructions

Generate the quarterly metrics report for the AI Core Platform Requests Channel.
These instructions work with any AI assistant (Cursor, Claude Code, Gemini, etc.)
or can be followed manually from the terminal.

## Prerequisites

- Python 3 installed
- A CSV export from the Slack Help Requests Tracker (#ai-core-platform-requests)
- (Optional) The metrics-history.json file from Google Drive for trend comparison

## Where things live

**Script and instructions (public, no sensitive data):**
- https://github.com/sanandpa/AI-experiments
- Path: `skills/core-platform-requests-metrics/`

**Reports and history (internal, sensitive data — do NOT commit to public repos):**
- Google Drive: https://drive.google.com/drive/u/0/folders/1g4NlUgiXLCNYhaMGLai6fgX_ZMb5dxKe
- Folder structure:
  - `metrics-history.json` — cumulative quarter-over-quarter summary data
  - `Core Platform Requests - Q1 2026.html` — generated reports
  - `Core Platform Requests - Q1 2026.pdf` — static PDF version for quick preview

## Step-by-step

### Step 1: Export the CSV

1. Open the #ai-core-platform-requests channel in Slack
2. Go to the Help Requests Tracker (list view)
3. Export as CSV
4. Save locally (e.g. `~/Downloads/tracker.csv`)

### Step 2: Download the history file

1. Go to the Google Drive folder (link above)
2. Download `metrics-history.json` to the same location as your CSV
3. If this is the first report, skip this step — the script creates the file

### Step 3: Run the script

```bash
# Clone the repo (first time only)
git clone https://github.com/sanandpa/AI-experiments.git
cd AI-experiments/skills/core-platform-requests-metrics

# Generate the report
python3 generate_report.py ~/Downloads/tracker.csv "Q2 2026" \
  --history ~/Downloads/metrics-history.json \
  --output ~/Downloads/Core-Platform-Requests-Q2-2026.html
```

This produces:
- An HTML report at the specified output path
- An updated `metrics-history.json` (in the same directory as the --history file,
  or current directory if --history was not provided)

### Step 4: Add AI analysis (optional but recommended)

The script generates a base report with all charts and drill-down tables.
The "Key Observations" section is left as a placeholder for an AI assistant
to fill in with fresh analysis.

**Using any AI assistant (Cursor, Claude Code, Gemini, etc.):**

Provide the AI with:
1. The generated HTML report
2. The metrics-history.json file (for trend comparison)
3. This instruction:

> Read the generated HTML metrics report and the metrics history file.
> Write a "Key Observations" section with 5-7 bullet points covering:
> - Dominant request types and what they signal
> - Closure rate assessment
> - Priority distribution and whether it looks calibrated
> - Assignee tracking gaps
> - Volume trends (growing, stable, declining)
> - Quarter-over-quarter changes (if history has prior quarters)
> - Any new patterns or anomalies
>
> Replace the placeholder in the HTML between the
> "Key Observations" section-title and the "Data Gaps" section-title
> with your analysis. Use the existing CSS classes:
> - `<li class="warn">` for concerns
> - `<li class="good">` for positive signals
> - `<li class="info">` for neutral observations

### Step 5: Upload to Google Drive

1. Upload the final HTML report to the Google Drive folder
2. Upload the updated `metrics-history.json`
3. (Optional) Open the HTML in a browser, print to PDF, and upload the PDF too

**About the HTML file on Google Drive:**
Google Drive does not render HTML files natively. Viewers need to download
the file and open it in their browser for the full interactive experience
(charts, drill-down tables). The PDF version provides a quick static preview
without downloading.

### Step 6: Update the Jira tracker

Add a comment to RHOAIENG-41749 noting that the quarterly report has been
generated and is available in the Google Drive folder.

## For Cursor users

You can use this as a Cursor skill:

```bash
cp -r skills/core-platform-requests-metrics ~/.cursor/skills/
```

Then in Cursor, say:
"Generate the core platform requests metrics report from [path to CSV]"

## What the script does

1. Parses the CSV and excludes test/dummy rows
2. Categorizes each request (PR review, Repo/fork, Access, Infra, Question, Handoff)
3. Computes metrics: volume, priority, categories, requesters, assignee tracking, status, handoffs
4. Generates an interactive HTML dashboard with Chart.js charts and drill-down detail tables
5. Updates the metrics history file with the current quarter's summary

## What the AI assistant adds

- Key Observations — freshly written based on the computed data
- Trend comparisons — if prior quarter data exists in the history file
- New recommendations — based on emerging patterns

## Report layout (consistent every quarter)

- Summary cards: total requests, closure rate, unique requesters, unassigned %, top category
- Charts: weekly trend, monthly bar, priority doughnut, category bars, priority trend (stacked), status doughnut, assignee tracking, top requesters
- Drill-down detail tables under each chart (expand on click)
- Handoffs from DevTestOps table
- Key Observations (AI-generated)
- Data Gaps
- Recommendations
