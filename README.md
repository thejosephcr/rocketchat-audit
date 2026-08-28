# Rocket.Chat Security Audit

## Description

This project contains automated security audits for Rocket.Chat using GitLab CI/CD.

The project currently includes two independent audits:

1. **Role Permission Audit**

   * Monitors changes to Rocket.Chat roles and permissions.
   * Detects added and removed roles.
   * Detects added and removed permissions.
   * Sends a notification to Rocket.Chat when changes are detected.
   * Maintains a baseline in the GitLab Package Registry.

2. **User Audit**

   * Identifies users who have not logged in for 6 months or more.
   * Identifies users who have never logged in.
   * Identifies newly created accounts.
   * Identifies accounts where the creation date cannot be determined.
   * Generates a CSV report.
   * Does not modify Rocket.Chat.

Both audits perform read-only operations against Rocket.Chat.

---

## Project Structure

```text
rocketchat-audit/
│
├── .gitlab-ci.yml
│
├── rocketchat_role_audit.py
│
└── rocketchat_audit.py
```

Generated files:

```text
role_changes.json
roles_permissions_baseline.json
rocketchat_users.csv
```

These files are generated during pipeline execution and are stored as GitLab artifacts when applicable.

---

## GitLab CI/CD

The project intentionally uses a single GitLab CI/CD stage:

```yaml
stages:
  - audit
```

The stage contains two independent jobs:

```text
audit
│
├── rocketchat_role_audit
│
└── rocketchat_user_audit
```

The two jobs can execute independently and do not depend on each other.

---

## Role Permission Audit

### Script

```text
rocketchat_role_audit.py
```

The script retrieves Rocket.Chat roles and permissions using:

```text
/api/v1/roles.list
/api/v1/permissions.listAll
```

The information is used to build a relationship between:

```text
Role → Permissions
```

The current state is compared against the previous baseline.

---

### Detected Changes

The audit can detect the following changes:

```text
ROLE_ADDED
ROLE_REMOVED
PERMISSION_ADDED
PERMISSION_REMOVED
```

#### Permission Added

Example:

```text
Permission Added: abac-management | Role: Infosec
```

#### Permission Removed

Example:

```text
Permission Removed: abac-management | Role: Infosec
```

#### Role Added

Example:

```text
Role Added: HelpDesk
```

#### Role Removed

Example:

```text
Role Removed: expert
```

---

## Role Audit Output

The detected changes are stored in:

```text
role_changes.json
```

Example:

```json
[
  {
    "timestamp": "2026-08-27T16:50:24.476824+00:00",
    "change": "PERMISSION_ADDED",
    "role_id": "695da6d68edc5f7637c355d4",
    "role": "Infosec",
    "permission": "abac-management"
  }
]
```

If no changes are detected:

```json
[]
```

---

## Baseline Management

The Role Permission Audit uses a baseline to determine whether roles or permissions have changed.

The baseline file is:

```text
roles_permissions_baseline.json
```

The baseline is stored in the GitLab Package Registry as a Generic Package:

```text
Package:
rocketchat-role-baseline
```

Each baseline is stored using a unique version generated from the Unix timestamp:

```bash
CURRENT_VERSION=$(date +%s)
```

Example:

```text
1756313421
```

---

### Baseline Workflow

The Role Audit follows this process:

```text
1. Check GitLab Package Registry
             |
             v
2. Find latest baseline
             |
             v
3. Download previous baseline
             |
             v
4. Query Rocket.Chat
             |
             v
5. Compare current state
             |
             v
6. Generate role_changes.json
             |
       +-----+-----+
       |           |
     No change   Changes
       |           |
       v           v
     Stop      Notify Rocket.Chat
                   |
              +----+----+
              |         |
            Failed    Success
              |         |
              v         v
             STOP   Publish baseline
```

The baseline is only updated after a successful Rocket.Chat notification.

This prevents the audit from losing a detected change if the notification fails.

---

## Rocket.Chat Notifications

Notifications are only sent when changes are detected.

Example:

```text
Rocket.Chat Role Permission Audit
Permission Added: `abac-management` | Role: `Infosec`
```

Another example:

```text
Rocket.Chat Role Permission Audit
Permission Removed: `abac-management` | Role: `Infosec`
```

For role changes:

```text
Rocket.Chat Role Permission Audit
Role Removed: `expert`
```

No notification is sent when there are no changes.

---

## User Audit

### Script

```text
rocketchat_audit.py
```

The User Audit reviews Rocket.Chat user activity and generates a CSV report.

The audit is intended to identify accounts that may require review.

The script does not modify users or Rocket.Chat configuration.

---

## Inactivity Threshold

The current inactivity threshold is:

```text
6 months
```

The value is defined directly in:

```text
rocketchat_audit.py
```

as:

```python
INACTIVE_MONTHS = 6
```

`INACTIVE_MONTHS` is intentionally **not configured as a GitLab CI/CD variable**.

This keeps the audit criteria fixed and reproducible.

If the audit requirement changes in the future, the value can be modified in the Python script and committed through the normal Git workflow.

For example:

```python
INACTIVE_MONTHS = 3
```

would change the audit threshold to three months.

---

## User Audit Categories

The User Audit can classify accounts using categories such as:

```text
INACTIVE_6_MONTHS
NEVER_LOGGED_IN
NEW_ACCOUNT
UNKNOWN_NO_CREATED_DATE
ACTIVE
```

### INACTIVE_6_MONTHS

The user's last login occurred six months or more before the calculated cutoff date.

---

### NEVER_LOGGED_IN

The user does not have a `lastLogin` value and can be classified as an account that has never logged in.

---

### NEW_ACCOUNT

The account was created recently and has not reached the six-month inactivity threshold.

This prevents recently created accounts from being incorrectly classified as inactive.

---

### UNKNOWN_NO_CREATED_DATE

The required creation date information could not be obtained for the account.

The audit does not assume a creation date when the information is unavailable.

This allows accounts with incomplete API data to be clearly identified instead of being incorrectly classified.

---

## User Audit Output

The User Audit generates:

```text
rocketchat_users.csv
```

The report contains fields such as:

```text
username
name
email
lastLogin
createdAt
category
```

The CSV is stored as a GitLab artifact for:

```text
30 days
```

---

## User Audit Schedule

The User Audit job is configured to run only when the pipeline is triggered by a GitLab Pipeline Schedule:

```yaml
rules:
  - if: '$CI_PIPELINE_SOURCE == "schedule"'
```

This allows the user audit to be executed periodically without requiring it to run on every repository commit.

---

## Role Audit Schedule

The Role Permission Audit is configured to run on the default branch:

```yaml
rules:
  - if: '$CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH'
```

A GitLab Pipeline Schedule can therefore be used to perform periodic role and permission checks.

For example, to execute the scheduled pipeline every 15 minutes:

```cron
*/15 * * * *
```

This results in executions at:

```text
00
15
30
45
```

of every hour.

Because the Role Audit only sends a notification when changes are detected, scheduled executions without changes do not generate Rocket.Chat messages.

---

## CI/CD Variables

The project requires the following GitLab CI/CD variables:

```text
ROCKETCHAT_URL
ROCKETCHAT_AUTH_TOKEN
ROCKETCHAT_USER_ID
ROCKETCHAT_WEBHOOK_URL
```

### ROCKETCHAT_URL

Base URL of the Rocket.Chat instance.

Example:

```text
https://chat.example.com
```

### ROCKETCHAT_AUTH_TOKEN

Authentication token used by the Rocket.Chat REST API.

### ROCKETCHAT_USER_ID

User ID associated with the authentication token.

### ROCKETCHAT_WEBHOOK_URL

Complete Incoming Webhook URL used to send notifications to Rocket.Chat.

The complete URL is stored as a single GitLab CI/CD variable.

The webhook URL should never be committed to the repository.

---

## Security

The audit scripts perform read-only operations against Rocket.Chat.

They do not:

* Create users.
* Delete users.
* Modify users.
* Disable users.
* Modify roles.
* Modify permissions.
* Modify Rocket.Chat settings.

The Role Audit only writes the generated baseline to the GitLab Package Registry after a successful notification.

The User Audit only generates a CSV report.

---

## Authentication

Rocket.Chat API authentication is performed using:

```text
X-Auth-Token
X-User-Id
```

The values are provided through GitLab CI/CD variables.

Example local configuration:

```bash
export ROCKETCHAT_URL="https://chat.example.com"
export ROCKETCHAT_AUTH_TOKEN="YOUR_TOKEN"
export ROCKETCHAT_USER_ID="YOUR_USER_ID"
```

The webhook is only required when sending Role Audit notifications.

---

## Local Execution

### Role Permission Audit

```bash
export ROCKETCHAT_URL="https://chat.example.com"
export ROCKETCHAT_AUTH_TOKEN="YOUR_TOKEN"
export ROCKETCHAT_USER_ID="YOUR_USER_ID"

python3 rocketchat_role_audit.py
```

The Role Audit requires a previous baseline for change comparison after the initial execution.

---

### User Audit

```bash
export ROCKETCHAT_URL="https://chat.example.com"
export ROCKETCHAT_AUTH_TOKEN="YOUR_TOKEN"
export ROCKETCHAT_USER_ID="YOUR_USER_ID"

python3 rocketchat_audit.py
```

The current inactivity threshold is six months.

The resulting report is:

```text
rocketchat_users.csv
```

---

## Dependencies

The Python scripts use Python 3 and standard Python libraries.

No external Python packages are required.

The GitLab runner uses:

```text
python:3.12-slim
```

The Role Audit job installs:

```text
curl
jq
```

because they are required for GitLab Package Registry operations and JSON processing.

---

## GitLab Artifacts

The pipeline can generate the following artifacts:

| File                              | Purpose                              |
| --------------------------------- | ------------------------------------ |
| `role_changes.json`               | Detected role and permission changes |
| `roles_permissions_baseline.json` | Candidate Role/Permission baseline   |
| `rocketchat_users.csv`            | User activity audit report           |

Artifacts are retained for:

```text
30 days
```

---

## Current Scope

The project currently provides two security audit capabilities:

```text
Rocket.Chat Security Audit
│
├── User Audit
│   │
│   ├── Inactive users >= 6 months
│   ├── Never logged in
│   ├── New accounts
│   └── Unknown creation date
│
└── Role Permission Audit
    │
    ├── Roles added
    ├── Roles removed
    ├── Permissions added
    └── Permissions removed
```

The two audits are intentionally independent and run within the same GitLab CI/CD `audit` stage.

---

## Future Improvements

Potential future enhancements include:

* Additional Rocket.Chat security audits.
* Automated reporting of inactive accounts to a dedicated channel.
* Historical tracking of user audit results.
* Additional role and permission validation rules.
* Integration with SIEM platforms.
* Periodic security attestation reports.
* Detection of unexpected administrative privileges.