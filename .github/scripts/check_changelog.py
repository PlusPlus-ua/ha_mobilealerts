#!/usr/bin/env python3
"""Keep CHANGELOG.md in step with the integration.

Checks (all must pass):
  1. The newest CHANGELOG heading equals the version in manifest.json.
  2. That newest section has a date and at least one bullet.
  3. Version headings are unique and in descending order.
  4. If the change being checked (BASE_SHA..HEAD_SHA) touches anything under
     custom_components/, CHANGELOG.md must be part of the same change.

Rule 4 only runs when BASE_SHA and HEAD_SHA are set (the workflow sets them).
Run locally from the repository root:  python3 .github/scripts/check_changelog.py
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "custom_components" / "mobile_alerts" / "manifest.json"
CHANGELOG = ROOT / "CHANGELOG.md"
CODE_PREFIX = "custom_components/"

HEADING = re.compile(
    r"^## \[(?P<version>\d+(?:\.\d+)*)\](?: - (?P<date>\d{4}-\d{2}-\d{2}))?[ \t]*$",
    re.MULTILINE,
)

errors: list[str] = []


def error(message: str) -> None:
    errors.append(message)
    print(f"::error file=CHANGELOG.md::{message}")


def version_key(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def check_changelog_matches_manifest() -> None:
    manifest_version = json.loads(MANIFEST.read_text(encoding="utf-8"))["version"]
    text = CHANGELOG.read_text(encoding="utf-8")
    headings = list(HEADING.finditer(text))

    if not headings:
        error("CHANGELOG.md has no '## [x.y.z] - YYYY-MM-DD' version headings.")
        return

    top = headings[0]
    top_version = top.group("version")

    # 1. newest heading == manifest version
    if top_version != manifest_version:
        error(
            f"manifest.json is at {manifest_version} but the newest CHANGELOG "
            f"heading is {top_version}. Add a '## [{manifest_version}]' section "
            "(or fix the manifest version)."
        )

    # 2. newest section has a date and at least one bullet
    if not top.group("date"):
        error(f"CHANGELOG heading [{top_version}] has no date ('## [{top_version}] - YYYY-MM-DD').")
    end = headings[1].start() if len(headings) > 1 else len(text)
    section = text[top.end():end]
    if not re.search(r"^\s*[-*] \S", section, re.MULTILINE):
        error(f"CHANGELOG section [{top_version}] has no bullet points describing the change.")

    # 3. unique and descending
    seen: set[str] = set()
    previous: tuple[int, ...] | None = None
    for heading in headings:
        version = heading.group("version")
        if version in seen:
            error(f"CHANGELOG lists version {version} more than once.")
        seen.add(version)
        key = version_key(version)
        if previous is not None and key >= previous:
            error(f"CHANGELOG version {version} is not older than the heading above it (newest first).")
        previous = key


def check_code_changes_have_changelog() -> None:
    base = os.environ.get("BASE_SHA", "").strip()
    head = os.environ.get("HEAD_SHA", "").strip()
    if not base or not head:
        print("Rule 4 skipped: BASE_SHA/HEAD_SHA not set.")
        return
    if set(base) == {"0"}:
        print("Rule 4 skipped: new branch, no previous commit to compare against.")
        return

    result = subprocess.run(
        ["git", "diff", "--name-only", base, head],
        cwd=ROOT, capture_output=True, text=True,
    )
    if result.returncode != 0:
        # e.g. a force push that removed BASE_SHA from history. Don't fail the build for that.
        print(f"::warning::Rule 4 skipped: could not diff {base[:8]}..{head[:8]}: {result.stderr.strip()}")
        return

    changed = [line for line in result.stdout.splitlines() if line]
    code = [name for name in changed if name.startswith(CODE_PREFIX)]
    print(f"Changed files in {base[:8]}..{head[:8]}: {len(changed)} ({len(code)} under {CODE_PREFIX})")
    if code and "CHANGELOG.md" not in changed:
        listed = ", ".join(code[:5]) + (" ..." if len(code) > 5 else "")
        error(
            f"Integration files changed ({listed}) but CHANGELOG.md was not updated in "
            "the same change. Add an entry (and bump the version in manifest.json)."
        )


def main() -> int:
    check_changelog_matches_manifest()
    check_code_changes_have_changelog()
    if errors:
        print(f"\nFAILED: {len(errors)} problem(s).")
        return 1
    print("OK: CHANGELOG.md matches manifest.json.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
