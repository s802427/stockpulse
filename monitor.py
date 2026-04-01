import feedparser
import requests
import hashlib
import os
from datetime import datetime

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY")

CHANNELS = {
    "all": "@stockpulse_news2",
    "tech": "@stockpulse_tech",
    "finance": "@stockpulse_finance",
    "energy": "@stockpulse_energy",
    "health": "@stockpulse_health",
    "consumer": "@stockpulse_consumer",
    "general": "@stockpulse_news2",
}

PRIORITY_EMOJI = {
    "high": "🔴",
    "medium": "🟡",
    "low": "🟢",
}

RSS_FEEDS = [
    "https://feeds.finance.yahoo.com/rss/2.0/headline?s=^GSPC&region=US&lang=en-US",
    "https://feeds.finance.yahoo.com/rss/2.0/headline?s=^DJI&region=US&lang=en-US",
    "https://finance.yahoo.com/news/rssindex",
    "https://feeds.marketwatch.com/marketwatch/topstories/",
    "https://feeds.marketwatch.com/marketwatch/marketpulse/",
    "https://www.cnbc.com/id/100003114/device/rss/rss.html",
    "https://www.cnbc.com/id/10001147/device/rss/rss.html",
    "https://feeds.reuters.com/reuters/businessNews",
    "https://feeds.reuters.com/reuters/companyNews",
    "https://www.investors.com/feed/",
    "https://techcrunch.com/feed/",
    "https://feeds.arstechnica.com/arstechnica/index",
    "https://feeds.federalreserve.gov/feeds/press_monetary.xml",
    "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=8-K&dateb=&owner=include&count=20&output=atom",

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
        prompt = "分析這條美股新聞，用以下格式回覆，每行一個：\n"
        prompt += "TRANSLATION: 繁體中文翻譯\n"
        prompt += "IMPACT: 對股市影響（15字內）\n"
        prompt += "SECTOR: tech或finance或energy或health或consumer或general\n"
        prompt += "PRIORITY: high或medium或low\n\n"
        prompt += "標題：" + title
        body = {
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": 200,
            "messages": [{"role": "user", "content": prompt}]
        }
        r = requests.post("https://api.anthropic.com/v1/messages", headers=headers, json=body, timeout=10)
        text = r.json()["content"][0]["text"].strip()
        translation = ""
        impact = ""
        sector = "general"
        priority = "medium"
        for line in text.split("\n"):
            if line.startswith("TRANSLATION:"):
                translation = line.replace("TRANSLATION:", "").strip()
            elif line.startswith("IMPACT:"):
                impact = line.replace("IMPACT:", "").strip()
            elif line.startswith("SECTOR:"):
                sector = line.replace("SECTOR:", "").strip().lower()
            elif line.startswith("PRIORITY:"):
                priority = line.replace("PRIORITY:", "").strip().lower()
        if sector not in CHANNELS:
            sector = "general"
        if priority not in PRIORITY_EMOJI:
            priority = "medium"
        return translation, impact, sector, priority
    except:
        return "", "", "general", "medium"

def send_telegram(chat_id, title, link, source, zh, impact, priority):
    emoji = PRIORITY_EMOJI.get(priority, "🟡")
    msg = emoji + " <b>" + title + "</b>\n"
    msg += "🇹🇼 " + zh + "\n"
    msg += "💡 " + impact + "\n\n"
    msg += "🔗 <a href='" + link + "'>閱讀全文</a>\n"
    msg += "📡 <code>" + source + "</code>"
    url = "https://api.telegram.org/bot" + TELEGRAM_TOKEN + "/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": msg,
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
            zh, impact, sector, priority = analyze(title)
            send_telegram(CHANNELS["all"], title, link, source, zh, impact, priority)
            if sector in CHANNELS and sector != "general":
                send_telegram(CHANNELS[sector], title, link, source, zh, impact, priority)
            new_count += 1
    print(str(datetime.now()) + " 推送了 " + str(new_count) + " 條新聞")

if __name__ == "__main__":
    main()
