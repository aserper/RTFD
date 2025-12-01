# Contributing to RTFD

Thank you for your interest in contributing to RTFD! This document outlines how to contribute code and how the release process works.

## Development Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/aserper/RTFD.git
   cd RTFD
   ```

2. Install in development mode:
   ```bash
   pip install -e .
   # or with uv:
   uv pip install -e .
   ```

3. Run tests:
   ```bash
   pytest
   ```

## Making Changes

1. Create a feature branch:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. Make your changes and commit with clear messages:
   ```bash
   git commit -m "feat: add new feature"
   # or
   git commit -m "fix: resolve issue with X"
   ```

3. Push and create a pull request on GitHub

## Release Process

RTFD uses automated releases to PyPI. Here's how to create a release:

### Option 1: GitHub UI (Recommended)

1. Go to your fork/repository on GitHub
2. Navigate to the **Actions** tab
3. Select the **"Release to PyPI"** workflow
4. Click **"Run workflow"** button
5. Select the version bump type:
   - **patch**: Bug fixes (0.1.0 → 0.1.1)
   - **minor**: New features (0.1.0 → 0.2.0)
   - **major**: Breaking changes (0.1.0 → 1.0.0)
6. Click **"Run workflow"**

The workflow will:
- Bump the version in `pyproject.toml` and `src/RTFD/__init__.py`
- Create a commit and git tag (e.g., `v0.1.1`)
- Create a GitHub release
- Automatically publish to PyPI

### Option 2: GitHub CLI

```bash
gh workflow run release.yml -f bump_type=patch
```

### Option 3: Manual Release (Fallback)

If you need to manually release:

1. Bump the version:
   ```bash
   python scripts/bump_version.py patch
   ```

2. Commit and tag:
   ```bash
   git add .
   git commit -m "chore: bump version to X.Y.Z"
   git tag vX.Y.Z
   git push && git push --tags
   ```

3. Create a GitHub release through the web UI or CLI:
   ```bash
   gh release create vX.Y.Z --title "vX.Y.Z" --notes "Release notes here"
   ```

This will trigger the publish workflow automatically.

## Version Bumping Details

The `scripts/bump_version.py` script handles semantic versioning:

```bash
python scripts/bump_version.py major   # 0.1.0 → 1.0.0
python scripts/bump_version.py minor   # 0.1.0 → 0.2.0
python scripts/bump_version.py patch   # 0.1.0 → 0.1.1
python scripts/bump_version.py 1.2.3   # Set to specific version
```

This updates:
- `pyproject.toml` - Project metadata version
- `src/RTFD/__init__.py` - Package `__version__` attribute

## Code Quality

- Follow PEP 8 style guidelines
- Write clear commit messages
- Include docstrings for public functions
- Add tests for new features
- Ensure all tests pass before submitting PR

## Questions?

Feel free to open an issue or discussion if you have questions about the contribution process!
