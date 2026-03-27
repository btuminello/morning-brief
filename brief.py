import os
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import feedparser

OUTPUT_PATH = "output/brief.txt"

# Broad news searches — not limited to specific companies
FEEDS = {
    "AI": [
        "https://news.google.com/rss/search?q=artificial+intelligence",
        "https://news.google.com/rss/search?q=AI+agents",
        "https://news.google.com/rss/search?q=generative+AI",
        "https://news.google.com/rss/search?q=machine+learning",
        "https://news.google.com/rss/search?q=AI+regulation",
        "https://news.google.com/rss/search?q=AI+startup",
        "https://news.google.com/rss/search?q=AI+consumer+apps",
        "https://news.google.com/rss/search?q=AI+enterprise+software"
    ],
    "Markets": [
        "https://news.google.com/rss/search?q=stock+market",
        "https://news.google.com/rss/search?q=financial+markets",
        "https://news.google.com/rss/search?q=market+outlook",
        "https://news.google.com/rss/search?q=interest+rates",
        "https://news.google.com/rss/search?q=inflation+markets",
        "https://news.google.com/rss/search?q=tech+stocks",
        "https://news.google.com/rss/search?q=AI+stocks",
        "https://news.google.com/rss/search?q=venture+capital+AI"
    ],
    "Travel / Boop Relevance": [
        "https://news.google.com/rss/search?q=travel+technology",
        "https://news.google.com/rss/search?q=travel+startup",
        "https://news.google.com/rss/search?q=online+travel",
        "https://news.google.com/rss/search?q=travel+planning+app",
        "https://news.google.com/rss/search?q=digital+travel+booking",
        "https://news.google.com/rss/search?q=creator+travel",
        "https://news.google.com/rss/search?q=consumer+internet+travel",
        "https://news.google.com/rss/search?q=trip+planning+AI"
    ]
}

AI_KEYWORDS = [
    "ai", "artificial intelligence", "machine learning", "llm", "agent",
    "model", "generative ai", "chatbot", "reasoning", "chip", "data center",
    "training", "inference", "robotics", "automation"
]

MARKET_KEYWORDS = [
    "market", "stocks", "shares", "earnings", "investor", "valuation",
    "interest rates", "inflation", "fed", "nasdaq", "s&p", "trade",
    "revenue", "guidance", "capital spending"
]

TRAVEL_KEYWORDS = [
    "travel", "trip", "booking", "vacation", "airline", "hotel",
    "hospitality", "tourism", "itinerary", "travel app", "travel tech",
    "consumer internet", "creator", "discovery"
]


def normalize(text):
    return (text or "").strip()


def parse_datetime(value):
    if not value:
        return None
    try:
        dt = parsedate_to_datetime(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def fetch_feed_items(url):
    feed = feedparser.parse(url)
    items = []
    for entry in feed.entries[:8]:
        items.append({
            "title": normalize(entry.get("title")),
            "summary": normalize(entry.get("summary")),
            "link": normalize(entry.get("link")),
            "published": parse_datetime(entry.get("published") or entry.get("updated"))
        })
    return items


def dedupe(items):
    seen = set()
    out = []
    for item in items:
        title = item["title"].lower()
        if not title or title in seen:
            continue
        seen.add(title)
        out.append(item)
    return out


def score_item(item, section):
    text = f'{item["title"]} {item["summary"]}'.lower()
    score = 0

    if section == "AI":
        score += sum(2 for kw in AI_KEYWORDS if kw in text)
        score += sum(1 for kw in MARKET_KEYWORDS if kw in text)

    elif section == "Markets":
        score += sum(2 for kw in MARKET_KEYWORDS if kw in text)
        score += sum(1 for kw in AI_KEYWORDS if kw in text)

    elif section == "Travel / Boop Relevance":
        score += sum(2 for kw in TRAVEL_KEYWORDS if kw in text)
        score += sum(1 for kw in AI_KEYWORDS if kw in text)

    published = item.get("published")
    if published:
        hours_old = (datetime.now(timezone.utc) - published).total_seconds() / 3600
        if hours_old <= 12:
            score += 3
        elif hours_old <= 24:
            score += 2
        elif hours_old <= 48:
            score += 1

    return score


def why_it_matters(section, title):
    t = title.lower()

    if section == "AI":
        if any(word in t for word in ["regulation", "policy", "law"]):
            return "Could affect the pace of AI adoption and which companies benefit."
        if any(word in t for word in ["model", "agent", "launch", "release"]):
            return "Signals where the AI product race is moving next."
        return "Useful for understanding the direction of the broader AI space."

    if section == "Markets":
        if any(word in t for word in ["inflation", "fed", "rates"]):
            return "Macro shifts like this can move growth stocks and risk appetite."
        if any(word in t for word in ["earnings", "valuation", "stocks"]):
            return "Helpful for judging how the market is pricing growth and AI exposure."
        return "Relevant to overall market tone and investor sentiment."

    if section == "Travel / Boop Relevance":
        if any(word in t for word in ["booking", "trip", "travel", "hotel", "airline"]):
            return "Could show where travel demand and consumer behavior are heading."
        if any(word in t for word in ["creator", "discovery", "app"]):
            return "Relevant to how people discover experiences and convert interest into bookings."
        return "Potentially useful for spotting product and consumer trends in travel."

    return "Relevant to your overall brief."


def build_section(section_name, urls, limit=3):
    items = []
    for url in urls:
        items.extend(fetch_feed_items(url))

    items = dedupe(items)
    ranked = sorted(items, key=lambda x: score_item(x, section_name), reverse=True)
    ranked = [item for item in ranked if score_item(item, section_name) > 0][:limit]

    lines = [section_name]
    if not ranked:
        lines.append("- No strong headlines found.")
        return "\n".join(lines)

    for item in ranked:
        lines.append(f'- {item["title"]}')
        lines.append(f'  Why it matters: {why_it_matters(section_name, item["title"])}')

    return "\n".join(lines)


def main():
    today = datetime.now().strftime("%B %d, %Y")

    sections = []
    for section_name, urls in FEEDS.items():
        sections.append(build_section(section_name, urls))

    brief = f"""Morning Brief — {today}

{sections[0]}

{sections[1]}

{sections[2]}

Bottom Line
- Watch where AI, consumer behavior, and market sentiment overlap today.
"""

    os.makedirs("output", exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(brief)

    print("Wrote output/brief.txt")


if __name__ == "__main__":
    main()
