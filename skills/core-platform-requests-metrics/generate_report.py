#!/usr/bin/env python3
"""
Core Platform Requests Metrics Report Generator

Generates an interactive HTML dashboard from a Slack Help Requests Tracker CSV export.
No external dependencies beyond Python 3 standard library — Chart.js is loaded via CDN.

Usage:
    python3 generate_report.py <csv_path> <quarter_label> [--history <history_json_path>] [--output <output_path>]

Examples:
    python3 generate_report.py tracker.csv "Q1 2026"
    python3 generate_report.py tracker.csv "Q2 2026" --history metrics-history.json
    python3 generate_report.py tracker.csv "Q1 2026" --output ~/Downloads/report.html
"""

import argparse
import csv
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta

# --- Configuration ---

TEST_TITLES = {'test req', 'test request', 'test time travel', ''}
TEST_KEYWORDS = ['tzag channel champion']

MANUAL_CATEGORY_OVERRIDES = {
    "Can anyone help review these two MaaS PRs? We're targeting merge by April 3rd (ODH code freeze)": "PR review / merge",
    "Can anyone help review this MaaS PR? We're targeting merge by April 3rd (ODH code freeze)": "PR review / merge",
    "Can anyone help review this PR ?": "PR review / merge",
    "Information Request - What's happening in 3.4 for Dashboard URL?": "Information / process question",
    "Request to provide access to https://quay.io/repository/opendatahub/spark-operator": "Access / permissions",
    "Request for Quay Credentials (AIPCC) for GitHub Workflow \u2013 Hermetic Build Support (RHOAI)": "Access / permissions",
    "GitHub Actions ODH Org Help": "Infrastructure / config",
    "Requesting new repo in ODH Quay org": "Repo / fork creation",
    "Infrastructure": "Repo / fork creation",
    "Make GHCR packages public": "Access / permissions",
    "RHDS Team for Llama Stack": "Access / permissions",
    "3.3 RC1 DfFIPS": "Infrastructure / config",
    "Request to make changes in MaaS gateway configuration in test automation": "Infrastructure / config",
    "Maas auth polices alignment #3350": "PR review / merge",
    "Code review needed": "PR review / merge",
    "OpenCode PoC": "Repo / fork creation",
    "Set production image and tag for IMAGES_PIPELINES_COMPONENTS": "Infrastructure / config",
}

CATEGORY_ORDER = [
    'PR review / merge',
    'Access / permissions',
    'Repo / fork creation',
    'Information / process question',
    'Infrastructure / config',
    'Handoff from DevTestOps',
]

CATEGORY_CHART_LABELS = ['PR review', 'Access', 'Repo/fork', 'Questions', 'Infra', 'Handoff']


# --- Data Processing ---

def parse_date(ds):
    ds = ds.strip()
    if not ds:
        return None
    try:
        return datetime.strptime(ds, '%m/%d/%y, %I:%M %p')
    except ValueError:
        return None


def is_test_row(title, details):
    if title.lower() in TEST_TITLES:
        return True
    if any(kw in title.lower() for kw in TEST_KEYWORDS):
        return True
    if title == '' and details == '':
        return True
    return False


def categorize(title, details):
    if title in MANUAL_CATEGORY_OVERRIDES:
        return MANUAL_CATEGORY_OVERRIDES[title]

    t = (title + ' ' + details).lower()

    if 'handoff' in t or 'received from' in t or 'redirected from' in t:
        return 'Handoff from DevTestOps'
    if any(kw in t for kw in [
        'pr review', 'pr request', 'review request', 'review and merge',
        'review and approve', 'need pr', 'merge pr', 'pr help',
        'code review', 'help with merging', 'review here',
        'requesting pr review', 'review on', 'can i get a review',
        'help landing', 'review needed', 'review for', 'reviewed+merged',
    ]):
        return 'PR review / merge'
    if any(kw in t for kw in [
        'fork', 'new repo', 'create a new repo', 'repo for',
        'midstream repo', 'repo setup', 'new repository',
    ]):
        return 'Repo / fork creation'
    if any(kw in t for kw in [
        'access', 'permission', 'credential', 'quay robot',
        'quay credential', 'pat', 'secret', 'codeowner',
        'approver', 'add this user', 'added as',
    ]):
        return 'Access / permissions'
    if any(kw in t for kw in [
        'question', 'understand', 'how do', 'how to', 'what is',
        'information request', 'process', 'onboarding',
        'what should i do', 'is it intentional',
    ]):
        return 'Information / process question'
    if any(kw in t for kw in [
        'infrastructure', 'github actions', 'konflux', 'operator',
        'imagestream', 'configmap', 'cluster', 'disconnected',
        'dashboard', 'manifest', 'param', 'gateway', 'component',
        'github workflow', 'hermetic build', 'reconcil',
    ]):
        return 'Infrastructure / config'
    return 'Other'


def load_csv(csv_path):
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        return list(reader)


def clean_and_enrich(rows):
    clean = []
    for row in rows:
        title = row.get('Request', '').strip()
        details = row.get('Details', '').strip()
        if is_test_row(title, details):
            continue
        row['_title'] = title
        row['_details'] = details
        row['_date'] = parse_date(row.get('Date submitted', ''))
        row['_priority'] = row.get('Priority', '').strip()
        row['_status'] = row.get('Status', '').strip()
        row['_submitter'] = row.get('Submitted by', '').strip().replace('@redhat.com', '')
        row['_assignee'] = row.get('Assignee', '').strip().replace('@redhat.com', '')
        row['_category'] = categorize(title, details)
        clean.append(row)
    return clean


def compute_metrics(clean):
    m = {}
    m['total'] = len(clean)

    # Status
    statuses = Counter(r['_status'] for r in clean)
    m['done'] = statuses.get('Done', 0)
    m['in_progress'] = statuses.get('In progress', 0)
    m['other_status'] = m['total'] - m['done'] - m['in_progress']
    m['closure_rate'] = round(m['done'] / m['total'] * 100) if m['total'] > 0 else 0

    # Priority
    priorities = Counter(r['_priority'] for r in clean)
    m['high'] = priorities.get('High', 0)
    m['medium'] = priorities.get('Medium', 0)
    m['low'] = priorities.get('Low', 0)

    # Assignee tracking
    m['assigned'] = sum(1 for r in clean if r['_assignee'])
    m['unassigned'] = m['total'] - m['assigned']
    m['unassigned_pct'] = round(m['unassigned'] / m['total'] * 100) if m['total'] > 0 else 0

    # Unique requesters
    all_requesters = Counter(r['_submitter'] for r in clean if r['_submitter'])
    m['unique_requesters'] = len(all_requesters)
    m['repeat_requesters'] = sum(1 for v in all_requesters.values() if v > 1)

    # Categories
    cats = Counter(r['_category'] for r in clean)
    m['categories'] = {c: cats.get(c, 0) for c in CATEGORY_ORDER}
    m['categories']['Other'] = cats.get('Other', 0)
    top_cat = cats.most_common(1)
    m['top_category'] = top_cat[0][0] if top_cat else 'N/A'
    m['top_category_pct'] = round(top_cat[0][1] / m['total'] * 100) if top_cat and m['total'] > 0 else 0

    # Monthly
    months = Counter()
    for r in clean:
        if r['_date']:
            months[r['_date'].strftime('%Y-%m')] += 1
    m['months'] = dict(sorted(months.items()))

    # Monthly priority
    mp = defaultdict(lambda: Counter())
    for r in clean:
        if r['_date']:
            mo = r['_date'].strftime('%Y-%m')
            mp[mo][r['_priority']] += 1
    m['monthly_priority'] = {k: dict(v) for k, v in sorted(mp.items())}

    # Weekly
    week_agg = {}
    for r in clean:
        if r['_date']:
            ws = r['_date'] - timedelta(days=r['_date'].weekday())
            key = ws.strftime('%Y-%m-%d')
            if key not in week_agg:
                week_agg[key] = {'label': ws.strftime('%b %d'), 'count': 0}
            week_agg[key]['count'] += 1
    m['weeks'] = [week_agg[k] for k in sorted(week_agg.keys())]

    # Top requesters
    m['top_requesters'] = all_requesters.most_common(10)

    # Handoffs
    m['handoffs'] = [r for r in clean if r['_category'] == 'Handoff from DevTestOps']

    return m


# --- History ---

def update_history(history_path, quarter_label, metrics):
    history = []
    if history_path and os.path.exists(history_path):
        with open(history_path, 'r') as f:
            history = json.load(f)

    entry = {
        'quarter': quarter_label,
        'generated': datetime.now().isoformat(),
        'total': metrics['total'],
        'done': metrics['done'],
        'closure_rate': metrics['closure_rate'],
        'high': metrics['high'],
        'medium': metrics['medium'],
        'low': metrics['low'],
        'assigned': metrics['assigned'],
        'unassigned': metrics['unassigned'],
        'unique_requesters': metrics['unique_requesters'],
        'categories': metrics['categories'],
    }

    existing = [i for i, h in enumerate(history) if h['quarter'] == quarter_label]
    if existing:
        history[existing[0]] = entry
    else:
        history.append(entry)

    out_path = history_path if history_path else 'metrics-history.json'
    with open(out_path, 'w') as f:
        json.dump(history, f, indent=2)
    return out_path


# --- HTML Generation ---

def js_escape(s):
    return s.replace('\\', '\\\\').replace('"', '\\"').replace("'", "\\'").replace('\n', ' ')


def build_js_requests(clean):
    items = []
    for r in clean:
        t = js_escape(r['_title'])
        items.append(
            f'  {{t:"{t}",p:"{r["_priority"]}",s:"{r["_status"]}",'
            f'by:"{r["_submitter"]}",a:"{r["_assignee"]}",c:"{r["_category"]}"}}'
        )
    return ',\n'.join(items)


def month_label(ym):
    try:
        d = datetime.strptime(ym, '%Y-%m')
        return d.strftime('%b')
    except ValueError:
        return ym


def generate_html(quarter_label, metrics, clean):
    total = metrics['total']
    month_labels = [month_label(m) for m in metrics['months'].keys()]
    month_data = list(metrics['months'].values())

    if month_labels and len(month_labels) > 0:
        month_labels[-1] = month_labels[-1] + ' (partial)'

    week_labels = [w['label'] for w in metrics['weeks']]
    week_data = [w['count'] for w in metrics['weeks']]

    cat_data = [metrics['categories'].get(c, 0) for c in CATEGORY_ORDER]

    sorted_months = sorted(metrics['monthly_priority'].keys())
    mp_high = [metrics['monthly_priority'].get(m, {}).get('High', 0) for m in sorted_months]
    mp_med = [metrics['monthly_priority'].get(m, {}).get('Medium', 0) for m in sorted_months]
    mp_low = [metrics['monthly_priority'].get(m, {}).get('Low', 0) for m in sorted_months]
    mp_labels = [month_label(m) for m in sorted_months]

    req_labels = [r[0] for r in metrics['top_requesters']]
    req_data = [r[1] for r in metrics['top_requesters']]

    handoff_rows = ''
    for h in metrics['handoffs']:
        pcls = 'high' if h['_priority'] == 'High' else ('medium' if h['_priority'] == 'Medium' else 'low')
        scls = 'done' if h['_status'] == 'Done' else ('progress' if h['_status'] == 'In progress' else 'backlog')
        handoff_rows += (
            f'<tr><td>{h["_title"]}</td>'
            f'<td><span class="priority-badge {pcls}">{h["_priority"]}</span></td>'
            f'<td>{h["_submitter"]}</td>'
            f'<td><span class="status-badge {scls}">{h["_status"] or "New"}</span></td></tr>\n'
        )

    js_requests = build_js_requests(clean)

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI Core Platform Requests Channel \u2014 {quarter_label} Metrics</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js"></script>
<style>
  :root {{
    --bg: #0f1117; --surface: #1a1d27; --surface2: #242734; --border: #2e3144;
    --text: #e1e4ed; --text-muted: #8b8fa3;
    --accent: #6c8cff; --accent2: #44d7b6; --accent3: #f7768e;
    --accent4: #e0af68; --accent5: #bb9af7; --accent6: #7dcfff;
  }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: var(--bg); color: var(--text); line-height: 1.6; }}
  .header {{ padding: 2.5rem 2rem 1.5rem; max-width: 1280px; margin: 0 auto; }}
  .header h1 {{ font-size: 1.75rem; font-weight: 700; margin-bottom: 0.25rem; }}
  .header p {{ color: var(--text-muted); font-size: 0.9rem; }}
  .dashboard {{ max-width: 1280px; margin: 0 auto; padding: 0 2rem 3rem; }}
  .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 1rem; margin-bottom: 2rem; }}
  .card {{ background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 1.25rem; }}
  .card .label {{ font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-muted); margin-bottom: 0.5rem; }}
  .card .value {{ font-size: 2rem; font-weight: 700; }}
  .card .sub {{ font-size: 0.8rem; color: var(--text-muted); margin-top: 0.25rem; }}
  .card .value.green {{ color: var(--accent2); }} .card .value.blue {{ color: var(--accent); }}
  .card .value.red {{ color: var(--accent3); }} .card .value.yellow {{ color: var(--accent4); }}
  .card .value.purple {{ color: var(--accent5); }}
  .grid {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 1.5rem; margin-bottom: 1.5rem; }}
  .grid.full {{ grid-template-columns: 1fr; }}
  .panel {{ background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 1.5rem; }}
  .panel h2 {{ font-size: 1rem; font-weight: 600; margin-bottom: 1rem; color: var(--text); }}
  .chart-container {{ position: relative; width: 100%; }}
  .chart-container.tall {{ height: 320px; }} .chart-container.short {{ height: 260px; }} .chart-container.medium {{ height: 300px; }}
  .section-title {{ font-size: 1.15rem; font-weight: 700; margin: 2.5rem 0 1rem; padding-bottom: 0.5rem; border-bottom: 1px solid var(--border); }}
  .insight-list {{ list-style: none; padding: 0; }}
  .insight-list li {{ padding: 0.75rem 1rem; border-left: 3px solid var(--accent); background: var(--surface2); border-radius: 0 8px 8px 0; margin-bottom: 0.5rem; font-size: 0.9rem; line-height: 1.5; }}
  .insight-list li.warn {{ border-left-color: var(--accent4); }}
  .insight-list li.good {{ border-left-color: var(--accent2); }}
  .insight-list li.info {{ border-left-color: var(--accent6); }}
  .rec-list {{ list-style: none; padding: 0; counter-reset: rec; }}
  .rec-list li {{ counter-increment: rec; padding: 1rem 1rem 1rem 3rem; background: var(--surface2); border-radius: 8px; margin-bottom: 0.5rem; font-size: 0.9rem; position: relative; }}
  .rec-list li::before {{ content: counter(rec); position: absolute; left: 1rem; top: 1rem; width: 1.5rem; height: 1.5rem; background: var(--accent); color: var(--bg); border-radius: 50%; font-size: 0.75rem; font-weight: 700; display: flex; align-items: center; justify-content: center; }}
  .rec-list li strong {{ color: var(--accent); }}
  .gap-box {{ background: var(--surface2); border: 1px dashed var(--accent3); border-radius: 8px; padding: 1.25rem; margin-bottom: 1rem; }}
  .gap-box h3 {{ color: var(--accent3); font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.5rem; }}
  .gap-box p {{ font-size: 0.9rem; color: var(--text-muted); }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.85rem; }}
  th {{ text-align: left; padding: 0.6rem 0.75rem; border-bottom: 2px solid var(--border); color: var(--text-muted); font-weight: 600; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.04em; }}
  td {{ padding: 0.5rem 0.75rem; border-bottom: 1px solid var(--border); }}
  .toggle-link {{ display: inline-block; margin-top: 0.75rem; color: var(--accent); font-size: 0.85rem; cursor: pointer; user-select: none; text-decoration: none; border-bottom: 1px dashed var(--accent); }}
  .toggle-link:hover {{ color: var(--accent6); border-color: var(--accent6); }}
  .toggle-link::before {{ content: '+ '; font-weight: 700; }}
  .toggle-link.open::before {{ content: '- '; }}
  .detail-table {{ display: none; margin-top: 0.75rem; }}
  .detail-table.open {{ display: block; }}
  .detail-table table {{ font-size: 0.8rem; }}
  .detail-table td {{ color: var(--text-muted); }}
  .detail-table td:first-child {{ color: var(--text); }}
  .priority-badge {{ display: inline-block; padding: 0.1rem 0.5rem; border-radius: 4px; font-size: 0.7rem; font-weight: 600; text-transform: uppercase; }}
  .priority-badge.high {{ background: #f7768e30; color: var(--accent3); }}
  .priority-badge.medium {{ background: #e0af6830; color: var(--accent4); }}
  .priority-badge.low {{ background: #7dcfff30; color: var(--accent6); }}
  .status-badge {{ display: inline-block; padding: 0.1rem 0.5rem; border-radius: 4px; font-size: 0.7rem; font-weight: 600; }}
  .status-badge.done {{ background: #44d7b630; color: var(--accent2); }}
  .status-badge.progress {{ background: #e0af6830; color: var(--accent4); }}
  .status-badge.backlog {{ background: #8b8fa330; color: var(--text-muted); }}
  .handoff-note {{ background: var(--surface2); border: 1px dashed var(--accent4); border-radius: 8px; padding: 0.75rem 1rem; margin-top: 0.75rem; font-size: 0.85rem; color: var(--text-muted); }}
  @media (max-width: 768px) {{ .grid {{ grid-template-columns: 1fr; }} .cards {{ grid-template-columns: repeat(2, 1fr); }} .header, .dashboard {{ padding-left: 1rem; padding-right: 1rem; }} }}
</style>
</head>
<body>
<div class="header">
  <h1>AI Core Platform Requests Channel</h1>
  <p>Quarterly Metrics Report \u2014 {quarter_label}</p>
</div>
<div class="dashboard">

  <div class="cards">
    <div class="card"><div class="label">Total Requests</div><div class="value blue">{total}</div><div class="sub">After excluding test data</div></div>
    <div class="card"><div class="label">Closure Rate</div><div class="value green">{metrics['closure_rate']}%</div><div class="sub">{metrics['done']} of {total} resolved</div></div>
    <div class="card"><div class="label">Unique Requesters</div><div class="value purple">{metrics['unique_requesters']}</div><div class="sub">{metrics['repeat_requesters']} repeat requesters</div></div>
    <div class="card"><div class="label">Unassigned</div><div class="value red">{metrics['unassigned_pct']}%</div><div class="sub">{metrics['unassigned']} of {total} requests</div></div>
    <div class="card"><div class="label">Top Category</div><div class="value yellow">{metrics['top_category_pct']}%</div><div class="sub">{metrics['top_category']}</div></div>
  </div>

  <div class="grid">
    <div class="panel"><h2>Requests by Week</h2><div class="chart-container tall"><canvas id="weeklyChart"></canvas></div></div>
    <div class="panel"><h2>Requests by Month</h2><div class="chart-container tall"><canvas id="monthlyChart"></canvas></div></div>
  </div>

  <div class="grid">
    <div class="panel">
      <h2>Priority Breakdown</h2><div class="chart-container short"><canvas id="priorityChart"></canvas></div>
      <a class="toggle-link" onclick="toggleDetail('priority-detail', this)">View all {total} requests by priority</a>
      <div class="detail-table" id="priority-detail"><table><thead><tr><th>Request</th><th>Priority</th><th>Status</th><th>Submitted by</th></tr></thead><tbody id="priority-detail-body"></tbody></table></div>
    </div>
    <div class="panel">
      <h2>Request Categories</h2><div class="chart-container short"><canvas id="categoryChart"></canvas></div>
      <a class="toggle-link" onclick="toggleDetail('category-detail', this)">View all requests by category</a>
      <div class="detail-table" id="category-detail"><div id="category-detail-body"></div></div>
    </div>
  </div>

  <div class="grid">
    <div class="panel"><h2>Priority Trend by Month</h2><div class="chart-container short"><canvas id="priorityTrendChart"></canvas></div></div>
    <div class="panel">
      <h2>Request Status</h2><div class="chart-container short"><canvas id="statusChart"></canvas></div>
      <a class="toggle-link" onclick="toggleDetail('status-detail', this)">View In Progress and open requests</a>
      <div class="detail-table" id="status-detail"><table><thead><tr><th>Request</th><th>Priority</th><th>Status</th><th>Assignee</th></tr></thead><tbody id="status-detail-body"></tbody></table></div>
    </div>
  </div>

  <div class="grid">
    <div class="panel">
      <h2>Assignee Tracking</h2><div class="chart-container medium"><canvas id="assigneeChart"></canvas></div>
      <a class="toggle-link" onclick="toggleDetail('assignee-detail', this)">View the {metrics['unassigned']} unassigned requests</a>
      <div class="detail-table" id="assignee-detail"><div id="assignee-detail-body"></div></div>
    </div>
    <div class="panel">
      <h2>Top Requesters</h2><div class="chart-container medium"><canvas id="requesterChart"></canvas></div>
      <a class="toggle-link" onclick="toggleDetail('requester-detail', this)">View requests per requester</a>
      <div class="detail-table" id="requester-detail"><div id="requester-detail-body"></div></div>
    </div>
  </div>

  <div class="grid full">
    <div class="panel">
      <h2>Handoffs from DevTestOps ({len(metrics['handoffs'])})</h2>
      <div class="table-wrap"><table><thead><tr><th>Request</th><th>Priority</th><th>Submitted by</th><th>Status</th></tr></thead><tbody>
        {handoff_rows}
      </tbody></table></div>
      <div class="handoff-note"><strong>Note:</strong> Review whether all handoffs correctly belonged to Core Platform or if some should have remained with DevTestOps.</div>
    </div>
  </div>

  <!-- AI ANALYSIS PLACEHOLDER: An AI assistant will inject observations, trends, and recommendations here -->
  <h2 class="section-title">Key Observations</h2>
  <p style="color:var(--text-muted);font-size:0.9rem;padding:1rem;background:var(--surface2);border-radius:8px;">
    This section is populated by an AI assistant after the base report is generated.
    Run the report through your preferred AI tool with INSTRUCTIONS.md for analysis.
  </p>

  <h2 class="section-title">Data Gaps</h2>
  <div class="gap-box"><h3>Acknowledgment Time</h3><p>No timestamp for when the CC first responded. Cannot measure time-to-first-response or SLO compliance.</p></div>
  <div class="gap-box"><h3>Resolution Time</h3><p>No "Date Resolved" field in the tracker. The data exists in ticket comment threads but is not exported. Without this, we can measure <em>what</em> gets done but not <em>how fast</em>.</p></div>

  <h2 class="section-title">Recommendations</h2>
  <ol class="rec-list">
    <li><strong>Add a "Date Resolved" column</strong> to the tracker. The CC fills it when moving a request to Done. Enables resolution time tracking for the next quarter.</li>
    <li><strong>Add a "Category" dropdown</strong> (PR review, Repo/fork, Access, Infra, Question, Handoff). Eliminates manual derivation for future reports.</li>
    <li><strong>Address the {metrics['unassigned_pct']}% unassigned rate.</strong> Enforce assignee updates in the CC workflow, or accept ad-hoc handling and adjust expectations.</li>
    <li><strong>Tackle PR review volume.</strong> Consider a dedicated review queue, CODEOWNERS process, or encouraging teams to tag reviewers directly via GitHub.</li>
    <li><strong>Document common questions.</strong> Information/process requests point to documentation gaps. Add common topics to the NotebookLM knowledge base.</li>
    <li><strong>Review priority calibration.</strong> Add guidance on when to use High vs Medium vs Low so the label carries real signal.</li>
    <li><strong>Clarify cross-channel handoff criteria</strong> with DevTestOps. Review handoffs to confirm which were correctly routed.</li>
  </ol>
</div>

<script>
const colors = {{blue:'#6c8cff',green:'#44d7b6',red:'#f7768e',yellow:'#e0af68',purple:'#bb9af7',cyan:'#7dcfff',muted:'#8b8fa3',grid:'#2e3144'}};
const allRequests = [
{js_requests}
];
const categoryOrder = {json.dumps(CATEGORY_ORDER)};
const categoryColors = {{'PR review / merge':colors.blue,'Access / permissions':colors.green,'Repo / fork creation':colors.purple,'Information / process question':colors.yellow,'Infrastructure / config':colors.cyan,'Handoff from DevTestOps':colors.muted}};

function priorityBadge(p){{const c=p==='High'?'high':p==='Medium'?'medium':'low';return `<span class="priority-badge ${{c}}">${{p}}</span>`;}}
function statusBadge(s){{const c=s==='Done'?'done':s==='In progress'?'progress':'backlog';return `<span class="status-badge ${{c}}">${{s||'New'}}</span>`;}}
function toggleDetail(id,el){{document.getElementById(id).classList.toggle('open');el.classList.toggle('open');}}

(function(){{const b=document.getElementById('priority-detail-body');let h='';['High','Medium','Low'].forEach(p=>{{allRequests.filter(r=>r.p===p).forEach(r=>{{h+=`<tr><td>${{r.t}}</td><td>${{priorityBadge(r.p)}}</td><td>${{statusBadge(r.s)}}</td><td>${{r.by}}</td></tr>`;}});}});b.innerHTML=h;}})();

(function(){{const c=document.getElementById('category-detail-body');let h='';categoryOrder.forEach(cat=>{{const items=allRequests.filter(r=>r.c===cat);if(!items.length)return;h+=`<div style="margin-bottom:1rem;"><div style="font-size:0.85rem;font-weight:600;color:${{categoryColors[cat]}};margin-bottom:0.4rem;">${{cat}} (${{items.length}})</div><table><thead><tr><th>Request</th><th>Priority</th><th>Status</th><th>Assignee</th></tr></thead><tbody>`;items.forEach(r=>{{h+=`<tr><td>${{r.t}}</td><td>${{priorityBadge(r.p)}}</td><td>${{statusBadge(r.s)}}</td><td>${{r.a||'\\u2014'}}</td></tr>`;}});h+=`</tbody></table></div>`;}});c.innerHTML=h;}})();

(function(){{const b=document.getElementById('status-detail-body');let h='';allRequests.filter(r=>r.s!=='Done').forEach(r=>{{h+=`<tr><td>${{r.t}}</td><td>${{priorityBadge(r.p)}}</td><td>${{statusBadge(r.s)}}</td><td>${{r.a||'\\u2014'}}</td></tr>`;}});b.innerHTML=h;}})();

(function(){{const c=document.getElementById('assignee-detail-body');const u=allRequests.filter(r=>!r.a);let h=`<table><thead><tr><th>Request</th><th>Priority</th><th>Status</th><th>Submitted by</th><th>Category</th></tr></thead><tbody>`;u.forEach(r=>{{h+=`<tr><td>${{r.t}}</td><td>${{priorityBadge(r.p)}}</td><td>${{statusBadge(r.s)}}</td><td>${{r.by}}</td><td style="color:${{categoryColors[r.c]||colors.muted}};font-size:0.75rem;">${{r.c}}</td></tr>`;}});h+=`</tbody></table>`;c.innerHTML=h;}})();

(function(){{const c=document.getElementById('requester-detail-body');const g={{}};allRequests.forEach(r=>{{if(!g[r.by])g[r.by]=[];g[r.by].push(r);}});const s=Object.entries(g).sort((a,b)=>b[1].length-a[1].length).slice(0,11);let h='';s.forEach(([n,items])=>{{h+=`<div style="margin-bottom:1rem;"><div style="font-size:0.85rem;font-weight:600;color:${{colors.purple}};margin-bottom:0.4rem;">${{n}} (${{items.length}})</div><table><thead><tr><th>Request</th><th>Priority</th><th>Status</th><th>Category</th></tr></thead><tbody>`;items.forEach(r=>{{h+=`<tr><td>${{r.t}}</td><td>${{priorityBadge(r.p)}}</td><td>${{statusBadge(r.s)}}</td><td style="color:${{categoryColors[r.c]||colors.muted}};font-size:0.75rem;">${{r.c}}</td></tr>`;}});h+=`</tbody></table></div>`;}});c.innerHTML=h;}})();

const defaultOptions={{responsive:true,maintainAspectRatio:false,plugins:{{legend:{{labels:{{color:colors.muted,font:{{size:12}}}}}}}},scales:{{x:{{ticks:{{color:colors.muted,font:{{size:11}}}},grid:{{color:colors.grid}}}},y:{{ticks:{{color:colors.muted,font:{{size:11}}}},grid:{{color:colors.grid}}}}}}}};

new Chart(document.getElementById('weeklyChart'),{{type:'line',data:{{labels:{json.dumps(week_labels)},datasets:[{{label:'Requests',data:{json.dumps(week_data)},borderColor:colors.blue,backgroundColor:colors.blue+'20',fill:true,tension:0.3,pointRadius:4,pointBackgroundColor:colors.blue}}]}},options:{{...defaultOptions,plugins:{{legend:{{display:false}}}}}}}});

new Chart(document.getElementById('monthlyChart'),{{type:'bar',data:{{labels:{json.dumps(month_labels)},datasets:[{{label:'Requests',data:{json.dumps(month_data)},backgroundColor:colors.blue+'90',borderRadius:6}}]}},options:{{...defaultOptions,plugins:{{legend:{{display:false}}}}}}}});

new Chart(document.getElementById('priorityChart'),{{type:'doughnut',data:{{labels:['High ({metrics["high"]})','Medium ({metrics["medium"]})','Low ({metrics["low"]})'],datasets:[{{data:[{metrics['high']},{metrics['medium']},{metrics['low']}],backgroundColor:[colors.red,colors.yellow,colors.cyan],borderWidth:0,spacing:2}}]}},options:{{responsive:true,maintainAspectRatio:false,cutout:'60%',plugins:{{legend:{{position:'right',labels:{{color:colors.muted,font:{{size:12}},padding:12}}}}}}}}}});

new Chart(document.getElementById('categoryChart'),{{type:'bar',data:{{labels:{json.dumps(CATEGORY_CHART_LABELS)},datasets:[{{data:{json.dumps(cat_data)},backgroundColor:[colors.blue,colors.green,colors.purple,colors.yellow,colors.cyan,colors.muted],borderRadius:6}}]}},options:{{...defaultOptions,indexAxis:'y',plugins:{{legend:{{display:false}}}}}}}});

new Chart(document.getElementById('priorityTrendChart'),{{type:'bar',data:{{labels:{json.dumps(mp_labels)},datasets:[{{label:'High',data:{json.dumps(mp_high)},backgroundColor:colors.red,borderRadius:4}},{{label:'Medium',data:{json.dumps(mp_med)},backgroundColor:colors.yellow,borderRadius:4}},{{label:'Low',data:{json.dumps(mp_low)},backgroundColor:colors.cyan,borderRadius:4}}]}},options:{{...defaultOptions,scales:{{...defaultOptions.scales,x:{{...defaultOptions.scales.x,stacked:true}},y:{{...defaultOptions.scales.y,stacked:true}}}},plugins:{{legend:{{labels:{{color:colors.muted,font:{{size:11}}}}}}}}}}}});

new Chart(document.getElementById('statusChart'),{{type:'doughnut',data:{{labels:['Done ({metrics["done"]})','In Progress ({metrics["in_progress"]})','Other ({metrics["other_status"]})'],datasets:[{{data:[{metrics['done']},{metrics['in_progress']},{metrics['other_status']}],backgroundColor:[colors.green,colors.yellow,colors.muted],borderWidth:0,spacing:2}}]}},options:{{responsive:true,maintainAspectRatio:false,cutout:'60%',plugins:{{legend:{{position:'right',labels:{{color:colors.muted,font:{{size:12}},padding:12}}}}}}}}}});

new Chart(document.getElementById('assigneeChart'),{{type:'doughnut',data:{{labels:['Assigned ({metrics["assigned"]})','Unassigned ({metrics["unassigned"]})'],datasets:[{{data:[{metrics['assigned']},{metrics['unassigned']}],backgroundColor:[colors.green,colors.red+'80'],borderWidth:0,spacing:2}}]}},options:{{responsive:true,maintainAspectRatio:false,cutout:'60%',plugins:{{legend:{{position:'right',labels:{{color:colors.muted,font:{{size:12}},padding:12}}}}}}}}}});

new Chart(document.getElementById('requesterChart'),{{type:'bar',data:{{labels:{json.dumps(req_labels)},datasets:[{{data:{json.dumps(req_data)},backgroundColor:colors.purple+'90',borderRadius:6}}]}},options:{{...defaultOptions,indexAxis:'y',plugins:{{legend:{{display:false}}}}}}}});
</script>
</body>
</html>'''
    return html


# --- Main ---

def main():
    parser = argparse.ArgumentParser(
        description='Generate Core Platform Requests Metrics Report'
    )
    parser.add_argument('csv_path', help='Path to the CSV export from Slack Help Requests Tracker')
    parser.add_argument('quarter', help='Quarter label, e.g. "Q1 2026"')
    parser.add_argument('--history', help='Path to metrics-history.json (optional, for trend tracking)')
    parser.add_argument('--output', help='Output path for the HTML report (default: auto-generated)')
    args = parser.parse_args()

    print(f'Loading CSV from {args.csv_path}...')
    rows = load_csv(args.csv_path)
    print(f'  {len(rows)} rows loaded')

    clean = clean_and_enrich(rows)
    print(f'  {len(clean)} requests after cleanup')

    metrics = compute_metrics(clean)
    print(f'  {metrics["total"]} total | {metrics["done"]} done | {metrics["closure_rate"]}% closure rate')

    html = generate_html(args.quarter, metrics, clean)

    output_path = args.output
    if not output_path:
        safe_quarter = args.quarter.replace(' ', '-')
        output_path = f'Core-Platform-Requests-{safe_quarter}.html'

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f'\nReport generated: {output_path}')

    if args.history:
        hist_path = update_history(args.history, args.quarter, metrics)
        print(f'History updated: {hist_path}')
    else:
        hist_path = update_history(None, args.quarter, metrics)
        print(f'History created: {hist_path}')

    print('\nDone. Open the HTML file in a browser to view the interactive dashboard.')


if __name__ == '__main__':
    main()
