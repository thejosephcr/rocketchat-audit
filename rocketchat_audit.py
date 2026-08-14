#!/usr/bin/env python3

import urllib.request
import urllib.parse
import json
import csv
import sys
import os
from datetime import datetime, timezone


# ============================================================
# Configuration
# ============================================================

ROCKETCHAT_URL = os.environ["ROCKETCHAT_URL"]
AUTH_TOKEN = os.environ["ROCKETCHAT_AUTH_TOKEN"]
USER_ID = os.environ["ROCKETCHAT_USER_ID"]

OUTPUT_FILE = "rocketchat_users.csv"

# Users with no login older than this threshold
# will be classified as inactive.
INACTIVE_MONTHS = 6

# Users created within this number of days
# that have never logged in will be classified
# as NEW_ACCOUNT.
NEW_ACCOUNT_DAYS = 7


# ============================================================
# Date utilities
# ============================================================

def parse_rocketchat_date(date_string):
    """
    Convert Rocket.Chat ISO 8601 date into datetime.
    """

    if not date_string:
        return None

    try:
        return datetime.fromisoformat(
            date_string.replace("Z", "+00:00")
        )

    except (ValueError, TypeError):
        return None


def months_ago(dt, months):
    """
    Return a datetime representing N calendar months ago.
    """

    year = dt.year
    month = dt.month - months

    while month <= 0:
        month += 12
        year -= 1

    # Days in each month
    days_in_month = [
        31,
        29 if year % 4 == 0 and
        (year % 100 != 0 or year % 400 == 0)
        else 28,
        31,
        30,
        31,
        30,
        31,
        31,
        30,
        31,
        30,
        31
    ]

    day = min(
        dt.day,
        days_in_month[month - 1]
    )

    return dt.replace(
        year=year,
        month=month,
        day=day
    )


# ============================================================
# Rocket.Chat API request
# ============================================================

def api_get(endpoint, params=None):

    url = f"{ROCKETCHAT_URL}{endpoint}"

    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"

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

        print(
            f"ERROR: API request failed: {endpoint}"
        )

        print(f"Details: {e}")

        return None

    try:

        data = json.loads(response_data)

    except json.JSONDecodeError:

        print(
            f"ERROR: Invalid JSON returned by: "
            f"{endpoint}"
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
# Get all users
# ============================================================

def get_users():

    params = {
        "count": "0",
        "fields": json.dumps({
            "username": 1,
            "name": 1,
            "emails": 1,
            "lastLogin": 1,
            "active": 1,
            "roles": 1,
            "type": 1
        })
    }

    data = api_get(
        "/api/v1/users.list",
        params
    )

    if data is None:
        sys.exit(1)

    return data.get("users", [])


# ============================================================
# Get specific user information
# ============================================================

def get_user_info(username):

    params = {
        "username": username
    }

    data = api_get(
        "/api/v1/users.info",
        params
    )

    if data is None:
        return None

    return data.get("user")


# ============================================================
# Get email
# ============================================================

def get_email(user):

    emails = user.get("emails") or []

    for email_entry in emails:

        address = email_entry.get("address")

        if address:
            return address

    return ""


# ============================================================
# Process users
# ============================================================

def process_users(users):

    now = datetime.now(timezone.utc)

    cutoff_date = months_ago(
        now,
        INACTIVE_MONTHS
    )

    results = []

    users_info_requests = 0
    users_info_errors = 0

    for user in users:

        username = user.get("username", "")
        name = user.get("name", "")

        email = get_email(user)

        last_login = user.get("lastLogin")

        active = user.get(
            "active",
            ""
        )

        user_type = user.get(
            "type",
            ""
        )

        roles = ",".join(
            user.get("roles", [])
        )

        created_at = ""
        account_age_days = ""
        inactive_days = ""

        # ====================================================
        # Users with a lastLogin
        # ====================================================

        if last_login:

            login_date = parse_rocketchat_date(
                last_login
            )

            if login_date is None:

                category = "INVALID_LAST_LOGIN"

            else:

                inactive_days = (
                    now - login_date
                ).days

                if login_date < cutoff_date:

                    category = (
                        f"INACTIVE_{INACTIVE_MONTHS}_MONTHS"
                    )

                else:

                    category = "ACTIVE"

        # ====================================================
        # Users without lastLogin
        # ====================================================

        else:

            # ------------------------------------------------
            # Get createdAt using users.info
            # ------------------------------------------------

            users_info_requests += 1

            detailed_user = get_user_info(
                username
            )

            if detailed_user is None:

                users_info_errors += 1

                category = "UNKNOWN_NO_CREATED_DATE"

            else:

                created_at = (
                    detailed_user.get(
                        "createdAt"
                    ) or ""
                )

                # Some users.info responses may contain
                # lastLogin even when users.list did not.
                detailed_last_login = (
                    detailed_user.get(
                        "lastLogin"
                    )
                )

                if detailed_last_login:

                    last_login = detailed_last_login

                    login_date = (
                        parse_rocketchat_date(
                            last_login
                        )
                    )

                    if login_date is None:

                        category = (
                            "INVALID_LAST_LOGIN"
                        )

                    else:

                        inactive_days = (
                            now - login_date
                        ).days

                        if login_date < cutoff_date:

                            category = (
                                f"INACTIVE_"
                                f"{INACTIVE_MONTHS}_MONTHS"
                            )

                        else:

                            category = "ACTIVE"

                else:

                    # ------------------------------------------------
                    # No login. Check account creation date.
                    # ------------------------------------------------

                    created_date = (
                        parse_rocketchat_date(
                            created_at
                        )
                    )

                    if created_date is None:

                        category = (
                            "UNKNOWN_NO_CREATED_DATE"
                        )

                    else:

                        account_age_days = (
                            now - created_date
                        ).days

                        if (
                            account_age_days
                            < NEW_ACCOUNT_DAYS
                        ):

                            category = "NEW_ACCOUNT"

                        else:

                            category = (
                                "NEVER_LOGGED_IN"
                            )

        # ====================================================
        # Store result
        # ====================================================

        results.append({
            "username": username,
            "name": name,
            "email": email,
            "createdAt": created_at,
            "account_age_days": account_age_days,
            "lastLogin": last_login or "",
            "inactive_days": inactive_days,
            "category": category,
            "active": active,
            "type": user_type,
            "roles": roles
        })

    return (
        results,
        cutoff_date,
        users_info_requests,
        users_info_errors
    )


# ============================================================
# Write CSV
# ============================================================

def write_csv(results):

    fieldnames = [
        "username",
        "name",
        "email",
        "createdAt",
        "account_age_days",
        "lastLogin",
        "inactive_days",
        "category",
        "active",
        "type",
        "roles"
    ]

    try:

        with open(
            OUTPUT_FILE,
            "w",
            newline="",
            encoding="utf-8-sig"
        ) as csvfile:

            writer = csv.DictWriter(
                csvfile,
                fieldnames=fieldnames
            )

            writer.writeheader()

            writer.writerows(results)

    except Exception as e:

        print(
            "ERROR: Could not create CSV."
        )

        print(f"Details: {e}")

        sys.exit(1)


# ============================================================
# Main
# ============================================================

def main():

    print(
        "=============================================="
    )

    print(
        " Rocket.Chat User Login Audit"
    )

    print(
        "=============================================="
    )

    print()

    print(
        "Connecting to Rocket.Chat..."
    )

    users = get_users()

    print(
        f"Users retrieved: {len(users)}"
    )

    print()

    (
        results,
        cutoff_date,
        users_info_requests,
        users_info_errors
    ) = process_users(users)

    write_csv(results)

    # ========================================================
    # Statistics
    # ========================================================

    active = sum(
        1
        for user in results
        if user["category"] == "ACTIVE"
    )

    inactive = sum(
        1
        for user in results
        if user["category"]
        == f"INACTIVE_{INACTIVE_MONTHS}_MONTHS"
    )

    never_logged = sum(
        1
        for user in results
        if user["category"]
        == "NEVER_LOGGED_IN"
    )

    new_accounts = sum(
        1
        for user in results
        if user["category"] == "NEW_ACCOUNT"
    )

    unknown = sum(
        1
        for user in results
        if user["category"]
        == "UNKNOWN_NO_CREATED_DATE"
    )

    invalid = sum(
        1
        for user in results
        if user["category"]
        == "INVALID_LAST_LOGIN"
    )

    print(
        "=============================================="
    )

    print(
        " Results"
    )

    print(
        "=============================================="
    )

    print(
        f"Cutoff date:          "
        f"{cutoff_date.isoformat()}"
    )

    print(
        f"New accounts:         "
        f"{new_accounts}"
    )

    print(
        f"Active:               "
        f"{active}"
    )

    print(
        f"Inactive > "
        f"{INACTIVE_MONTHS} months: "
        f"{inactive}"
    )

    print(
        f"Never logged in:      "
        f"{never_logged}"
    )

    print(
        f"Unknown created date: "
        f"{unknown}"
    )

    print(
        f"Invalid login:        "
        f"{invalid}"
    )

    print()

    print(
        f"users.info requests:  "
        f"{users_info_requests}"
    )

    print(
        f"users.info errors:    "
        f"{users_info_errors}"
    )

    print()

    print(
        f"CSV generated:        "
        f"{OUTPUT_FILE}"
    )

    print(
        "=============================================="
    )


# ============================================================
# Entry point
# ============================================================

if __name__ == "__main__":
    main()