import feedparser
import requests
import hashlib
import os
from datetime import datetime

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY")
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

HIGH = [
    "fed rate", "rate hike", "rate cut", "earnings beat", "earnings miss",
    "bankruptcy", "merger", "acquisition", "IPO", "layoff",
    "inflation", "GDP", "job report", "payroll", "crash", "surge",
]

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
    return sum(1 for kw in LOW if kw in t) >= 2

def analyze(title):
    try:
        headers = {
            "x-api-key": ANTHROPIC_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        body = {
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": 150,
            "messages": [{
                "role": "user",
                "content": f"""以下是一條美股新聞標題，請用繁體中文回覆兩行：
第一行：翻譯標題
第二行：一句話說明對股市的影響（15字以內）

標題：{title}"""
            }]
        }
        r = requests.post("https://api.anthropic.com/v1/messages", headers=headers, json=body, timeout=10)
        return r.json()["content"][0]["text"].strip()
    except:
        return ""

def send_telegram(title, link, source, analysis):
    message = (
        f"📰 <b>{title}</b>\n"
        f"{analysis}\n\n"
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
            analysis = analyze(title)
            send_telegram(title, link, source, analysis)
            new_count += 1
    print(f"[{datetime.now()}] 推送了 {new_count} 條新聞")

if __name__ == "__main__":
    main()
