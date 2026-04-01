import feedparser
import requests
import hashlib
import json
import os
from datetime import datetime

DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK_URL")

RSS_FEEDS = [
    "https://feeds.finance.yahoo.com/rss/2.0/headline?s=^GSPC&region=US&lang=en-US",
    "https://feeds.finance.yahoo.com/rss/2.0/headline?s=^DJI&region=US&lang=en-US",
    "https://finance.yahoo.com/news/rssindex",
    "https://feeds.marketwatch.com/marketwatch/topstories/",
]

KEYWORDS = [
    "earnings", "revenue", "profit", "loss", "guidance",
    "Fed", "interest rate", "inflation", "GDP",
    "merger", "acquisition", "buyback", "dividend",
    "layoff", "bankruptcy", "IPO", "recall",
]

SEEN_FILE = "seen.json"

def load_seen():
    try:
        with open(SEEN_FILE, "r") as f:
            return set(json.load(f))
    except:
        return set()

def save_seen(seen):
    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen)[-500:], f)

def hash_title(title):
    return hashlib.md5(title.encode()).hexdigest()

def is_relevant(title):
    title_lower = title.lower()
    return any(kw.lower() in title_lower for kw in KEYWORDS)

def send_discord(title, link, source):
    message = f"📰 **{title}**\n🔗 {link}\n📡 `{source}`"
    payload = {"content": message}
    requests.post(DISCORD_WEBHOOK, json=payload)

def main():
    seen = load_seen()
    new_count = 0

    for feed_url in RSS_FEEDS:
        feed = feedparser.parse(feed_url)
        source = feed.feed.get("title", feed_url)

        for entry in feed.entries:
            title = entry.get("title", "")
            link = entry.get("link", "")
            h = hash_title(title)

            if h in seen:
                continue
            if not is_relevant(title):
                continue

            seen.add(h)
            send_discord(title, link, source)
            new_count += 1

    save_seen(seen)
    print(f"[{datetime.now()}] 推送了 {new_count} 條新聞")

if __name__ == "__main__":
    main()
