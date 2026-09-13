#!/usr/bin/env python3
"""
Fetches WakaTime editor stats and computes total coding time,
excluding AI CLI agents (Claude Code, Codex CLI, etc.) that WakaTime
logs as if they were editors. Writes a shields.io badge line into
README.md between the WAKATIME marker comments.

Requires env var WAKATIME_API_KEY (WakaTime API key, from
https://wakatime.com/settings/api-key).
"""

import base64
import os
import re
import sys
import urllib.request
import json

# Range to pull. Options: last_7_days, last_30_days, last_6_months, last_year, all_time
RANGE = os.environ.get("WAKATIME_RANGE", "last_7_days")

# Editor names to exclude from the total — extend this list as you pick up
# new AI coding tools that WakaTime tracks as "editors".
EXCLUDED_EDITORS = {
    e.strip().lower()
    for e in os.environ.get(
        "WAKATIME_EXCLUDED_EDITORS",
        "Antigravity CLI,Antigravity IDE,Antigravity,Claude Code,Codex CLI,"
        "Copilot CLI,Grok Build,Amp CLI,OpenCode,Cursor Agent",
    ).split(",")
    if e.strip()
}

README_PATH = "README.md"
START_MARKER = "<!--WAKATIME:START-->"
END_MARKER = "<!--WAKATIME:END-->"


def fetch_stats(api_key: str) -> dict:
    url = f"https://wakatime.com/api/v1/users/current/stats/{RANGE}"
    token = base64.b64encode(api_key.encode()).decode()
    req = urllib.request.Request(url, headers={"Authorization": f"Basic {token}"})
    with urllib.request.urlopen(req) as resp:
        return json.load(resp)


def seconds_to_hm(total_seconds: float) -> str:
    total_minutes = round(total_seconds / 60)
    h, m = divmod(total_minutes, 60)
    return f"{h}h {m}m" if h else f"{m}m"


def compute_filtered_total(stats: dict) -> tuple[str, float]:
    editors = stats.get("data", {}).get("editors", [])
    kept = [e for e in editors if e.get("name", "").strip().lower() not in EXCLUDED_EDITORS]
    total_seconds = sum(e.get("total_seconds", 0) for e in kept)
    return seconds_to_hm(total_seconds), total_seconds


def build_badge_markdown(time_str: str) -> str:
    label = "Coding%20Time"
    # shields.io static badge — spaces become %20, dashes are literal
    value = time_str.replace(" ", "%20")
    range_label = RANGE.replace("_", " ")
    badge_url = f"https://img.shields.io/badge/{label}-{value}-blue"
    return (
        f'<img src="{badge_url}" alt="Coding time ({range_label})" />'
    )


def update_readme(badge_markdown: str) -> bool:
    with open(README_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    if START_MARKER not in content or END_MARKER not in content:
        print(
            f"Markers {START_MARKER} / {END_MARKER} not found in {README_PATH}. "
            "Add them where you want the badge to appear.",
            file=sys.stderr,
        )
        return False

    pattern = re.compile(
        re.escape(START_MARKER) + r".*?" + re.escape(END_MARKER), re.DOTALL
    )
    replacement = f"{START_MARKER}\n{badge_markdown}\n{END_MARKER}"
    new_content = pattern.sub(replacement, content)

    if new_content == content:
        return False

    with open(README_PATH, "w", encoding="utf-8") as f:
        f.write(new_content)
    return True


def main() -> None:
    api_key = os.environ.get("WAKATIME_API_KEY")
    if not api_key:
        print("WAKATIME_API_KEY environment variable is not set.", file=sys.stderr)
        sys.exit(1)

    stats = fetch_stats(api_key)
    time_str, _ = compute_filtered_total(stats)
    badge_markdown = build_badge_markdown(time_str)
    changed = update_readme(badge_markdown)

    print(f"Computed time: {time_str}")
    print("README updated." if changed else "No change to README.")

    # Expose for the workflow step that decides whether to commit.
    gh_output = os.environ.get("GITHUB_OUTPUT")
    if gh_output:
        with open(gh_output, "a", encoding="utf-8") as f:
            f.write(f"changed={'true' if changed else 'false'}\n")


if __name__ == "__main__":
    main()
