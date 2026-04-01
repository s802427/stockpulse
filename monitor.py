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
            "max_tokens": 200,
            "messages": [{
                "role": "user",
                "content": "分析這條美股新聞，用以下格式回覆，每行一個，不要加其他文字：\nTRANSLATION: 繁體中文翻譯\nIMPACT: 💡對股市影響（15字內）\nSECTOR: tech或finance或energy或health或consumer或general\nPRIORITY: high或medium或low\n\n標題：" + title
            }]
        }
        r = requests.post("https://​​​​​​​​​​​​​​​​
