"""Web scraping and content extraction utilities for SecondSelf."""

from __future__ import annotations

import re
from typing import Tuple
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
import trafilatura


PAYWALL_MARKERS = [
    "sign in to continue reading",
    "subscribe to read",
    "member-only story",
    "you have reached your limit of free articles",
    "create an account to continue",
]


def validate_url(url: str) -> str:
    """Ensure URL has a valid scheme and format."""
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    parsed = urlparse(url)
    if not parsed.netloc:
        raise ValueError(f"Invalid URL: '{url}'. Missing domain.")
    return url


def check_content_type(url: str, timeout: int = 10) -> str:
    """Perform a HEAD request to verify MIME type before full fetch."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36 SecondSelf/1.0"
        )
    }
    try:
        response = requests.head(url, headers=headers, timeout=timeout, allow_redirects=True)
        content_type = response.headers.get("Content-Type", "").lower()
        return content_type
    except Exception:
        # If HEAD fails (e.g. server blocks HEAD), allow GET attempt
        return "text/html"


def scrape_url(url: str, timeout: int = 15) -> Tuple[str, str, dict]:
    """
    Extract clean article text, title, and metadata from a web URL.
    Returns (title, content, metadata_dict).
    """
    url = validate_url(url)
    content_type = check_content_type(url, timeout=timeout)

    # Reject unsupported binary MIME types
    binary_types = ["application/zip", "video/", "audio/", "application/octet-stream", "image/"]
    if any(b in content_type for b in binary_types):
        raise ValueError(f"URL points to a non-document binary resource ({content_type}): {url}")

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36 SecondSelf/1.0"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }

    metadata = {
        "url": url,
        "content_type": content_type,
        "extraction_method": "trafilatura",
        "warnings": [],
    }

    html = None
    try:
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        html = response.text
    except requests.exceptions.HTTPError as e:
        status = e.response.status_code if e.response is not None else "Unknown"
        raise RuntimeError(f"HTTP {status} error while accessing {url}") from e
    except requests.exceptions.Timeout as e:
        raise RuntimeError(f"Request timed out after {timeout} seconds for {url}") from e
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Failed to connect to {url}: {e}") from e

    # Extract title using BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
    elif og_title := soup.find("meta", property="og:title"):
        title = og_title.get("content", "").strip()

    if not title:
        parsed = urlparse(url)
        title = parsed.path.strip("/").split("/")[-1] or parsed.netloc

    # Extract body content with Trafilatura
    extracted_text = trafilatura.extract(
        html,
        url=url,
        include_comments=False,
        include_tables=True,
        output_format="txt",
        no_fallback=False,
    )

    # Fallback to BeautifulSoup if Trafilatura extracted nothing or minimal text
    if not extracted_text or len(extracted_text.strip()) < 80:
        metadata["extraction_method"] = "beautifulsoup_fallback"
        # Remove script and style elements
        for script in soup(["script", "style", "noscript", "nav", "footer", "header"]):
            script.extract()
        text_elements = [p.get_text().strip() for p in soup.find_all(["p", "h1", "h2", "h3", "li"])]
        extracted_text = "\n\n".join([t for t in text_elements if len(t) > 20])

    content = extracted_text.strip() if extracted_text else ""

    # Check for Single-Page Application (SPA) / empty rendering
    if len(content) < 100:
        meta_desc = ""
        if desc_tag := (soup.find("meta", attrs={"name": "description"}) or soup.find("meta", property="og:description")):
            meta_desc = desc_tag.get("content", "").strip()

        if meta_desc:
            content = f"{title}\n\n{meta_desc}"
            metadata["warnings"].append("Dynamic JavaScript site detected. Captured page description.")
        else:
            content = f"Page Title: {title}\nURL: {url}\n\n(No readable textual content could be extracted from this page.)"
            metadata["warnings"].append("Minimal content extracted. Target may require JavaScript execution.")

    # Check for potential paywall
    content_lower = content.lower()
    if any(marker in content_lower for marker in PAYWALL_MARKERS):
        metadata["warnings"].append("Potential paywall or login gate detected on this page.")

    return title, content, metadata
