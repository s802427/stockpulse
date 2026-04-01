import feedparser
import requests
import hashlib
import os
from datetime import datetime

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = "@stockpulse_news2"

RSS_FEEDS = [
    "https://feeds.finance.yahoo.com/rss/2.0/headline?s=^GSPC&region=US&lang=en-US",
    "https://feeds.finance.yahoo.com/rss/2.0/headline?s=^DJI&region=US&lang=en-US",
    "https://finance.yahoo.com/news/rssindex",
    "https://feeds.marketwatch.com/marketwatch/topstories/",
    "https://feeds.marketwatch.com/marketwatch/marketpulse/",
    "https://www.cnbc.com/id/100003114/device/rss/rss.html",
    "https://feeds.reuters.com/reuters/businessNews",
    "https://feeds.reuters.com/reuters/companyNews",
]

# 高優先級：一定推
HIGH = [
    "fed rate", "rate hike", "rate cut", "earnings beat", "earnings miss",
    "bankruptcy", "merger", "acquisition", "IPO", "layoff", "recalls",
    "inflation", "GDP", "job report", "payroll", "crash", "surge",
]

# 低優先級：有其他條件才推
LOW = [
    "earnings", "revenue", "profit", "loss", "dividend",
    "upgrade", "downgrade", "forecast", "outlook", "tariff",
]

def hash_title(title):
    return hashlib.md5(title.encode()).hexdigest()

def is_important(title):
    t = title.lower()
    for kw in HIGH:
        if kw in t:
            return True
    matches = sum(1 for kw in LOW if kw in t)
    return matches >= 2

def translate(text):
    try:
        url = "https://translate.googleapis.com/translate_a/single"
        params = {"client": "gtx", "sl": "en", "tl": "zh-TW", "dt": "t", "q": text}
        r = requests.get(url, params=params, timeout=5)
        return r.json()[0][0][0]
    except:
        return ""

def send_telegram(title, link, source):
    zh = translate(title)
    message = (
        f"📰 <b>{title}</b>\n"
        f"🇹🇼 {zh}\n\n"
        f"🔗 <a href='{link}'>閱讀全文</a>\n"
        f"📡 <code>{source}</code>"
    )
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }
    requests.post(url, json=payload)

def main():
    seen = set()
    new_count = 0
    for feed_url in RSS_FEEDS:
        feed = feedparser.parse(feed_url)
        source = feed.feed.get("title", feed_url)
        for entry in feed.entries[:10]:
            title = entry.get("title", "")
            link = entry.get("link", "")
            h = hash_title(title)
            if h in seen or not is_important(title):
                continue
            seen.add(h)
            send_telegram(title, link, source)
            new_count += 1
    print(f"[{datetime.now()}] 推送了 {new_count} 條新聞")

if __name__ == "__main__":
    main()
