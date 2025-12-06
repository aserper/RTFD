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
   uv sync --extra dev
   ```

3. Run tests:
   ```bash
   uv run pytest
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

3. **Update the CHANGELOG.md**:
   - Add your changes under the `[Unreleased]` section
   - **Note**: Do not create a new version header. The release process will automatically move your `[Unreleased]` changes to a new version section.
   - Follow the [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) format
   - Use categories: `Added`, `Changed`, `Deprecated`, `Removed`, `Fixed`, `Security`
   - Write clear, user-focused descriptions
   - Example:
     ```markdown
     ## [Unreleased]

     ### Added
     - New feature X that allows users to do Y

     ### Fixed
     - Issue with Z that caused incorrect behavior
     ```

4. Push and create a pull request on GitHub

## Code Quality

- Follow PEP 8 style guidelines
- Write clear commit messages
- Include docstrings for public functions
- Add tests for new features
- Ensure all tests pass before submitting PR

## Questions?

Feel free to open an issue or discussion if you have questions about the contribution process!
