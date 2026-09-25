#!/usr/bin/env python3
"""
news_to_post.py
================
Fetches the latest world news headlines from RSS feeds and turns each
story into a ready-to-publish social media post.

No API key required for the basic version (template-based posts).
If you set the ANTHROPIC_API_KEY environment variable, the script will
use Claude to write sharper, more natural posts instead of the template.

Usage:
    python news_to_post.py                     # 5 latest world news posts
    python news_to_post.py --count 3            # only 3 posts
    python news_to_post.py --style linkedin      # tone/style of post
    python news_to_post.py --source bbc          # single source only
    python news_to_post.py --ai                  # force Claude rewriting (needs API key)

Sources used by default: BBC World, Reuters World, Al Jazeera.
"""

import argparse
import os
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime
from email.utils import parsedate_to_datetime
from html import unescape

# ---------------------------------------------------------------------------
# RSS sources (all public, no key needed)
# ---------------------------------------------------------------------------
RSS_FEEDS = {
    "bbc": "http://feeds.bbci.co.uk/news/world/rss.xml",
    "reuters": "https://www.reutersagency.com/feed/?best-topics=world&post_type=best",
    "aljazeera": "https://www.aljazeera.com/xml/rss/all.xml",
}

USER_AGENT = "Mozilla/5.0 (compatible; NewsToPostBot/1.0)"


@dataclass
class NewsItem:
    title: str
    link: str
    summary: str
    source: str
    published: datetime | None


def clean_text(text: str) -> str:
    """Strip HTML tags and unescape entities from a feed field."""
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", "", text)
    return unescape(text).strip()


def fetch_rss(url: str, source_name: str, timeout: int = 10) -> list[NewsItem]:
    """Download and parse an RSS feed into a list of NewsItem."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    items = []
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
        root = ET.fromstring(raw)
        for entry in root.findall(".//item"):
            title = clean_text(entry.findtext("title", default=""))
            link = clean_text(entry.findtext("link", default=""))
            desc = clean_text(entry.findtext("description", default=""))
            pub_raw = entry.findtext("pubDate", default="")
            try:
                pub_date = parsedate_to_datetime(pub_raw) if pub_raw else None
            except (TypeError, ValueError):
                pub_date = None
            if title:
                items.append(NewsItem(title, link, desc, source_name, pub_date))
    except Exception as exc:  # noqa: BLE001 - report and continue with other feeds
        print(f"[warn] could not fetch {source_name} ({url}): {exc}", file=sys.stderr)
    return items


def gather_news(sources: list[str]) -> list[NewsItem]:
    """Fetch and merge news from the requested sources, newest first."""
    all_items: list[NewsItem] = []
    for name in sources:
        url = RSS_FEEDS.get(name)
        if not url:
            print(f"[warn] unknown source '{name}', skipping", file=sys.stderr)
            continue
        all_items.extend(fetch_rss(url, name))

    # Sort newest first; items with no date go last
    all_items.sort(key=lambda i: i.published or datetime.min.replace(tzinfo=None) if i.published is None
                    else i.published, reverse=True)
    return all_items


# ---------------------------------------------------------------------------
# Post generation
# ---------------------------------------------------------------------------

STYLE_TEMPLATES = {
    "twitter": "{hook}\n\n{summary}\n\n🔗 {link}\n{hashtags}",
    "linkedin": "{hook}\n\n{summary}\n\nWhat's your take on this?\n\n🔗 Read more: {link}\n\n{hashtags}",
    "generic": "{hook}\n\n{summary}\n\nSource: {source}\n{link}",
}


def hashtags_from_title(title: str, max_tags: int = 3) -> str:
    words = re.findall(r"[A-Za-z]{4,}", title)
    stop = {"says", "with", "from", "have", "this", "that", "will", "after", "over"}
    tags = []
    for w in words:
        wl = w.lower()
        if wl in stop or wl in [t.lower().strip("#") for t in tags]:
            continue
        tags.append("#" + w[0].upper() + w[1:])
        if len(tags) == max_tags:
            break
    return " ".join(tags)


def template_post(item: NewsItem, style: str) -> str:
    hook = item.title.strip()
    summary = item.summary[:220].rsplit(" ", 1)[0] + "…" if len(item.summary) > 220 else item.summary
    if not summary:
        summary = "Full story at the link below."
    tmpl = STYLE_TEMPLATES.get(style, STYLE_TEMPLATES["generic"])
    return tmpl.format(
        hook=hook,
        summary=summary,
        link=item.link,
        source=item.source.upper(),
        hashtags=hashtags_from_title(item.title),
    )


def ai_post(item: NewsItem, style: str) -> str:
    """Use the Claude API to write a punchier post. Requires ANTHROPIC_API_KEY."""
    import json

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("[warn] ANTHROPIC_API_KEY not set, falling back to template post", file=sys.stderr)
        return template_post(item, style)

    prompt = (
        f"Write a {style} post (no more than 80 words) summarizing this news story. "
        f"Be factual, engaging, and neutral in tone. Do not invent details not in the source.\n\n"
        f"Headline: {item.title}\n"
        f"Summary: {item.summary}\n"
        f"Source: {item.source}\n"
        f"Link: {item.link}\n\n"
        f"End the post with the link and 2-3 relevant hashtags."
    )

    body = json.dumps({
        "model": "claude-sonnet-4-6",
        "max_tokens": 300,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
        text_blocks = [b["text"] for b in data.get("content", []) if b.get("type") == "text"]
        return "\n".join(text_blocks).strip() or template_post(item, style)
    except Exception as exc:  # noqa: BLE001
        print(f"[warn] Claude API call failed ({exc}), falling back to template", file=sys.stderr)
        return template_post(item, style)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Gather latest world news and draft social posts.")
    parser.add_argument("--count", type=int, default=5, help="number of posts to generate (default 5)")
    parser.add_argument("--style", choices=["twitter", "linkedin", "generic"], default="generic",
                         help="post style/tone (default generic)")
    parser.add_argument("--source", choices=list(RSS_FEEDS.keys()), action="append",
                         help="limit to a specific source; can be passed multiple times")
    parser.add_argument("--ai", action="store_true", help="use Claude API to write the posts")
    args = parser.parse_args()

    sources = args.source or list(RSS_FEEDS.keys())
    print(f"Fetching latest world news from: {', '.join(sources)}...\n", file=sys.stderr)

    news = gather_news(sources)
    if not news:
        print("No news items retrieved. Check your network connection or feed URLs.", file=sys.stderr)
        sys.exit(1)

    seen_titles = set()
    picked = []
    for item in news:
        if item.title in seen_titles:
            continue
        seen_titles.add(item.title)
        picked.append(item)
        if len(picked) == args.count:
            break

    for i, item in enumerate(picked, 1):
        post = ai_post(item, args.style) if args.ai else template_post(item, args.style)
        print(f"===== POST {i} ({item.source}) =====")
        print(post)
        print()


if __name__ == "__main__":
    main()
