import os
import re
import html
import smtplib
from datetime import datetime, timezone
from email.mime.text import MIMEText
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo

import feedparser
import requests

OUTPUT_PATH = "output/brief.txt"
LOCAL_TZ = os.getenv("BRIEF_TZ", "America/New_York")

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

BREAKING_WORDS = [
    "breaking", "just in", "urgent", "surges", "slumps", "plunges",
    "soars", "rate hike", "inflation", "fed", "launch", "release",
    "funding", "raises", "acquisition", "earnings", "guidance"
]

WEAK_SOURCES = [
    "vocal.media"
]


def now_local() -> datetime:
    return datetime.now(ZoneInfo(LOCAL_TZ))


def normalize(text: str) -> str:
    return (text or "").strip()


def strip_html(text: str) -> str:
    text = html.unescape(text or "")
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def remove_source_from_title(title: str) -> str:
    if " - " in title:
        return title.rsplit(" - ", 1)[0].strip()
    return title.strip()


def first_sentence(text: str, max_len: int = 180) -> str:
    text = strip_html(text)
    if not text:
        return ""

    parts = re.split(r"(?<=[.!?])\s+", text)
    sentence = parts[0].strip()

    if len(sentence) > max_len:
        sentence = sentence[:max_len].rsplit(" ", 1)[0].strip() + "..."

    return sentence


def parse_datetime(value: str):
    if not value:
        return None
    try:
        dt = parsedate_to_datetime(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def clean_link(link: str) -> str:
    return (link or "").strip()


def fetch_feed_items(url: str):
    feed = feedparser.parse(url)
    items = []

    for entry in feed.entries[:10]:
        link = clean_link(entry.get("link"))
        title = normalize(entry.get("title"))
        summary = normalize(entry.get("summary"))
        published = parse_datetime(entry.get("published") or entry.get("updated"))

        if not title or not link:
            continue

        items.append({
            "title": title,
            "summary": summary,
            "link": link,
            "published": published,
        })

    return items


def dedupe(items):
    seen = set()
    out = []

    for item in items:
        key = (item["title"].lower(), item["link"])
        if key in seen:
            continue
        seen.add(key)
        out.append(item)

    return out


def score_item(item, section):
    text = f'{item["title"]} {item.get("summary", "")}'.lower()
    title = item["title"].lower()
    link = item["link"].lower()
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

    if any(domain in link for domain in WEAK_SOURCES):
        score -= 4

    published = item.get("published")
    if published:
        age_hours = (datetime.now(timezone.utc) - published).total_seconds() / 3600
        if age_hours <= 6:
            score += 6
        elif age_hours <= 12:
            score += 4
        elif age_hours <= 24:
            score += 3
        elif age_hours <= 48:
            score += 2
        elif age_hours <= 72:
            score += 1

    return score


def summarize_item(item, section):
    title = remove_source_from_title(item["title"])
    raw_summary = strip_html(item.get("summary", ""))

    if raw_summary:
        cleaned = raw_summary.replace(title, "").strip(" -:|")
        sentence = first_sentence(cleaned)
        if sentence and sentence.lower() != title.lower():
            return sentence

    t = title.lower()

    if section == "AI":
        if "agent" in t:
            return "The article covers how AI agents are being used to automate more complex workflows."
        if "funding" in t or "raises" in t or "financing" in t:
            return "The article explains where AI capital is flowing and what part of the stack investors are backing."
        if "data center" in t or "chip" in t or "infrastructure" in t:
            return "The article focuses on the infrastructure needed to support growing AI demand."
        return title

    if section == "Markets":
        if "fed" in t or "inflation" in t or "rates" in t:
            return "The article explains how inflation and Fed expectations are shaping markets today."
        if "stocks" in t or "futures" in t or "nasdaq" in t or "s&p" in t:
            return "The article gives a snapshot of how investors are positioning heading into the trading day."
        return title

    if section == "Travel / Boop Relevance":
        if "booking" in t or "travel planning" in t or "hotel" in t:
            return "The article looks at how travel discovery is turning into planning and booking."
        if "ai" in t:
            return "The article shows how AI is changing the trip planning and booking experience."
        return title

    return title


def collect_ranked_items():
    sections = {}

    for section_name, urls in FEEDS.items():
        items = []
        for url in urls:
            items.extend(fetch_feed_items(url))

        items = dedupe(items)
        ranked = sorted(items, key=lambda x: score_item(x, section_name), reverse=True)
        ranked = [item for item in ranked if score_item(item, section_name) > 0]
        sections[section_name] = ranked

    return sections


def build_breaking_news_section(all_section_items, used_links, limit=3):
    candidates = []
    now_utc = datetime.now(timezone.utc)

    for section_name, items in all_section_items.items():
        for item in items:
            if item["link"] in used_links:
                continue

            published = item.get("published")
            is_recent = False
            if published:
                age_hours = (now_utc - published).total_seconds() / 3600
                is_recent = age_hours <= 12

            text = f'{item["title"]} {item.get("summary", "")}'.lower()
            has_breaking_signal = any(word in text for word in BREAKING_WORDS)

            if is_recent or has_breaking_signal:
                candidates.append({
                    "section": section_name,
                    "title": item["title"],
                    "link": item["link"],
                    "score": score_item(item, section_name) + (5 if has_breaking_signal else 0)
                })

    candidates = sorted(candidates, key=lambda x: x["score"], reverse=True)

    lines = ["Breaking News"]
    added = 0

    for item in candidates:
        if item["link"] in used_links:
            continue
        used_links.add(item["link"])
        lines.append(f'- [{item["section"]}] {item["title"]}')
        lines.append(f'  Link: {item["link"]}')
        lines.append("")
        added += 1
        if added >= limit:
            break

    if added == 0:
        lines.append("- No major breaking items this morning.")
        lines.append("")

    return "\n".join(lines)


def build_must_read_section(all_section_items, used_links, limit=5):
    combined = []

    for section_name, items in all_section_items.items():
        for item in items:
            if item["link"] in used_links:
                continue
            combined.append({
                "section": section_name,
                "title": item["title"],
                "link": item["link"],
                "score": score_item(item, section_name)
            })

    combined = sorted(combined, key=lambda x: x["score"], reverse=True)

    lines = ["Must Read Today"]
    added = 0

    for item in combined:
        if item["link"] in used_links:
            continue
        used_links.add(item["link"])
        lines.append(f'- [{item["section"]}] {item["title"]}')
        lines.append(f'  Link: {item["link"]}')
        lines.append("")
        added += 1
        if added >= limit:
            break

    if added == 0:
        lines.append("- No must-read items found.")
        lines.append("")

    return "\n".join(lines)


def build_section(section_name, ranked_items, used_links, limit=3):
    lines = [section_name]
    added = 0

    for item in ranked_items:
        if item["link"] in used_links:
            continue

        used_links.add(item["link"])
        lines.append(f'- {item["title"]}')
        lines.append(f'  Summary: {summarize_item(item, section_name)}')
        lines.append(f'  Link: {item["link"]}')
        lines.append("")
        added += 1

        if added >= limit:
            break

    if added == 0:
        lines.append("- No additional unique headlines.")
        lines.append("")

    return "\n".join(lines)


def get_espn_scoreboard(sport_path: str, date_yyyymmdd: str):
    url = f"https://site.api.espn.com/apis/site/v2/sports/{sport_path}/scoreboard"
    try:
        r = requests.get(url, params={"dates": date_yyyymmdd}, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception:
        return {}


def extract_team_game_note(scoreboard_json, target_team: str):
    events = scoreboard_json.get("events", [])
    target = target_team.lower()

    for event in events:
        competitions = event.get("competitions", [])
        if not competitions:
            continue

        comp = competitions[0]
        competitors = comp.get("competitors", [])

        team_names = []
        for c in competitors:
            team = c.get("team", {})
            display = team.get("displayName", "")
            short = team.get("shortDisplayName", "")
            abbr = team.get("abbreviation", "")
            team_names.extend([display, short, abbr])

        if not any(target in (name or "").lower() for name in team_names):
            continue

        names = []
        for c in competitors:
            team = c.get("team", {})
            names.append(team.get("displayName", "Unknown"))

        status = event.get("status", {}).get("type", {}).get("shortDetail", "")
        matchup = " vs ".join(names)

        return f"- {matchup} — {status}"

    return None


def build_sports_note():
    today_local = now_local()
    date_yyyymmdd = today_local.strftime("%Y%m%d")
    notes = []

    mariners = get_espn_scoreboard("baseball/mlb", date_yyyymmdd)
    mariners_note = extract_team_game_note(mariners, "Seattle Mariners")
    if mariners_note:
        notes.append(mariners_note)

    seahawks = get_espn_scoreboard("football/nfl", date_yyyymmdd)
    seahawks_note = extract_team_game_note(seahawks, "Seattle Seahawks")
    if seahawks_note:
        notes.append(seahawks_note)

    if not notes:
        return ""

    return "Seattle Sports Today\n" + "\n".join(notes) + "\n\n"


def build_boston_weather_section():
    try:
        geo = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": "Boston, Massachusetts", "count": 1},
            timeout=10,
        )
        geo.raise_for_status()
        geo_data = geo.json()

        results = geo_data.get("results", [])
        if not results:
            return ""

        lat = results[0]["latitude"]
        lon = results[0]["longitude"]

        forecast = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,apparent_temperature,wind_speed_10m",
                "hourly": "temperature_2m,precipitation_probability",
                "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max",
                "temperature_unit": "fahrenheit",
                "wind_speed_unit": "mph",
                "timezone": "America/New_York",
            },
            timeout=10,
        )
        forecast.raise_for_status()
        data = forecast.json()

        current = data.get("current", {})
        daily = data.get("daily", {})
        hourly = data.get("hourly", {})

        current_temp = round(current.get("temperature_2m", 0))
        feels_like = round(current.get("apparent_temperature", 0))
        wind = round(current.get("wind_speed_10m", 0))

        max_temp = round(daily.get("temperature_2m_max", [0])[0])
        min_temp = round(daily.get("temperature_2m_min", [0])[0])
        precip_max = round(daily.get("precipitation_probability_max", [0])[0])

        hours = hourly.get("time", [])
        temps = hourly.get("temperature_2m", [])
        today_date = now_local().strftime("%Y-%m-%d")

        morning_temp = None
        afternoon_temp = None
        evening_temp = None

        for t, temp in zip(hours, temps):
            if t == f"{today_date}T08:00":
                morning_temp = round(temp)
            elif t == f"{today_date}T14:00":
                afternoon_temp = round(temp)
            elif t == f"{today_date}T20:00":
                evening_temp = round(temp)

        wear = []
        if max_temp < 45:
            wear.append("coat")
        elif max_temp < 60:
            wear.append("light jacket")
        else:
            wear.append("light layer")

        if morning_temp is not None and afternoon_temp is not None and (afternoon_temp - morning_temp) >= 15:
            wear.append("layers")

        if precip_max >= 40:
            wear.append("umbrella")

        if wind >= 15:
            wear.append("wind-resistant outer layer")

        wear_text = ", ".join(wear)

        lines = [
            "Boston Weather",
            f"- {min_temp}° to {max_temp}° today. Right now it's {current_temp}° and feels like {feels_like}°.",
            f"- Around 8 AM: {morning_temp if morning_temp is not None else '?'}° | 2 PM: {afternoon_temp if afternoon_temp is not None else '?'}° | 8 PM: {evening_temp if evening_temp is not None else '?'}°.",
            f"- Wear: {wear_text}.",
            ""
        ]

        return "\n".join(lines)

    except Exception as e:
        print(f"Weather section failed: {e}")
        return ""


def send_email(subject: str, body: str):
    sender = os.getenv("BRIEF_EMAIL_FROM")
    recipient = os.getenv("BRIEF_EMAIL_TO")
    app_password = os.getenv("BRIEF_EMAIL_APP_PASSWORD")

    if not sender or not recipient or not app_password:
        print("Email secrets not set; skipping email send.")
        return

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = recipient

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender, app_password)
        server.send_message(msg)

    print(f"Sent email to {recipient}")


def main():
    today_local = now_local()
    today_label = today_local.strftime("%B %d, %Y")

    ranked_sections = collect_ranked_items()
    used_links = set()

    sports_note = build_sports_note()
    weather_note = build_boston_weather_section()
    breaking_news = build_breaking_news_section(ranked_sections, used_links, limit=3)
    must_read = build_must_read_section(ranked_sections, used_links, limit=5)

    ai_text = build_section("AI", ranked_sections["AI"], used_links, limit=3)
    markets_text = build_section("Markets", ranked_sections["Markets"], used_links, limit=3)
    travel_text = build_section(
        "Travel / Boop Relevance",
        ranked_sections["Travel / Boop Relevance"],
        used_links,
        limit=3
    )

    brief = f"""Morning Brief — {today_label}

{sports_note}{weather_note}{breaking_news}

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

    send_email(f"Morning Brief — {today_label}", brief)
    print("Wrote output/brief.txt")


if __name__ == "__main__":
    main()
