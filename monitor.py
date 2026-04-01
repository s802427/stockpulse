import feedparser
import requests
import hashlib
import json
import os
from datetime import datetime

DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK_URL")

RSS_FEEDS = [
    # Yahoo Finance
    "https://feeds.finance.yahoo.com/rss/2.0/headline?s=^GSPC&region=US&lang=en-US",
    "https://feeds.finance.yahoo.com/rss/2.0/headline?s=^DJI&region=US&lang=en-US",
    "https://finance.yahoo.com/news/rssindex",
    # MarketWatch
    "https://feeds.marketwatch.com/marketwatch/topstories/",
    "https://feeds.marketwatch.com/marketwatch/marketpulse/",
    # CNBC
    "https://www.cnbc.com/id/100003114/device/rss/rss.html",
    "https://www.cnbc.com/id/10001147/device/rss/rss.html",
    # Reuters
    "https://feeds.reuters.com/reuters/businessNews",
    "https://feeds.reuters.com/reuters/companyNews",
    # Seeking Alpha
    "https://seekingalpha.com/market_currents.xml",
    # SEC EDGAR 重大公告
    "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=8-K&dateb=&owner=include&count=10&search_text=&output=atom",
]

]

KEYWORDS = [
    "earnings", "revenue", "profit", "loss", "guidance",
    "Fed", "interest rate", "inflation", "GDP",
    "merger", "acquisition", "buyback", "dividend",
    "layoff", "bankruptcy", "IPO", "recall",
]

def hash_title(title):
    return hashlib.md5(title.encode()).hexdigest()

def is_relevant(title):
    title_lower = title.lower()
    return any(kw.lower() in title_lower for kw in KEYWORDS)

def translate(text):
    try:
        url = "https://translate.googleapis.com/translate_a/single"
        params = {
            "client": "gtx",
            "sl": "en",
            "tl": "zh-TW",
            "dt": "t",
            "q": text
        }
        r = requests.get(url, params=params, timeout=5)
        return r.json()[0][0][0]
    except:
        return ""

def send_discord(title, link, source):
    zh = translate(title)
    message = (
        f"📰 **{title}**\n"
        f"🇹🇼 {zh}\n"
        f"🔗 {link}\n"
        f"📡 `{source}`"
    )
    payload = {"content": message}
    requests.post(DISCORD_WEBHOOK, json=payload)

def main():
    seen = set()
    new_count = 0

    for feed_url in RSS_FEEDS:
        feed = feedparser.parse(feed_url)
        source = feed.feed.get("title", feed_url)

        for entry in feed.entries[:5]:
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

    print(f"[{datetime.now()}] 推送了 {new_count} 條新聞")

if __name__ == "__main__":
    main()
