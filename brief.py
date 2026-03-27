import os
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import feedparser

OUTPUT_PATH = "output/brief.txt"

FEEDS = {
    "AI": [
        "https://news.google.com/rss/search?q=artificial+intelligence",
        "https://news.google.com/rss/search?q=AI+agents",
        "https://news.google.com/rss/search?q=generative+AI",
        "https://news.google.com/rss/search?q=AI+infrastructure",
        "https://news.google.com/rss/search?q=AI+enterprise+adoption",
        "https://news.google.com/rss/search?q=AI+regulation",
        "https://news.google.com/rss/search?q=AI+funding",
        "https://news.google.com/rss/search?q=consumer+AI"
    ],
    "Markets": [
        "https://news.google.com/rss/search?q=stock+market",
        "https://news.google.com/rss/search?q=financial+markets",
        "https://news.google.com/rss/search?q=tech+stocks",
        "https://news.google.com/rss/search?q=growth+stocks",
        "https://news.google.com/rss/search?q=inflation+markets",
        "https://news.google.com/rss/search?q=interest+rates",
        "https://news.google.com/rss/search?q=AI+stocks",
        "https://news.google.com/rss/search?q=semiconductor+demand"
    ],
    "Travel / Boop Relevance": [
        "https://news.google.com/rss/search?q=travel+technology",
        "https://news.google.com/rss/search?q=online+travel",
        "https://news.google.com/rss/search?q=digital+booking+travel",
        "https://news.google.com/rss/search?q=travel+planning+app",
        "https://news.google.com/rss/search?q=AI+travel+planning",
        "https://news.google.com/rss/search?q=travel+consumer+behavior",
        "https://news.google.com/rss/search?q=creator+economy+travel",
        "https://news.google.com/rss/search?q=travel+startup"
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
    text = f'{item["title"]} {item.get("summary", "")}'.lower()
    title = item["title"].lower()
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

    strong_words = [
        "launch", "release", "funding", "raises", "acquisition", "earnings",
        "inflation", "fed", "regulation", "policy", "booking", "startup",
        "agent", "chips", "data center", "demand", "consumer"
    ]
    score += sum(2 for word in strong_words if word in title)

    weak_words = ["opinion", "editorial", "podcast", "review"]
    score -= sum(2 for word in weak_words if word in title)

    published = item.get("published")
    if published:
        hours_old = (datetime.now(timezone.utc) - published).total_seconds() / 3600
        if hours_old <= 12:
            score += 4
        elif hours_old <= 24:
            score += 3
        elif hours_old <= 48:
            score += 2
        elif hours_old <= 72:
            score += 1

    return score


def why_it_matters(section, title):
    t = title.lower()

    if section == "AI":
        if "google" in t:
            return "Signals big-tech AI product expansion and stronger competition across the space."
        if "openai" in t or "anthropic" in t:
            return "Useful for tracking where frontier model competition is heading."
        if "agent" in t or "agents" in t:
            return "Shows the shift from chatbots toward AI systems that can complete workflows."
        if "regulation" in t or "policy" in t:
            return "Could affect the speed of AI adoption and which companies benefit."
        if "chip" in t or "data center" in t or "inference" in t:
            return "Relevant to the infrastructure side of the AI trade."
        return "Useful for understanding where the broader AI space is moving."

    if section == "Markets":
        if "fed" in t or "inflation" in t or "rates" in t:
            return "Macro changes here can move tech valuations and overall risk appetite."
        if "nasdaq" in t or "s&p" in t or "dow" in t:
            return "Helpful for gauging overall market tone heading into the day."
        if "earnings" in t or "valuation" in t:
            return "Relevant for how investors are pricing growth and AI exposure."
        return "Useful for understanding how markets are reacting to current events."

    if section == "Travel / Boop Relevance":
        if "booking" in t or "trip" in t or "itinerary" in t:
            return "Shows how people are moving from inspiration to planning and booking."
        if "ai" in t:
            return "Reinforces the trend toward AI-powered travel planning and personalization."
        if "startup" in t or "travel tech" in t:
            return "Useful for spotting where product innovation is happening in travel."
        if "creator" in t or "discovery" in t:
            return "Relevant to how travel interest turns into action and conversion."
        return "Helpful for understanding travel consumer behavior and product trends."

    return "Relevant to today’s broader themes."


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
        return "\n".join(lines), []

    for item in ranked:
        lines.append(f'- {item["title"]}')
        lines.append(f'  Why it matters: {why_it_matters(section_name, item["title"])}')
        lines.append(f'  Link: {item["link"]}')
        lines.append("")

    return "\n".join(lines), ranked


def build_must_read_section(all_section_items, limit=5):
    combined = []

    for section_name, items in all_section_items.items():
        for item in items:
            combined.append({
                "section": section_name,
                "title": item["title"],
                "link": item["link"],
                "score": score_item(item, section_name)
            })

    combined = sorted(combined, key=lambda x: x["score"], reverse=True)[:limit]

    lines = ["Must Read Today"]

    for item in combined:
        lines.append(f'- [{item["section"]}] {item["title"]}')
        lines.append(f'  Link: {item["link"]}')
        lines.append("")

    return "\n".join(lines)


def main():
    today = datetime.now().strftime("%B %d, %Y")

    ai_text, ai_items = build_section("AI", FEEDS["AI"])
    markets_text, markets_items = build_section("Markets", FEEDS["Markets"])
    travel_text, travel_items = build_section("Travel / Boop Relevance", FEEDS["Travel / Boop Relevance"])

    all_section_items = {
        "AI": ai_items,
        "Markets": markets_items,
        "Travel / Boop Relevance": travel_items
    }

    must_read = build_must_read_section(all_section_items)

    brief = f"""Morning Brief — {today}

{must_read}

{ai_text}

{markets_text}

{travel_text}

Bottom Line
- Watch where AI, consumer behavior, and market sentiment overlap today.
"""

    os.makedirs("output", exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(brief)

    print("Wrote output/brief.txt")


if __name__ == "__main__":
    main()
