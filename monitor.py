import feedparser
import requests
import hashlib
import os
from datetime import datetime

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY")
NEWS_API_KEY = os.environ.get("NEWS_API_KEY")

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
    "https://feeds.finance.yahoo.com/rss/2.0/headline?s=^IXIC&region=US&lang=en-US",
    "https://finance.yahoo.com/news/rssindex",
    "https://feeds.marketwatch.com/marketwatch/topstories/",
    "https://feeds.marketwatch.com/marketwatch/marketpulse/",
    "https://www.cnbc.com/id/100003114/device/rss/rss.html",
    "https://www.cnbc.com/id/10001147/device/rss/rss.html",
    "https://www.cnbc.com/id/15839135/device/rss/rss.html",
    "https://feeds.reuters.com/reuters/businessNews",
    "https://feeds.reuters.com/reuters/companyNews",
    "https://feeds.reuters.com/reuters/financialsNews",
    "https://www.investors.com/feed/",
    "https://feeds.federalreserve.gov/feeds/press_monetary.xml",
    "https://feeds.federalreserve.gov/feeds/press_all.xml",
    "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=8-K&dateb=&owner=include&count=20&output=atom",
    "https://feeds.bloomberg.com/markets/news.rss",
    "https://www.ft.com/rss/home/us",
    "https://fortune.com/feed/",
    "https://www.businessinsider.com/rss",
    "https://oilprice.com/rss/main",
    "https://www.fiercepharma.com/rss/xml",
    "https://feeds.barrons.com/barrons/markets",
]

def get_newsapi_titles():
    try:
        url = "https://newsapi.org/v2/top-headlines"
        params = {
            "category": "business",
            "language": "en",
            "pageSize": 100,
            "apiKey": NEWS_API_KEY
        }
        r = requests.get(url, params=params, timeout=10)
        articles = r.json().get("articles", [])
        results = []
        for a in articles:
            title = a.get("title", "")
            link = a.get("url", "")
            source = a.get("source", {}).get("name", "NewsAPI")
            if title and link:
                results.append((title, link, source))
        return results
    except:
        return []

def get_rss_titles():
    results = []
    for feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            source = feed.feed.get("title", feed_url)
            for entry in feed.entries[:15]:
                title = entry.get("title", "")
                link = entry.get("link", "")
                if title and link:
                    results.append((title, link, source))
        except:
            continue
    return results

def quick_filter(titles_batch):
    try:
        headers = {
            "x-api-key": ANTHROPIC_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        news_list = "\n".join(f"{i+1}. {t[0]}" for i, t in enumerate(titles_batch))
        prompt = "以下是美股新聞標題，請篩選出值得深度分析的重要財經新聞，只回覆編號，用逗號分隔，例如：1,3,5\n\n"
        prompt += "重要新聞標準：財報、Fed政策、重大併購、裁員、IPO、經濟數據、股價大漲大跌、重大政策\n"
        prompt += "排除：娛樂、體育、生活、非財經相關新聞\n\n"
        prompt += news_list
        body = {
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": 100,
            "messages": [{"role": "user", "content": prompt}]
        }
        r = requests.post("https://api.anthropic.com/v1/messages", headers=headers, json=body, timeout=10)
        text = r.json()["content"][0]["text"].strip()
        indices = [int(x.strip()) - 1 for x in text.split(",") if x.strip().isdigit()]
        return [titles_batch[i] for i in indices if i < len(titles_batch)]
    except:
        return []

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
    all_news = []
    all_news += get_newsapi_titles()
    all_news += get_rss_titles()
    unique_news = []
    for item in all_news:
        h = hashlib.md5(item[0].encode()).hexdigest()
        if h not in seen:
            seen.add(h)
            unique_news.append(item)
    print(str(datetime.now()) + " 共收集 " + str(len(unique_news)) + " 條新聞")
    batch_size = 20
    important_news = []
    for i in range(0, len(unique_news), batch_size):
        batch = unique_news[i:i+batch_size]
        filtered = quick_filter(batch)
        important_news += filtered
    print(str(datetime.now()) + " 粗篩後剩 " + str(len(important_news)) + " 條")
    sent_count = 0
    for title, link, source in important_news:
        zh, impact, sector, priority = analyze(title)
        send_telegram(CHANNELS["all"], title, link, source, zh, impact, priority)
        if sector in CHANNELS and sector != "general":
            send_telegram(CHANNELS[sector], title, link, source, zh, impact, priority)
        sent_count += 1
    print(str(datetime.now()) + " 推送了 " + str(sent_count) + " 條新聞")

if __name__ == "__main__":
    main()
