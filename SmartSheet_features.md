### Overview

Smartsheet is a cloud-based work management tool that feels like a spreadsheet but adds strong **project management**, **automation**, and **collaboration** features. Think of it as “Excel + Trello + lightweight MS Project” in one place.

Below are the key features for project management, grouped so you can map them to how you actually run projects.

---

### 1. Core Structure: Sheets, Views, and Hierarchy

- **Sheets (where work lives)**  
  - Each project is usually a **sheet** with rows = tasks, columns = task properties.  
  - Common columns: `Task Name`, `Start Date`, `End Date`, `Duration`, `Assigned To`, `Status`, `% Complete`, `Predecessors` (dependencies).

- **Multiple views of the same data**  
  Smartsheet lets you switch how you look at the same tasks:
  - **Grid View**: Spreadsheet-style; great for detailed editing.
  - **Gantt View**: Timeline with bars, dependencies, and critical path.
  - **Card View**: Kanban-style boards grouped by a column (e.g., Status, Phase).
  - **Calendar View**: Tasks placed on a calendar based on date columns.

- **Hierarchy (parent/child rows)**  
  - You can indent tasks to create **phases → sub-tasks → sub-sub-tasks**.  
  - Parent rows can auto-rollup values (e.g., sum of child durations or average % complete).

---

### 2. Scheduling: Dependencies, Critical Path, and Baselines

- **Task dependencies (Predecessors)**  
  - Use a `Predecessors` column to link tasks (e.g., Task B starts after Task A finishes).  
  - Supports relationships like **Finish-to-Start**, lags/leads (e.g., `2FS+3d`).

- **Automatic Gantt scheduling**  
  - When you update dates or dependencies, Smartsheet updates the Gantt chart and related tasks.

- **Critical Path**  
  - In Gantt view, you can highlight the **critical path** to see the sequence of tasks that determine the project’s end date.

- **Baselines (in project sheets)**  
  - You can capture a **baseline** of your planned schedule, then compare actuals vs baseline dates to see drift/delays.

---

### 3. Collaboration: Comments, Attachments, and Sharing

- **Row-level comments**  
  - Add comments directly on tasks; @mention people to notify them.
  - Good for keeping context (decisions, clarifications) attached to the work.

- **Attachments**  
  - Attach files (docs, designs, contracts) to the sheet or to specific rows.
  - Can link to cloud storage (OneDrive, Google Drive, Box, etc.).

- **Sharing & permissions**  
  - Share whole sheets or reports with different roles: **Admin, Editor, Viewer**.  
  - Option to send people **update requests** without giving full edit access.

- **Alerts & notifications**  
  - Users get email / in-app notifications when they’re assigned work, mentioned, or when automations trigger.

---

### 4. Automation & Workflows

- **No-code automation rules**  
  - Build “when this happens → do that” rules, e.g.:
    - When `Status` changes to “Complete” → notify the PM.
    - When `End Date` passes and `Status` is not “Complete” → alert assignee and manager.
    - When a row is added via a form → assign it and set Due Date automatically.

- **Typical actions**  
  - Send alerts or update requests  
  - Move or copy rows to other sheets (e.g., escalation board)  
  - Lock/unlock rows  
  - Change cell values (e.g., auto-set `Status` to “Overdue”)

- **Time-based triggers**  
  - Schedule rules: daily, weekly, or relative to a date in a row (e.g., 3 days before `End Date`).

---

### 5. Intake & Requests: Forms

- **Forms tied to a sheet**  
  - Build a form so stakeholders can submit **work requests, bugs, change requests, ideas**.  
  - Each form submission becomes a **new row** in your project or intake sheet.

- **Use cases**  
  - Project intake / portfolio funnel  
  - Support / ticket queue  
  - Feature requests or change requests

---

### 6. Reporting and Portfolio View

- **Reports (multi-sheet views)**  
  - Pull rows from one or many sheets based on conditions (e.g., “All open tasks assigned to me across all projects”).  
  - Reports are **live views**: you can often edit directly and it writes back to the source sheet.

- **Dashboards (high-level views)**  
  - Visual summary: charts, metrics, rich text, shortcuts, and embedded content.  
  - Typical dashboard elements:
    - Project health indicators (On Track / At Risk / Off Track)
    - KPIs (e.g., number of overdue tasks, % complete)
    - Gantt snapshots or report widgets
    - Links to key sheets and documents.

- **Portfolio / program management**  
  - Multiple projects each have a “summary” section or sheet.  
  - A **portfolio summary sheet** or report rolls up data (e.g., health, budget, schedule variance) across projects.  
  - Dashboards can display portfolio-level charts and summaries.

---

### 7. Resource & Workload Management

- **Assignments**  
  - Tasks can be assigned via a `Contact` column (usually `Assigned To`).
  - Good for seeing who is responsible for what.

- **Workload views (depending on plan)**  
  - On higher-tier plans and with **Resource Management by Smartsheet**, you can:
    - View resource utilization across projects.
    - See who is over/under-allocated.
    - Plan capacity by person/role.

---

### 8. Data, Formulas, and Governance

- **Formulas & functions**  
  - Spreadsheet-like formulas: `SUM`, `IF`, `VLOOKUP`, `INDEX/MATCH`, `COUNTIFS`, etc.  
  - Useful for:
    - Calculating durations or effort
    - Status logic (e.g. automatically mark “Overdue”)
    - Rollups in summary sheets or portfolio sheets.

- **Cross-sheet references**  
  - You can pull data from other sheets (e.g., budget from a finance sheet into a project sheet).

- **Cell history & change tracking**  
  - View cell history to see who changed what and when (good for audits).

- **Access control & governance (enterprise features)**  
  - More advanced controls for who can create sheets, share externally, etc.

---

### 9. Integrations

- **Integrations with other tools**  
  - Microsoft 365 (Outlook, Teams), Google Workspace, Slack, Jira, Salesforce, and others (depends on plan).  
  - Typical patterns:
    - Sync issues between Jira and Smartsheet.
    - Send notifications to Teams/Slack channels.
    - Link project status to Salesforce opportunities.

---

### 10. Templates & Solution Sets

- **Pre-built templates**  
  - Project plan & schedule  
  - Agile sprint board  
  - PMO / portfolio management  
  - Marketing campaigns, IT work intake, etc.

- **Solution sets (for larger orgs)**  
  - Bundled templates + reports + dashboards for specific use cases (e.g., PMO, IT PM, marketing).

---

### How to Start Using It for a Project

- **Simple way to begin**  
  1. Create a new sheet from a **Project** template.  
  2. Define tasks, start/end dates, and predecessors.  
  3. Switch to **Gantt view** to visualize timeline.  
  4. Add an `Assigned To` and `Status` column.  
  5. Set up a few **basic automations** (overdue alerts, status-change notifications).  
  6. Add a **dashboard** pulling KPIs and a summary report.

---
