"""Tests for content utilities."""

import pytest
from unittest.mock import patch
from src.RTFD.content_utils import (
    html_to_markdown,
    convert_rst_to_markdown,
    extract_sections,
    Section,
    score_section,
    prioritize_sections,
    smart_truncate,
    convert_relative_urls,
)


def test_html_to_markdown_basic():
    """Test basic HTML to Markdown conversion."""
    html = "<h1>Title</h1><p>Content</p>"
    expected = "# Title\n\nContent"
    assert html_to_markdown(html) == expected


def test_html_to_markdown_with_base_url():
    """Test HTML to Markdown conversion with base URL."""
    html = '<a href="page.html">Link</a><img src="image.png" alt="Image">'
    base_url = "https://example.com/docs"

    markdown = html_to_markdown(html, base_url)
    assert "[Link](https://example.com/docs/page.html)" in markdown
    assert "![Image](https://example.com/docs/image.png)" in markdown


def test_convert_rst_to_markdown_success():
    """Test successful RST to Markdown conversion."""
    # Using a simple body content, as docutils might split title/body
    rst = "This is a paragraph.\n\n* List item"
    markdown = convert_rst_to_markdown(rst)

    assert "This is a paragraph." in markdown
    assert "List item" in markdown
    assert "-" in markdown or "*" in markdown  # List marker


def test_convert_rst_to_markdown_failure():
    """Test RST conversion failure handling (returns original)."""
    rst = "Valid RST content"

    # Mock publish_parts to raise an exception
    with patch("src.RTFD.content_utils.publish_parts", side_effect=Exception("Conversion failed")):
        result = convert_rst_to_markdown(rst)
        assert result == rst


def test_extract_sections_basic():
    """Test extracting sections from Markdown."""
    markdown = "# Section 1\nContent 1\n\n## Section 2\nContent 2"
    sections = extract_sections(markdown)

    assert len(sections) == 2
    assert sections[0].title == "Section 1"
    assert sections[0].level == 1
    assert "Content 1" in sections[0].content

    assert sections[1].title == "Section 2"
    assert sections[1].level == 2
    assert "Content 2" in sections[1].content


def test_extract_sections_no_headings():
    """Test extracting sections when there are no headings."""
    markdown = "Just some text without headings."
    sections = extract_sections(markdown)
    assert len(sections) == 1
    assert sections[0].content == markdown
    assert sections[0].title == ""


def test_score_section():
    """Test section scoring logic."""
    assert score_section("Installation") == 90
    assert score_section("Usage Guide") == 85  # Matches 'guide' (85) > 'usage' (80)
    assert score_section("API Reference") == 70
    assert score_section("Random Section") == 30  # Default


def test_prioritize_sections():
    """Test prioritizing sections within size limit."""
    # Use real sizes for consistency
    c1 = "Intro content"
    c2 = "Install content"
    c3 = "API content"

    s1 = Section(1, "Intro", c1, 100, len(c1))   # 13 bytes
    s2 = Section(2, "Install", c2, 90, len(c2))  # 15 bytes
    s3 = Section(2, "API", c3, 70, len(c3))      # 11 bytes

    sections = [s1, s2, s3]

    # Large limit: should include all
    result = prioritize_sections(sections, max_bytes=100)
    assert c1 in result
    assert c2 in result
    assert c3 in result

    # Limit 30 bytes:
    # 1. Intro (13) added. Remaining: 17.
    # 2. Install (15) <= 17? Yes. Added. Remaining: 2.
    # 3. API (11) <= 2? No. Skipped.

    result = prioritize_sections(sections, max_bytes=30)
    assert c1 in result
    assert c2 in result
    assert c3 not in result


def test_smart_truncate():
    """Test smart truncation logic."""
    text = "Paragraph one.\n\nParagraph two.\n\nParagraph three."

    # If we allow 19 bytes, it should keep the first paragraph.
    # "Paragraph one." (14) + "\n\n..." (5) = 19 bytes.
    # 19 * 0.7 = 13.3 < 14 (break index), so it should work.
    truncated = smart_truncate(text, 19)
    assert "Paragraph one." in truncated
    assert "..." in truncated
    assert "Paragraph two" not in truncated

    # Test sentence break
    text2 = "Sentence one. Sentence two."
    # "Sentence one." is 13 bytes.
    # Allow 15 bytes.
    truncated2 = smart_truncate(text2, 15)
    assert "Sentence one." in truncated2
    assert "Sentence two" not in truncated2


def test_convert_relative_urls():
    """Test relative URL conversion."""
    base = "https://example.com/docs"

    # Relative link
    assert convert_relative_urls("[Link](page.html)", base) == "[Link](https://example.com/docs/page.html)"

    # Absolute link (should not change)
    assert convert_relative_urls("[Link](http://google.com)", base) == "[Link](http://google.com)"

    # Root relative link
    assert convert_relative_urls("[Link](/root.html)", base) == "[Link](https://example.com/root.html)"

    # Image
    assert convert_relative_urls("![Img](img.png)", base) == "![Img](https://example.com/docs/img.png)"
