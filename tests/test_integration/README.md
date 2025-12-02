# Integration Tests with VCR Cassettes

This directory contains integration tests that verify RTFD works correctly with real external APIs (PyPI, npm, GitHub, Crates.io, etc.).

## How It Works

Instead of hitting external APIs every time tests run, we use [pytest-recording](https://github.com/kiwicom/pytest-recording) (powered by VCR.py) to:

1. **Record** real API responses to YAML "cassette" files (first run)
2. **Replay** those responses in subsequent test runs (fast, deterministic, offline)
3. **Detect breaking changes** when APIs change their response format

## Running Tests

### Run with existing cassettes (default - no network access)
```bash
pytest tests/test_integration
```

This uses pre-recorded cassettes from `tests/cassettes/`. No network access needed.

### Run unit tests only (skip integration)
```bash
pytest tests -m "not integration"
```

### Run integration tests only
```bash
pytest tests/test_integration -m "integration"
```

## Recording/Updating Cassettes

### Record missing cassettes
If a cassette doesn't exist, record it:
```bash
pytest tests/test_integration --record-mode=once
```

This will:
- Use existing cassettes for tests that have them
- Make real API calls and record new cassettes for tests that don't

### Re-record all cassettes from scratch
To update cassettes with fresh API responses:
```bash
pytest tests/test_integration --record-mode=rewrite
```

**⚠️ Warning:** This deletes and re-records ALL cassettes.

### Record a specific test
```bash
pytest tests/test_integration/test_pypi_integration.py::test_pypi_search_library_requests_package --record-mode=rewrite
```

## Understanding Cassette Files

Cassettes are stored in `tests/cassettes/` as YAML files. They look like:

```yaml
interactions:
- request:
    method: GET
    uri: https://pypi.org/pypi/requests/json
  response:
    status:
      code: 200
    body:
      string: '{"info": {"name": "requests", ...}}'
    headers:
      Content-Type: application/json
```

## Why Cassettes?

### ✅ Benefits
- **Fast**: No network I/O in CI/CD (milliseconds vs seconds)
- **Reliable**: No flaky tests due to network issues or rate limits
- **Offline**: Tests work without internet
- **Detect API changes**: If PyPI changes their JSON structure, tests fail
- **Reproducible**: Same results on every machine

### ❌ Tradeoffs
- **Stale data**: Cassettes need periodic updates
- **Storage**: YAML files in version control
- **Initial setup**: Must record cassettes once

## When to Update Cassettes

Update cassettes when:
- ✅ An external API changes (test fails, need to verify it's real)
- ✅ Adding new integration tests
- ✅ Periodic refresh (monthly/quarterly) to ensure data isn't too stale
- ✅ Changing what data you extract from API responses

Don't update cassettes when:
- ❌ Fixing bugs in your own code (unless bug was due to misunderstanding API)
- ❌ Changing test assertions (unless API actually changed)

## Sensitive Data

The `vcr_config` fixture in `tests/conftest.py` filters sensitive headers:
- `Authorization`
- `X-API-Key`
- API keys in query parameters

This prevents accidentally committing tokens to cassettes.

## CI/CD Behavior

In GitHub Actions (`.github/workflows/test.yml`):
- Unit tests run with `-m "not integration"` (skip integration tests)
- Integration tests run with `--record-mode=none` (fail if cassette missing)

This ensures:
- Tests are fast (no network calls)
- We detect if someone forgot to commit a cassette
- No accidental API calls in CI that could hit rate limits

## Troubleshooting

### "Could not find cassette" error
- Run with `--record-mode=once` to record the missing cassette
- Commit the new cassette file to version control

### API changed, tests fail
1. Verify the API actually changed (check API docs/changelog)
2. Update your code to handle the new API format
3. Re-record cassettes: `--record-mode=rewrite`
4. Commit updated cassettes

### Rate limited during recording
- Add delays between tests if needed
- Use environment variables for auth tokens (reduces rate limits)
- Record cassettes in smaller batches

## Example Workflow

Adding a new integration test:

```bash
# 1. Write the test
vim tests/test_integration/test_new_provider.py

# 2. Record cassette (makes real API call)
pytest tests/test_integration/test_new_provider.py --record-mode=once

# 3. Verify cassette was created
ls tests/cassettes/test_integration/test_new_provider/

# 4. Run test again (uses cassette, no network)
pytest tests/test_integration/test_new_provider.py

# 5. Commit both test and cassette
git add tests/test_integration/test_new_provider.py
git add tests/cassettes/test_integration/test_new_provider/
git commit -m "test: add integration test for new provider"
```

## Further Reading

- [pytest-recording documentation](https://github.com/kiwicom/pytest-recording)
- [VCR.py documentation](https://vcrpy.readthedocs.io/)
- [pytest markers](https://docs.pytest.org/en/stable/example/markers.html)
