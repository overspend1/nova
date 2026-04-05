from __future__ import annotations

import re
from html import unescape
from urllib.parse import quote_plus

import requests


def duckduckgo_search(query: str, limit: int = 5) -> dict[str, object]:
    if not query.strip():
        return {"query": query, "results": []}

    url = f"https://duckduckgo.com/html/?q={quote_plus(query)}"
    response = requests.get(
        url,
        timeout=20,
        headers={"User-Agent": "Mozilla/5.0 (Nova Assistant)"},
    )
    response.raise_for_status()
    html = response.text

    pattern = re.compile(
        r'<a[^>]*class="result__a"[^>]*href="(?P<href>[^"]+)"[^>]*>(?P<title>.*?)</a>',
        flags=re.IGNORECASE | re.DOTALL,
    )

    results: list[dict[str, str]] = []
    for match in pattern.finditer(html):
        href = unescape(_strip_tags(match.group("href")))
        title = unescape(_strip_tags(match.group("title")))
        if not href or not title:
            continue
        results.append({"title": title, "url": href})
        if len(results) >= limit:
            break

    return {"query": query, "results": results}


def _strip_tags(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text).strip()
