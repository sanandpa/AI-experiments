---
name: refinement-task
description: Creates a RHOAIENG platform refinement review Task for a given RHAISTRAT strategy issue. Replicates the AI Engineering org's standard process: fetches the RHAISTRAT feature name, builds the task from the standing template (RHOAIENG-50651), sets all standard fields and custom fields, and adds both issue links. Use when the user mentions a refinement task in any form — create, need, set up, open, new, or any phrasing involving "refinement task" or "refinement review" with a RHAISTRAT reference.
---

# Platform Refinement Task

## Invocation

User says something like:
- "Create a refinement task for RHAISTRAT-1309"
- "Need a refinement task for RHAISTRAT-XXXX"
- "New refinement review for RHAISTRAT-XXXX"
- "Refinement task for this — RHAISTRAT-XXXX"

Any mention of "refinement task" or "refinement review" with a RHAISTRAT
reference should trigger this skill.

## Component → Team name mapping

Use this mapping to resolve a Jira component to the team name used in
email drafts and the Team field reminder. Add new entries as teams adopt
this skill.

- **AI Core Platform** → AI Core Platform

If the user's component is not in the mapping, ask them for the team
name to use.

## Workflow

### Step 0 — Identify the component and team

Ask the user which component this refinement task is for. Present the
known components from the mapping above as options, plus an **Other**
option for unlisted components.

- If the user picks a mapped component → resolve the team name
  automatically and confirm it with the user (team names do not always
  match component names exactly).
- If the user picks "Other" → ask for both the component name and the
  team name.

### Step 1 — Fetch the RHAISTRAT issue

Call `jira_get_issue` with `issue_key: RHAISTRAT-XXXX`, fields: `summary`.
Extract the feature name from the summary field.

### Step 2 — Source the Refinement Document link

Call `jira_get_issue` with `issue_key: RHAISTRAT-XXXX`, fields: `*all`.

Search for a Google Docs URL (pattern: `https://docs.google.com/document/d/...`) across all of these in order:

1. Issue description
2. Comments
3. Issue links (scan the URL, summary, and title of every linked issue)

- If found → use it as the default, but confirm with the user in Step 3.
- If not found → ask the user:
  > "I couldn't find a Refinement Document link in RHAISTRAT-XXXX. Please share the Google Doc URL, or say 'skip' to leave it as a placeholder."

### Step 3 — Confirm before creating

Present the full proposed task to the user before taking any action:

```
Summary:        Platform refinement review [RHAISTRAT-XXXX] - <feature name>
Issue type:     Task
Project:        RHOAIENG
Component:      <selected component>
Priority:       Major
Assignee:       Unassigned
Labels:         (blank)
Sprint:         (none)
Story Points:   3  ← change? (default 3)
Activity Type:  New Features
Affects Testing:Testable
Blocked:        False
Blocked Reason: None
Ready:          False
Test Blocker:   No
Color Status:   Not Selected

Refinement Doc:       <URL found or provided>
Reviewer Guide link:  <ask: URL or "skip">

Description:
  Clone this template for platform refinement reviews.
  [Refinement Document for RHAISTRAT-XXXX|<refinement doc URL>]

Issue links:
  Clones       → RHOAIENG-50651
  Related to   → RHAISTRAT-XXXX
```

- The user may override **Story Points** or the **Refinement Doc URL**.
- Ask the user if they have a **Reviewer Guide link** to include.
  If provided, it will appear in the description. If skipped, that line
  is omitted.
- Wait for explicit confirmation ("go", "yes", "create it").

### Step 4 — Create the task

Call `jira_create_issue` with:

- `project_key`: RHOAIENG
- `issue_type`: Task
- `summary`: `Platform refinement review [RHAISTRAT-XXXX] - <feature name>`
- `components`: <selected component>
- `description` (Jira wiki markup):

If a reviewer guide link was provided:
```
Clone this template for platform refinement reviews. The guide for those [reviewing|<reviewer guide URL>].

[Refinement Document for RHAISTRAT-XXXX|<refinement doc URL>]
```

If no reviewer guide link:
```
Clone this template for platform refinement reviews.

[Refinement Document for RHAISTRAT-XXXX|<refinement doc URL>]
```

- `additional_fields`:
```json
{
  "priority": {"name": "Major"},
  "customfield_10464": {"value": "New Features"},
  "customfield_10489": [{"value": "Testable"}],
  "customfield_10028": <story_points>,
  "customfield_10483": "None",
  "customfield_10484": {"value": "False"},
  "customfield_10517": {"value": "False"},
  "customfield_10822": {"value": "No"},
  "customfield_10712": {"value": "Not Selected"}
}
```

### Step 5 — Add issue links

After the task is created, make two `jira_create_issue_link` calls:

1. `link_type: Cloners`, `inward_issue_key: <new key>`, `outward_issue_key: RHOAIENG-50651`
2. `link_type: Related`, `inward_issue_key: RHAISTRAT-XXXX`, `outward_issue_key: <new key>`

### Step 6 — Report back

Reply with:
```
Created [RHOAIENG-XXXXX](https://redhat.atlassian.net/browse/RHOAIENG-XXXXX)
- Clones RHOAIENG-50651
- Related to RHAISTRAT-XXXX
```

### Step 7 — Draft email to forward to the team

After reporting back, provide an email draft the user can forward to
the team. Use this template:

```
Refinement task created: [RHOAIENG-XXXXX](https://redhat.atlassian.net/browse/RHOAIENG-XXXXX)

If there's no work expected from <team name> on this one, please
update your sign-off in the refinement document and move the task
to Resolved. Otherwise, flag it.

Refinement doc: [link](<refinement doc URL>)
```

- Use the actual Jira key, team name, and refinement doc URL from earlier steps.
- Show the draft and wait for review before the user sends it.

## Custom field reference

- **customfield_10464** — Activity Type → New Features
- **customfield_10489** — Affects Testing → Testable
- **customfield_10028** — Story Points → 3 (default; user may override)
- **customfield_10483** — Blocked Reason → None
- **customfield_10484** — Ready → False
- **customfield_10517** — Blocked → False
- **customfield_10822** — Test Blocker → No
- **customfield_10712** — Color Status → Not Selected

## Notes

- Template issue: RHOAIENG-50651 (`[Template] - Platform refinement review [STRATLINK]`) — used for all teams
- Assignee and Label are left blank at creation — set them later when known
- If a Recording link is available, append it to the description:
  `[Refinement Recording|<google drive URL>]`
- **Team field limitation:** The Team field (customfield_10001, type: atlassian-team)
  cannot be set via the MCP Jira API — it requires a team ID that the tool does not
  resolve. After creating the task, remind the user to set the Team field manually
  to "<team name>" on the ticket.
