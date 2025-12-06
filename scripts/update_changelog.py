#!/usr/bin/env python3
"""Changelog management utility for RTFD project.

Handles updating CHANGELOG.md for releases, including:
- Validating [Unreleased] content
- Moving [Unreleased] to versioned section
- Updating comparison links
- Extracting release notes
"""

import argparse
import re
import sys
from datetime import date
from pathlib import Path

# Constants
CHANGELOG_FILE = Path("CHANGELOG.md")
PYPROJECT_FILE = Path("pyproject.toml")
REPO_URL = "https://github.com/aserper/rtfd"


def get_current_version() -> str:
    """Get current version from pyproject.toml."""
    if not PYPROJECT_FILE.exists():
        raise FileNotFoundError(f"{PYPROJECT_FILE} not found")

    content = PYPROJECT_FILE.read_text()
    match = re.search(r'version\s*=\s*"([^"]+)"', content)
    if not match:
        raise ValueError("Could not find version in pyproject.toml")
    return match.group(1)


def parse_version(version_str: str) -> tuple[int, int, int]:
    """Parse semantic version string."""
    match = re.match(r"^(\d+)\.(\d+)\.(\d+)$", version_str.strip())
    if not match:
        raise ValueError(f"Invalid version format: {version_str}")
    return tuple(int(x) for x in match.groups())


def calculate_new_version(current: str, bump_type: str) -> str:
    """Calculate new version based on bump type."""
    if "." in bump_type and bump_type[0].isdigit():
        return bump_type

    major, minor, patch = parse_version(current)

    if bump_type == "major":
        return f"{major + 1}.0.0"
    elif bump_type == "minor":
        return f"{major}.{minor + 1}.0"
    elif bump_type == "patch":
        return f"{major}.{minor}.{patch + 1}"
    else:
        raise ValueError(f"Invalid bump type: {bump_type}")


def validate_unreleased(content: str) -> bool:
    """Check if [Unreleased] section has actual content."""
    # Find content between ## [Unreleased] and the next ## [Version]
    pattern = r"## \[Unreleased\]\n(.*?)(\n## \[|$)"
    match = re.search(pattern, content, re.DOTALL)

    if not match:
        return False

    unreleased_content = match.group(1).strip()

    # Check if it's just empty subsections or whitespace
    # Remove standard subsections to see if anything else remains
    cleaned = re.sub(
        r"### (Added|Changed|Fixed|Removed|Deprecated|Security)", "", unreleased_content
    )
    cleaned = re.sub(r"\s+", "", cleaned)

    return len(cleaned) > 0


def extract_release_notes(content: str, version: str) -> str:
    """Extract release notes for a specific version."""
    # Escape dots in version for regex
    ver_pattern = re.escape(version)
    pattern = rf"## \[{ver_pattern}\] - \d{{4}}-\d{{2}}-\d{{2}}\n(.*?)(?=\n## \[|$)"
    match = re.search(pattern, content, re.DOTALL)

    if not match:
        raise ValueError(f"Could not find release notes for version {version}")

    return match.group(1).strip()


def update_changelog(bump_type: str, changelog_path: Path) -> str:
    """Update CHANGELOG.md for a new release."""
    if not changelog_path.exists():
        raise FileNotFoundError(f"{changelog_path} not found")

    content = changelog_path.read_text()

    # 1. Validate Unreleased content
    if not validate_unreleased(content):
        print(
            "Error: [Unreleased] section is empty. Add changes before releasing.", file=sys.stderr
        )
        sys.exit(1)

    # 2. Calculate versions
    current_version = get_current_version()
    new_version = calculate_new_version(current_version, bump_type)
    today = date.today().isoformat()

    print(f"Updating CHANGELOG for release: {new_version} ({today})")

    # 3. Move [Unreleased] to new version
    new_unreleased_section = f"""## [Unreleased]

### Added

### Changed

### Fixed

## [{new_version}] - {today}"""

    replacement = f"{new_unreleased_section}"
    new_content = content.replace("## [Unreleased]", replacement, 1)

    # 4. Update comparison links at the bottom
    link_pattern = r"\[Unreleased\]: (.*)/compare/v(.*)\.\.\.HEAD"
    link_match = re.search(link_pattern, new_content)

    if link_match:
        base_url = link_match.group(1)
        new_unreleased_link = f"[Unreleased]: {base_url}/compare/v{new_version}...HEAD"
        new_version_link = (
            f"[{new_version}]: {base_url}/compare/v{current_version}...v{new_version}"
        )

        links_replacement = f"{new_unreleased_link}\n{new_version_link}"
        new_content = re.sub(link_pattern, links_replacement, new_content)
    else:
        print("Warning: Could not find [Unreleased] link definition to update.", file=sys.stderr)

    changelog_path.write_text(new_content)
    return new_version


def main():
    parser = argparse.ArgumentParser(description="Manage CHANGELOG.md")
    parser.add_argument("--file", type=Path, default=CHANGELOG_FILE, help="Path to CHANGELOG.md")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # check command
    subparsers.add_parser("check", help="Validate [Unreleased] has content")

    # update command
    update_parser = subparsers.add_parser("update", help="Update CHANGELOG for release")
    update_parser.add_argument("bump_type", help="major, minor, patch, or specific version")

    # extract command
    extract_parser = subparsers.add_parser("extract", help="Extract release notes")
    extract_parser.add_argument("version", help="Version to extract notes for")

    args = parser.parse_args()
    changelog_path = args.file

    if args.command == "check":
        if not changelog_path.exists():
            print(f"{changelog_path} not found", file=sys.stderr)
            sys.exit(1)
        if validate_unreleased(changelog_path.read_text()):
            print("OK: [Unreleased] has content")
            sys.exit(0)
        else:
            print("FAIL: [Unreleased] is empty", file=sys.stderr)
            sys.exit(1)

    elif args.command == "update":
        try:
            new_ver = update_changelog(args.bump_type, changelog_path)
            print(new_ver)
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

    elif args.command == "extract":
        try:
            if not changelog_path.exists():
                raise FileNotFoundError(f"{changelog_path} not found")
            notes = extract_release_notes(changelog_path.read_text(), args.version)
            print(notes)
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
