"""Tests for GitHub authentication methods in utils.py."""

import os
from unittest.mock import MagicMock, patch

import pytest

from src.RTFD.utils import get_github_token


@pytest.fixture(autouse=True)
def clear_env_vars():
    """Clear GitHub-related environment variables before and after tests."""
    # Save original values
    original_github_token = os.environ.get("GITHUB_TOKEN")
    original_github_auth = os.environ.get("GITHUB_AUTH")

    # Clear variables for test
    if "GITHUB_TOKEN" in os.environ:
        del os.environ["GITHUB_TOKEN"]
    if "GITHUB_AUTH" in os.environ:
        del os.environ["GITHUB_AUTH"]

    yield

    # Restore original values
    if original_github_token is not None:
        os.environ["GITHUB_TOKEN"] = original_github_token
    elif "GITHUB_TOKEN" in os.environ:
        del os.environ["GITHUB_TOKEN"]

    if original_github_auth is not None:
        os.environ["GITHUB_AUTH"] = original_github_auth
    elif "GITHUB_AUTH" in os.environ:
        del os.environ["GITHUB_AUTH"]


def test_get_github_token_default_no_token():
    """Test get_github_token with default settings (token method) but no token available."""
    with patch("src.RTFD.utils.logger.error") as mock_logger:
        assert get_github_token() is None
        mock_logger.assert_called_once()


def test_get_github_token_with_token_env():
    """Test get_github_token with token method and token available."""
    os.environ["GITHUB_TOKEN"] = "test_token"
    assert get_github_token() == "test_token"


def test_get_github_token_disabled():
    """Test get_github_token with disabled method."""
    os.environ["GITHUB_AUTH"] = "disabled"
    os.environ["GITHUB_TOKEN"] = "test_token"
    assert get_github_token() is None


def test_get_github_token_cli_method():
    """Test get_github_token with cli method."""
    os.environ["GITHUB_AUTH"] = "cli"

    # Mock successful gh CLI execution
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "cli_test_token\n"

    with (
        patch("src.RTFD.utils.shutil.which", return_value=True),
        patch("src.RTFD.utils.subprocess.run", return_value=mock_result),
    ):
        assert get_github_token() == "cli_test_token"


def test_get_github_token_cli_method_no_gh():
    """Test get_github_token with cli method but gh CLI not available."""
    os.environ["GITHUB_AUTH"] = "cli"

    with (
        patch("src.RTFD.utils.shutil.which", return_value=None),
        patch("src.RTFD.utils.logger.error") as mock_logger,
    ):
        assert get_github_token() is None
        mock_logger.assert_called_once()


def test_get_github_token_cli_method_gh_error():
    """Test get_github_token with cli method but gh CLI returns an error."""
    os.environ["GITHUB_AUTH"] = "cli"

    # Mock failed gh CLI execution
    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stdout = ""

    with (
        patch("src.RTFD.utils.shutil.which", return_value=True),
        patch("src.RTFD.utils.subprocess.run", return_value=mock_result),
        patch("src.RTFD.utils.logger.error") as mock_logger,
    ):
        assert get_github_token() is None
        mock_logger.assert_called_once()


def test_get_github_token_auto_method_with_token():
    """Test get_github_token with auto method and token available."""
    os.environ["GITHUB_AUTH"] = "auto"
    os.environ["GITHUB_TOKEN"] = "auto_test_token"
    assert get_github_token() == "auto_test_token"


def test_get_github_token_auto_method_fallback_to_cli():
    """Test get_github_token with auto method, falling back to CLI when token not available."""
    os.environ["GITHUB_AUTH"] = "auto"

    # Mock successful gh CLI execution
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "fallback_test_token\n"

    with (
        patch("src.RTFD.utils.shutil.which", return_value=True),
        patch("src.RTFD.utils.subprocess.run", return_value=mock_result),
    ):
        assert get_github_token() == "fallback_test_token"


def test_get_github_token_auto_method_no_token_no_cli():
    """Test get_github_token with auto method but no token and no CLI available."""
    os.environ["GITHUB_AUTH"] = "auto"

    with (
        patch("src.RTFD.utils.shutil.which", return_value=None),
        patch("src.RTFD.utils.logger.error") as mock_logger,
    ):
        assert get_github_token() is None
        mock_logger.assert_called_once()
