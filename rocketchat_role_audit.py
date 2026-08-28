#!/usr/bin/env python3

import os
import json
import urllib.request
import urllib.parse
from datetime import datetime, timezone


# ============================================================
# Configuration
# ============================================================

ROCKETCHAT_URL = os.environ["ROCKETCHAT_URL"].rstrip("/")
ROCKETCHAT_AUTH_TOKEN = os.environ["ROCKETCHAT_AUTH_TOKEN"]
ROCKETCHAT_USER_ID = os.environ["ROCKETCHAT_USER_ID"]

BASELINE_FILE = "baseline_previous.json"
CANDIDATE_BASELINE_FILE = "roles_permissions_baseline.json"
CHANGES_FILE = "role_changes.json"


# ============================================================
# Rocket.Chat API
# ============================================================

def rocket_chat_get(endpoint, params=None):

    url = f"{ROCKETCHAT_URL}{endpoint}"

    if params:
        url += "?" + urllib.parse.urlencode(params)

    request = urllib.request.Request(
        url,
        headers={
            "X-Auth-Token": ROCKETCHAT_AUTH_TOKEN,
            "X-User-Id": ROCKETCHAT_USER_ID,
            "Content-Type": "application/json",
        },
        method="GET",
    )

    with urllib.request.urlopen(
        request,
        timeout=30
    ) as response:

        data = response.read().decode("utf-8")

        return json.loads(data)


# ============================================================
# Get Roles
# ============================================================

def get_roles():

    print("Retrieving roles...")

    data = rocket_chat_get(
        "/api/v1/roles.list"
    )

    roles = data.get(
        "roles",
        []
    )

    print(
        f"Roles retrieved: {len(roles)}"
    )

    return roles


# ============================================================
# Get Permissions
# ============================================================

def get_permissions():

    print("Retrieving permissions...")

    data = rocket_chat_get(
        "/api/v1/permissions.listAll"
    )

    permissions = data.get(
        "update",
        []
    )

    print(
        f"Permissions retrieved: {len(permissions)}"
    )

    return permissions


# ============================================================
# Build Role -> Permissions structure
# ============================================================

def build_role_permissions(
    roles,
    permissions
):

    role_names = {
        role["_id"]: role.get(
            "name",
            role["_id"]
        )
        for role in roles
    }

    role_permissions = {}

    for role_id, role_name in role_names.items():

        role_permissions[role_id] = {
            "name": role_name,
            "permissions": []
        }

    for permission in permissions:

        permission_id = permission.get(
            "_id"
        )

        for role_id in permission.get(
            "roles",
            []
        ):

            if role_id not in role_permissions:
                continue

            role_permissions[
                role_id
            ][
                "permissions"
            ].append(
                permission_id
            )

    for role_id in role_permissions:

        role_permissions[
            role_id
        ][
            "permissions"
        ].sort()

    return role_permissions


# ============================================================
# Load Previous Baseline
# ============================================================

def load_baseline():

    if not os.path.exists(
        BASELINE_FILE
    ):

        print(
            "No previous baseline found."
        )

        return None

    try:

        with open(
            BASELINE_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            baseline = json.load(f)

        print(
            "Previous baseline loaded successfully."
        )

        return baseline

    except json.JSONDecodeError as e:

        print(
            f"ERROR: Invalid baseline JSON: {e}"
        )

        raise


# ============================================================
# Save Candidate Baseline
# ============================================================

def save_candidate_baseline(
    current_state
):

    with open(
        CANDIDATE_BASELINE_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            current_state,
            f,
            indent=2,
            sort_keys=True
        )

    print(
        "Candidate baseline saved successfully."
    )

    print(
        f"Candidate baseline: "
        f"{CANDIDATE_BASELINE_FILE}"
    )


# ============================================================
# Compare States
# ============================================================

def compare_states(
    previous,
    current
):

    changes = []

    timestamp = datetime.now(
        timezone.utc
    ).isoformat()

    previous_roles = set(
        previous.keys()
    )

    current_roles = set(
        current.keys()
    )

    added_roles = (
        current_roles
        - previous_roles
    )

    removed_roles = (
        previous_roles
        - current_roles
    )

    # --------------------------------------------------------
    # Roles added
    # --------------------------------------------------------

    for role_id in sorted(
        added_roles
    ):

        changes.append({
            "timestamp": timestamp,
            "change": "ROLE_ADDED",
            "role_id": role_id,
            "role": current[
                role_id
            ][
                "name"
            ],
        })

    # --------------------------------------------------------
    # Roles removed
    # --------------------------------------------------------

    for role_id in sorted(
        removed_roles
    ):

        changes.append({
            "timestamp": timestamp,
            "change": "ROLE_REMOVED",
            "role_id": role_id,
            "role": previous[
                role_id
            ][
                "name"
            ],
        })

    # --------------------------------------------------------
    # Permission comparison
    # --------------------------------------------------------

    common_roles = (
        previous_roles
        & current_roles
    )

    for role_id in sorted(
        common_roles
    ):

        previous_permissions = set(
            previous[
                role_id
            ].get(
                "permissions",
                []
            )
        )

        current_permissions = set(
            current[
                role_id
            ].get(
                "permissions",
                []
            )
        )

        added_permissions = (
            current_permissions
            - previous_permissions
        )

        removed_permissions = (
            previous_permissions
            - current_permissions
        )

        role_name = current[
            role_id
        ][
            "name"
        ]

        # ----------------------------------------------------
        # Permissions added
        # ----------------------------------------------------

        for permission in sorted(
            added_permissions
        ):

            changes.append({
                "timestamp": timestamp,
                "change": "PERMISSION_ADDED",
                "role_id": role_id,
                "role": role_name,
                "permission": permission,
            })

        # ----------------------------------------------------
        # Permissions removed
        # ----------------------------------------------------

        for permission in sorted(
            removed_permissions
        ):

            changes.append({
                "timestamp": timestamp,
                "change": "PERMISSION_REMOVED",
                "role_id": role_id,
                "role": role_name,
                "permission": permission,
            })

    return changes


# ============================================================
# Save Changes
# ============================================================

def save_changes(
    changes
):

    with open(
        CHANGES_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            changes,
            f,
            indent=2
        )

    print(
        f"Changes file saved: "
        f"{CHANGES_FILE}"
    )


# ============================================================
# Display Changes
# ============================================================

def display_changes(
    changes
):

    print(
        "=============================================="
    )

    print(
        " Changes Detected"
    )

    print(
        "=============================================="
    )

    if not changes:

        print(
            "No changes detected."
        )

        return

    for change in changes:

        print(
            f"Change: {change['change']}"
        )

        print(
            f"Role:   "
            f"{change.get('role', 'N/A')}"
        )

        if "permission" in change:

            print(
                f"Permission: "
                f"{change['permission']}"
            )

        print(
            f"Timestamp: "
            f"{change['timestamp']}"
        )

        print()

    print(
        f"Total changes: "
        f"{len(changes)}"
    )

    print(
        "=============================================="
    )


# ============================================================
# Main
# ============================================================

def main():

    print(
        "=============================================="
    )

    print(
        " Rocket.Chat Role Permission Audit"
    )

    print(
        "=============================================="
    )

    try:

        # ----------------------------------------------------
        # Retrieve current state
        # ----------------------------------------------------

        roles = get_roles()

        permissions = get_permissions()

        current_state = build_role_permissions(
            roles,
            permissions
        )

        # ----------------------------------------------------
        # Load previous baseline
        # ----------------------------------------------------

        previous_state = load_baseline()

        # ----------------------------------------------------
        # First run
        # ----------------------------------------------------

        if previous_state is None:

            print(
                "Creating initial candidate baseline..."
            )

            save_candidate_baseline(
                current_state
            )

            save_changes([])

            print(
                "Initial candidate baseline created."
            )

            return

        # ----------------------------------------------------
        # Compare
        # ----------------------------------------------------

        print(
            "Comparing current state with baseline..."
        )

        changes = compare_states(
            previous_state,
            current_state
        )

        # ----------------------------------------------------
        # Save changes
        # ----------------------------------------------------

        save_changes(
            changes
        )

        # ----------------------------------------------------
        # Display changes
        # ----------------------------------------------------

        display_changes(
            changes
        )

        # ----------------------------------------------------
        # Generate candidate baseline
        # ----------------------------------------------------

        save_candidate_baseline(
            current_state
        )

        # ----------------------------------------------------
        # Finish
        # ----------------------------------------------------

        print(
            "Audit completed successfully."
        )

        if changes:

            print(
                "Changes detected."
            )

            print(
                "GitLab CI should send the notification "
                "before publishing the candidate baseline."
            )

        else:

            print(
                "No changes detected."
            )

    except Exception as e:

        print(
            f"ERROR: Audit failed: {e}"
        )

        raise


# ============================================================
# Entry Point
# ============================================================

if __name__ == "__main__":

    main()