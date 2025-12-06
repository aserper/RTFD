#!/usr/bin/env python3
"""Semantic version bumping utility for RTFD project.

Usage:
    python scripts/bump_version.py patch   # 0.1.0 -> 0.1.1
    python scripts/bump_version.py minor   # 0.1.0 -> 0.2.0
    python scripts/bump_version.py major   # 0.1.0 -> 1.0.0
    python scripts/bump_version.py 0.2.0   # Set to specific version
"""

import re
import sys
from pathlib import Path


def parse_version(version_str: str) -> tuple[int, int, int]:
    """Parse semantic version string into (major, minor, patch) tuple."""
    match = re.match(r"^(\d+)\.(\d+)\.(\d+)$", version_str.strip())
    if not match:
        raise ValueError(f"Invalid version format: {version_str}")
    return tuple(int(x) for x in match.groups())


def bump_version(current: str, bump_type: str) -> str:
    """Bump version according to semantic versioning rules.

    Args:
        current: Current version string (e.g., "0.1.0")
        bump_type: One of "major", "minor", "patch" or a specific version

    Returns:
        New version string
    """
    # If bump_type looks like a version, use it directly
    if "." in bump_type and bump_type[0].isdigit():
        try:
            parse_version(bump_type)
            return bump_type
        except ValueError:
            pass

    major, minor, patch = parse_version(current)

    if bump_type == "major":
        return f"{major + 1}.0.0"
    elif bump_type == "minor":
        return f"{major}.{minor + 1}.0"
    elif bump_type == "patch":
        return f"{major}.{minor}.{patch + 1}"
    else:
        raise ValueError(
            f"Invalid bump type: {bump_type}. Use 'major', 'minor', 'patch', or a version like '0.2.0'"
        )


def update_pyproject_toml(new_version: str) -> str:
    """Update version in pyproject.toml.

    Args:
        new_version: New version string

    Returns:
        Path to the updated file
    """
    pyproject_path = Path(__file__).parent.parent / "pyproject.toml"

    content = pyproject_path.read_text()

    # Match the version line in [project] section
    pattern = r'(version\s*=\s*")[^"]*(")'
    new_content = re.sub(pattern, rf"\g<1>{new_version}\g<2>", content)

    if new_content == content:
        raise ValueError("Could not find version in pyproject.toml")

    pyproject_path.write_text(new_content)
    return str(pyproject_path)


def update_init_py(new_version: str) -> str:
    """Update version in src/RTFD/__init__.py.

    Args:
        new_version: New version string

    Returns:
        Path to the updated file
    """
    init_path = Path(__file__).parent.parent / "src" / "RTFD" / "__init__.py"

    content = init_path.read_text()

    # If __version__ exists, update it
    if "__version__" in content:
        pattern = r'(__version__\s*=\s*")[^"]*(")'
        new_content = re.sub(pattern, rf"\g<1>{new_version}\g<2>", content)
    else:
        # Add __version__ at the top
        new_content = f'__version__ = "{new_version}"\n\n{content}'

    init_path.write_text(new_content)
    return str(init_path)


def get_current_version() -> str:
    """Get current version from pyproject.toml."""
    pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
    content = pyproject_path.read_text()

    match = re.search(r'version\s*=\s*"([^"]+)"', content)
    if not match:
        raise ValueError("Could not find version in pyproject.toml")

    return match.group(1)


def main():
    """Main entry point."""
    if len(sys.argv) != 2:
        print("Usage: python scripts/bump_version.py [major|minor|patch|X.Y.Z]")
        sys.exit(1)

    bump_type = sys.argv[1]

    try:
        current_version = get_current_version()
        print(f"Current version: {current_version}")

        new_version = bump_version(current_version, bump_type)
        print(f"New version:     {new_version}")

        # Update files
        pyproject_updated = update_pyproject_toml(new_version)
        print(f"✓ Updated {pyproject_updated}")

        init_updated = update_init_py(new_version)
        print(f"✓ Updated {init_updated}")

        print(f"\n✓ Version bumped from {current_version} to {new_version}")
        print("\nNext steps:")
        print("  1. git add .")
        print(f"  2. git commit -m 'chore: bump version to {new_version}'")
        print(f"  3. git tag v{new_version}")
        print("  4. git push && git push --tags")
        print("  5. Create GitHub release (or trigger release.yml workflow)")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
