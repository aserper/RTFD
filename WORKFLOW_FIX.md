# GitHub Workflow Issue Analysis & Solutions

## Issues Identified

### Issue 1: Publish workflow doesn't trigger automatically
**Root Cause**: GitHub Actions security limitation - workflows using `GITHUB_TOKEN` cannot trigger other workflows. When `release.yml` creates a release, it doesn't trigger `publish.yml`.

**Why this happens**:
- `release.yml` uses `GITHUB_TOKEN` to create releases
- GitHub prevents `GITHUB_TOKEN` from triggering subsequent workflows (prevents infinite loops)
- The `publish.yml` workflow listens for `release.types: [published]` but never receives the event

### Issue 2: PyPI badge shows old version
**Root Cause**: shields.io caching
- The badge URL `https://img.shields.io/pypi/v/rtfd-mcp.svg` caches for several hours
- PyPI itself shows the correct version (0.2.0)
- This is cosmetic and will auto-resolve within a few hours

## Solutions

### Solution A: Use Personal Access Token (PAT)
**Pros**: Keeps two separate workflows
**Cons**: Requires creating and managing a PAT secret

1. Create a PAT with `repo` and `workflow` scopes
2. Add it as repository secret named `PAT`
3. Update release.yml line 28:
```yaml
token: ${{ secrets.PAT || secrets.GITHUB_TOKEN }}
```

This allows the workflow to trigger other workflows while falling back gracefully.

### Solution B: Combine workflows (RECOMMENDED)
**Pros**: Simpler, no PAT needed, everything in one place
**Cons**: Longer single workflow

Merge release.yml and publish.yml into a single workflow:

```yaml
name: Release and Publish to PyPI

on:
  workflow_dispatch:
    inputs:
      bump_type:
        description: 'Version bump type'
        required: true
        default: 'patch'
        type: choice
        options:
          - patch
          - minor
          - major

jobs:
  release-and-publish:
    runs-on: ubuntu-latest
    permissions:
      contents: write
      id-token: write  # For PyPI trusted publishing

    steps:
    - uses: actions/checkout@v4
      with:
        fetch-depth: 0

    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.10'

    - name: Configure git
      run: |
        git config user.name "github-actions[bot]"
        git config user.email "github-actions[bot]@users.noreply.github.com"

    - name: Bump version
      run: python scripts/bump_version.py ${{ inputs.bump_type }}

    - name: Get new version
      id: version
      run: |
        import re
        import os
        with open('pyproject.toml') as f:
          content = f.read()
        match = re.search(r'version\s*=\s*"([^"]+)"', content)
        version = match.group(1)
        with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
          f.write(f"version={version}\n")
      shell: python

    - name: Commit version bump
      run: |
        git add pyproject.toml src/RTFD/__init__.py
        git commit -m "chore: bump version to ${{ steps.version.outputs.version }}"

    - name: Create tag
      run: |
        git tag v${{ steps.version.outputs.version }}

    - name: Push changes
      run: |
        git push origin main
        git push origin v${{ steps.version.outputs.version }}

    - name: Install build dependencies
      run: |
        python -m pip install --upgrade pip
        pip install build twine

    - name: Build distributions
      run: python -m build

    - name: Check distributions with twine
      run: twine check dist/*

    - name: Publish to PyPI
      uses: pypa/gh-action-pypi-publish@release/v1
      with:
        password: ${{ secrets.PYPI_API_TOKEN }}

    - name: Create GitHub Release
      uses: softprops/action-gh-release@v1
      with:
        tag_name: v${{ steps.version.outputs.version }}
        name: v${{ steps.version.outputs.version }}
        body: |
          Version ${{ steps.version.outputs.version }} has been released to PyPI.

          See [the changelog](https://github.com/${{ github.repository }}/commits/main) for changes in this release.
        draft: false
        prerelease: false
```

### Solution C: Add manual trigger to publish workflow
Keep both workflows but add manual dispatch option to publish:

```yaml
on:
  release:
    types: [published]
  workflow_dispatch:
    inputs:
      tag:
        description: 'Tag to publish (e.g., v0.2.0)'
        required: true
```

Then manually run publish after release completes.

## Recommendation

**Use Solution B** - combine the workflows. This:
- Eliminates the trigger issue entirely
- Simplifies maintenance (one file instead of two)
- Ensures atomic operation (version bump + publish in single workflow)
- No need for PAT secrets
- Clearer workflow logs

## For PyPI Badge Issue

No action needed - it's just caching. Options to force refresh:
1. Wait 2-6 hours for automatic cache expiry
2. Use `?v=<timestamp>` query parameter (but not worth it)
3. Ignore - it will update automatically

The badge URL is working correctly, shields.io just caches the response.
