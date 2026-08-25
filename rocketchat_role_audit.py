#!/usr/bin/env python3

import urllib.request
import urllib.parse
import json
import os
import sys
from datetime import datetime, timezone


# ============================================================
# Configuration
# ============================================================

ROCKETCHAT_URL = os.environ["ROCKETCHAT_URL"]
AUTH_TOKEN = os.environ["ROCKETCHAT_AUTH_TOKEN"]
USER_ID = os.environ["ROCKETCHAT_USER_ID"]

BASELINE_FILE = "roles_permissions_baseline.json"
CHANGES_FILE = "role_changes.json"


# ============================================================
# Rocket.Chat API
# ============================================================

def api_get(endpoint, params=None):

    url = f"{ROCKETCHAT_URL}{endpoint}"

    if params:
        url += "?" + urllib.parse.urlencode(params)

    headers = {
        "X-Auth-Token": AUTH_TOKEN,
        "X-User-Id": USER_ID,
        "Content-Type": "application/json"
    }

    request = urllib.request.Request(
        url,
        headers=headers,
        method="GET"
    )

    try:

        with urllib.request.urlopen(
            request,
            timeout=30
        ) as response:

            response_data = response.read().decode("utf-8")

    except Exception as e:

        print(f"ERROR: API request failed: {endpoint}")
        print(f"Details: {e}")

        return None

    try:

        data = json.loads(response_data)

    except json.JSONDecodeError:

        print(
            f"ERROR: Invalid JSON returned by {endpoint}"
        )

        return None

    if not data.get("success"):

        print(
            f"ERROR: Rocket.Chat API returned "
            f"success=false for {endpoint}"
        )

        return None

    return data


# ============================================================
# Get roles
# ============================================================

def get_roles():

    data = api_get(
        "/api/v1/roles.list"
    )

    if data is None:
        sys.exit(1)

    roles = data.get("roles", [])

    role_map = {}

    for role in roles:

        role_id = role.get("_id")

        if not role_id:
            continue

        role_map[role_id] = {
            "name": role.get("name", role_id),
            "description": role.get(
                "description",
                ""
            ),
            "scope": role.get(
                "scope",
                ""
            ),
            "protected": role.get(
                "protected",
                False
            ),
            "mandatory2fa": role.get(
                "mandatory2fa",
                False
            )
        }

    return role_map


# ============================================================
# Get permissions
# ============================================================

def get_permissions():

    data = api_get(
        "/api/v1/permissions.listAll"
    )

    if data is None:
        sys.exit(1)

    # Rocket.Chat may return permissions under
    # different keys depending on API response.
    permissions = data.get(
        "permissions",
        []
    )

    if not permissions:

        permissions = data.get(
            "update",
            []
        )

    return permissions


# ============================================================
# Build current authorization state
# ============================================================

def build_current_state(
    role_map,
    permissions
):

    state = {}

    # --------------------------------------------------------
    # Add all roles, even if they have no permissions
    # --------------------------------------------------------

    for role_id, role_data in role_map.items():

        state[role_id] = {
            "name": role_data["name"],
            "description": role_data["description"],
            "scope": role_data["scope"],
            "protected": role_data["protected"],
            "mandatory2fa": role_data["mandatory2fa"],
            "permissions": []
        }

    # --------------------------------------------------------
    # Associate permissions with roles
    # --------------------------------------------------------

    for permission in permissions:

        permission_id = permission.get("_id")

        if not permission_id:
            continue

        role_ids = permission.get(
            "roles",
            []
        )

        for role_id in role_ids:

            # ------------------------------------------------
            # If a permission references a role that is not
            # present in roles.list, keep the role anyway.
            # ------------------------------------------------

            if role_id not in state:

                state[role_id] = {
                    "name": role_id,
                    "description": "",
                    "scope": "",
                    "protected": False,
                    "mandatory2fa": False,
                    "permissions": []
                }

            state[role_id]["permissions"].append(
                permission_id
            )

    # --------------------------------------------------------
    # Sort permissions for consistent comparison
    # --------------------------------------------------------

    for role_id in state:

        state[role_id]["permissions"] = sorted(
            set(
                state[role_id]["permissions"]
            )
        )

    return state


# ============================================================
# Load baseline
# ============================================================

def load_baseline():

    if not os.path.exists(BASELINE_FILE):

        return None

    try:

        with open(
            BASELINE_FILE,
            "r",
            encoding="utf-8"
        ) as file:

            return json.load(file)

    except Exception as e:

        print(
            "ERROR: Could not read baseline file."
        )

        print(f"Details: {e}")

        sys.exit(1)


# ============================================================
# Save JSON
# ============================================================

def save_json(filename, data):

    try:

        with open(
            filename,
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                data,
                file,
                indent=2,
                ensure_ascii=False,
                sort_keys=True
            )

    except Exception as e:

        print(
            f"ERROR: Could not write {filename}"
        )

        print(f"Details: {e}")

        sys.exit(1)


# ============================================================
# Compare roles and permissions
# ============================================================

def compare_states(
    old_state,
    new_state
):

    changes = []

    detected_at = datetime.now(
        timezone.utc
    ).isoformat()

    old_roles = set(
        old_state.keys()
    )

    new_roles = set(
        new_state.keys()
    )

    # ========================================================
    # Role added
    # ========================================================

    for role_id in sorted(
        new_roles - old_roles
    ):

        role = new_state[role_id]

        changes.append({
            "timestamp": detected_at,
            "change": "ROLE_ADDED",
            "role_id": role_id,
            "role": role["name"],
            "permission": None
        })

    # ========================================================
    # Role removed
    # ========================================================

    for role_id in sorted(
        old_roles - new_roles
    ):

        role = old_state[role_id]

        changes.append({
            "timestamp": detected_at,
            "change": "ROLE_REMOVED",
            "role_id": role_id,
            "role": role["name"],
            "permission": None
        })

    # ========================================================
    # Compare existing roles
    # ========================================================

    for role_id in sorted(
        old_roles & new_roles
    ):

        old_role = old_state[role_id]
        new_role = new_state[role_id]

        old_name = old_role.get(
            "name",
            role_id
        )

        new_name = new_role.get(
            "name",
            role_id
        )

        # ----------------------------------------------------
        # Role renamed
        # ----------------------------------------------------

        if old_name != new_name:

            changes.append({
                "timestamp": detected_at,
                "change": "ROLE_RENAMED",
                "role_id": role_id,
                "role": new_name,
                "previous_role": old_name,
                "permission": None
            })

        # ----------------------------------------------------
        # Permissions
        # ----------------------------------------------------

        old_permissions = set(
            old_role.get(
                "permissions",
                []
            )
        )

        new_permissions = set(
            new_role.get(
                "permissions",
                []
            )
        )

        added_permissions = (
            new_permissions - old_permissions
        )

        removed_permissions = (
            old_permissions - new_permissions
        )

        # ----------------------------------------------------
        # Permission added
        # ----------------------------------------------------

        for permission in sorted(
            added_permissions
        ):

            changes.append({
                "timestamp": detected_at,
                "change": "PERMISSION_ADDED",
                "role_id": role_id,
                "role": new_name,
                "permission": permission
            })

        # ----------------------------------------------------
        # Permission removed
        # ----------------------------------------------------

        for permission in sorted(
            removed_permissions
        ):

            changes.append({
                "timestamp": detected_at,
                "change": "PERMISSION_REMOVED",
                "role_id": role_id,
                "role": new_name,
                "permission": permission
            })

    return changes


# ============================================================
# Print changes
# ============================================================

def print_changes(changes):

    if not changes:

        print(
            "No role or permission changes detected."
        )

        return

    print()
    print(
        "=============================================="
    )

    print(
        " Changes Detected"
    )

    print(
        "=============================================="
    )

    for change in changes:

        print()

        print(
            f"Change: {change['change']}"
        )

        print(
            f"Role:   {change['role']}"
        )

        if change.get("previous_role"):

            print(
                f"Previous role: "
                f"{change['previous_role']}"
            )

        if change.get("permission"):

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
        f"Total changes: {len(changes)}"
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

    print()

    # --------------------------------------------------------
    # Get current configuration
    # --------------------------------------------------------

    print(
        "Retrieving roles..."
    )

    role_map = get_roles()

    print(
        f"Roles retrieved: {len(role_map)}"
    )

    print(
        "Retrieving permissions..."
    )

    permissions = get_permissions()

    print(
        f"Permissions retrieved: "
        f"{len(permissions)}"
    )

    # --------------------------------------------------------
    # Build current state
    # --------------------------------------------------------

    current_state = build_current_state(
        role_map,
        permissions
    )

    # --------------------------------------------------------
    # Load baseline
    # --------------------------------------------------------

    baseline = load_baseline()

    # --------------------------------------------------------
    # First execution
    # --------------------------------------------------------

    if baseline is None:

        print()

        print(
            "No baseline found."
        )

        print(
            "Creating initial baseline..."
        )

        save_json(
            BASELINE_FILE,
            current_state
        )

        # Empty changes file
        save_json(
            CHANGES_FILE,
            []
        )

        print()

        print(
            "Baseline created successfully."
        )

        print(
            "No alerts generated on initial run."
        )

        print(
            f"Baseline file: {BASELINE_FILE}"
        )

        return

    # --------------------------------------------------------
    # Compare
    # --------------------------------------------------------

    print()

    print(
        "Comparing current state with baseline..."
    )

    changes = compare_states(
        baseline,
        current_state
    )

    # --------------------------------------------------------
    # Save changes
    # --------------------------------------------------------

    save_json(
        CHANGES_FILE,
        changes
    )

    # --------------------------------------------------------
    # Print changes
    # --------------------------------------------------------

    print_changes(
        changes
    )

    # --------------------------------------------------------
    # Update baseline
    # --------------------------------------------------------

    save_json(
        BASELINE_FILE,
        current_state
    )

    print()

    print(
        "Baseline updated successfully."
    )

    print(
        f"Changes file: {CHANGES_FILE}"
    )


# ============================================================
# Entry point
# ============================================================

if __name__ == "__main__":
    main()