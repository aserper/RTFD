"""Utilities for documentation content extraction and processing."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional
from io import StringIO

from markdownify import markdownify as md
from docutils.core import publish_parts


# Section priority keywords for smart content extraction
PRIORITY_KEYWORDS = {
    100: ["overview", "introduction", "about", "description"],
    90: ["install", "installation", "setup", "getting started", "get started"],
    85: ["quickstart", "quick start", "tutorial", "guide", "walkthrough"],
    80: ["usage", "example", "examples", "how to", "howto"],
    70: ["api", "reference", "methods", "functions", "classes"],
    60: ["configuration", "config", "options", "settings", "parameters"],
    50: ["advanced", "tips", "best practices", "patterns"],
    40: ["changelog", "history", "releases", "versions"],
}


@dataclass
class Section:
    """Represents a documentation section."""

    level: int  # Heading level (1=H1, 2=H2, etc.)
    title: str  # Heading text
    content: str  # Section content including heading
    priority: int  # Priority score for inclusion
    size_bytes: int  # UTF-8 byte size


def html_to_markdown(html: str, base_url: str = "") -> str:
    """
    Convert HTML to clean Markdown.

    Args:
        html: HTML content to convert
        base_url: Base URL for converting relative links to absolute

    Returns:
        Markdown string
    """
    # Convert HTML to Markdown using markdownify
    markdown = md(
        html,
        heading_style="ATX",  # Use # style headings
        bullets="-",  # Use - for bullets
        code_language="",  # Don't add language to code blocks by default
        strip=["script", "style"],  # Remove script and style tags
    )

    # Convert relative URLs to absolute if base_url provided
    if base_url:
        markdown = convert_relative_urls(markdown, base_url)

    return markdown.strip()


def convert_rst_to_markdown(rst: str) -> str:
    """
    Convert reStructuredText to Markdown.

    Args:
        rst: reStructuredText content

    Returns:
        Markdown string
    """
    try:
        # Convert reST to HTML using docutils
        parts = publish_parts(
            source=rst,
            writer_name="html",
            settings_overrides={
                "report_level": 5,  # Suppress warnings
                "halt_level": 5,  # Don't halt on errors
                "warning_stream": StringIO(),  # Suppress warnings
            },
        )

        # Extract the body HTML
        html_body = parts.get("body", "")

        # Convert HTML to Markdown
        markdown = html_to_markdown(html_body)

        return markdown

    except Exception as e:
        # If conversion fails, return original content
        # This is better than losing all content
        return rst


def extract_sections(markdown: str) -> List[Section]:
    """
    Parse Markdown into sections based on headings.

    Args:
        markdown: Markdown content to parse

    Returns:
        List of Section objects
    """
    if not markdown or not markdown.strip():
        return []

    sections: List[Section] = []
    lines = markdown.split("\n")

    current_section_lines: List[str] = []
    current_level = 0
    current_title = ""

    for line in lines:
        # Check if line is a heading
        heading_match = re.match(r"^(#{1,6})\s+(.+)$", line)

        if heading_match:
            # Save previous section if it exists
            if current_section_lines:
                section_content = "\n".join(current_section_lines)
                sections.append(
                    Section(
                        level=current_level,
                        title=current_title,
                        content=section_content,
                        priority=score_section(current_title),
                        size_bytes=len(section_content.encode("utf-8")),
                    )
                )

            # Start new section
            current_level = len(heading_match.group(1))
            current_title = heading_match.group(2).strip()
            current_section_lines = [line]
        else:
            current_section_lines.append(line)

    # Save last section
    if current_section_lines:
        section_content = "\n".join(current_section_lines)
        sections.append(
            Section(
                level=current_level,
                title=current_title,
                content=section_content,
                priority=score_section(current_title),
                size_bytes=len(section_content.encode("utf-8")),
            )
        )

    # If no sections were created (no headings), treat entire content as one section
    if not sections:
        sections.append(
            Section(
                level=0,
                title="Documentation",
                content=markdown,
                priority=100,
                size_bytes=len(markdown.encode("utf-8")),
            )
        )

    return sections


def score_section(title: str) -> int:
    """
    Score section based on title keywords.

    Args:
        title: Section title to score

    Returns:
        Priority score (higher is better)
    """
    if not title:
        return 30  # Default score

    title_lower = title.lower()

    # Check keywords by priority (highest first)
    for score, keywords in sorted(PRIORITY_KEYWORDS.items(), reverse=True):
        if any(kw in title_lower for kw in keywords):
            return score

    return 30  # Default score


def prioritize_sections(
    sections: List[Section], max_bytes: int = 20480
) -> str:
    """
    Select and combine sections by priority within size limit.

    Args:
        sections: List of sections to prioritize
        max_bytes: Maximum total size in bytes (default ~20KB)

    Returns:
        Combined Markdown content
    """
    if not sections:
        return ""

    # Always include first section (title + intro)
    result = [sections[0]]
    remaining_bytes = max_bytes - sections[0].size_bytes

    # If first section exceeds limit, truncate it
    if sections[0].size_bytes > max_bytes:
        return smart_truncate(sections[0].content, max_bytes)

    # Sort remaining sections by priority (highest first)
    sorted_sections = sorted(sections[1:], key=lambda s: s.priority, reverse=True)

    # Add sections greedily until we hit size limit
    for section in sorted_sections:
        if section.size_bytes <= remaining_bytes:
            result.append(section)
            remaining_bytes -= section.size_bytes

    # Reconstruct markdown in original order
    # Sort result sections by their original position
    result_dict = {id(s): s for s in result}
    ordered_result = [s for s in sections if id(s) in result_dict]

    return "\n\n".join(s.content for s in ordered_result)


def smart_truncate(text: str, max_bytes: int) -> str:
    """
    Truncate text to byte limit while preserving structure.

    Tries to truncate at paragraph or sentence boundaries.

    Args:
        text: Text to truncate
        max_bytes: Maximum size in bytes

    Returns:
        Truncated text
    """
    if not text:
        return ""

    # If already under limit, return as-is
    if len(text.encode("utf-8")) <= max_bytes:
        return text

    # Try to find a good breaking point
    # Priority: paragraph > sentence > word > character
    encoded = text.encode("utf-8")

    # Start with max_bytes and work backwards
    truncate_point = max_bytes

    # Decode with truncation, handling potential multi-byte character splits
    while truncate_point > 0:
        try:
            truncated = encoded[:truncate_point].decode("utf-8")
            break
        except UnicodeDecodeError:
            # Hit a multi-byte character boundary, try one byte earlier
            truncate_point -= 1
    else:
        return ""

    # Try to find paragraph break (double newline)
    last_para = truncated.rfind("\n\n")
    if last_para > max_bytes * 0.7:  # Only if we're keeping >70%
        result = truncated[:last_para].strip() + "\n\n..."
        if len(result.encode("utf-8")) <= max_bytes:
            return result

    # Try to find sentence break
    for punct in [".\n", "!\n", "?\n"]:
        last_sent = truncated.rfind(punct)
        if last_sent > max_bytes * 0.7:
            result = truncated[: last_sent + 1].strip() + "\n\n..."
            if len(result.encode("utf-8")) <= max_bytes:
                return result

    # Try to find word break
    last_space = truncated.rfind(" ")
    if last_space > 0:
        result = truncated[:last_space].strip() + "..."
        if len(result.encode("utf-8")) <= max_bytes:
            return result

    # Fallback: just truncate with strict ellipsis enforcement
    # We need to ensure we have room for "..." (3 bytes)
    if max_bytes <= 3:
        return "." * max_bytes

    # Recalculate truncation point allowing for ellipsis
    encoded = text.encode("utf-8")
    truncate_point = max_bytes - 3

    while truncate_point > 0:
        try:
            truncated = encoded[:truncate_point].decode("utf-8")
            break
        except UnicodeDecodeError:
            truncate_point -= 1
    else:
        return "." * max_bytes if max_bytes <= 3 else "..."

    return truncated.strip() + "..."


def convert_relative_urls(markdown: str, base_url: str) -> str:
    """
    Convert relative URLs in Markdown to absolute URLs.

    Args:
        markdown: Markdown content
        base_url: Base URL to prepend to relative links

    Returns:
        Markdown with absolute URLs
    """
    if not base_url:
        return markdown

    # Ensure base_url doesn't end with /
    base_url = base_url.rstrip("/")

    # Pattern for Markdown links: [text](url)
    def replace_link(match):
        text = match.group(1)
        url = match.group(2)

        # Only modify relative URLs (not starting with http:// or https://)
        if not url.startswith(("http://", "https://", "#", "mailto:")):
            # Handle URLs starting with /
            if url.startswith("/"):
                # Extract domain from base_url
                domain_match = re.match(r"(https?://[^/]+)", base_url)
                if domain_match:
                    url = domain_match.group(1) + url
                else:
                    url = base_url + url
            else:
                url = base_url + "/" + url

        return f"[{text}]({url})"

    # Replace links
    markdown = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", replace_link, markdown)

    # Pattern for Markdown images: ![alt](url)
    def replace_image(match):
        alt = match.group(1)
        url = match.group(2)

        if not url.startswith(("http://", "https://", "#")):
            if url.startswith("/"):
                domain_match = re.match(r"(https?://[^/]+)", base_url)
                if domain_match:
                    url = domain_match.group(1) + url
                else:
                    url = base_url + url
            else:
                url = base_url + "/" + url

        return f"![{alt}]({url})"

    # Replace images
    markdown = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", replace_image, markdown)

    return markdown
