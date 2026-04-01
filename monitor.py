import feedparser
import requests
import hashlib
import os
import json
from datetime import datetime

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY")
NEWS_API_KEY = os.environ.get("NEWS_API_KEY")
MY_GITHUB_TOKEN = os.environ.get("MY_GITHUB_TOKEN")
GITHUB_REPO = "s802427/stockpulse"

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
    "https://finance.yahoo.com/news/rssindex",
    "https://feeds.marketwatch.com/marketwatch/topstories/",
    "https://feeds.reuters.com/reuters/businessNews",
    "https://feeds.reuters.com/reuters/companyNews",
    "https://www.investors.com/feed/",
    "https://fortune.com/feed/",
    "https://oilprice.com/rss/main",
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
        print(f"NewsAPI 取得 {len(results)} 條")
        return results
    except Exception as e:
        print(f"NewsAPI 錯誤：{e}")
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
        except Exception as e:
            print(f"RSS 錯誤 {feed_url}：{e}")
            continue
    print(f"RSS 取得 {len(results)} 條")
    return results

def quick_filter(titles_batch):
    try:
        headers = {
            "x-api-key": ANTHROPIC_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        news_list = "\n".join(
            str(i+1) + ". " + t[0] for i, t in enumerate(titles_batch)
        )
        prompt = "篩選重要財經新聞，只回覆編號用逗號分隔：\n"
        prompt += "標準：財報Fed政策併購裁員IPO經濟數據\n"
        prompt += "排除：娛樂體育生活\n\n" + news_list
        body = {
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": 100,
            "messages": [{"role": "user", "content": prompt}]
        }
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers=headers, json=body, timeout=10
        )
        text = r.json()["content"][0]["text"].strip()
        indices = [
            int(x.strip()) - 1
            for x in text.split(",")
            if x.strip().isdigit()
        ]
        return [titles_batch[i] for i in indices if i < len(titles_batch)]
    except Exception as e:
        print(f"quick_filter 錯誤：{e}")
        return []

def analyze_batch(news_batch):
    """批次分析多條新聞，一次 API 呼叫處理全部"""
    try:
        headers = {
            "x-api-key": ANTHROPIC_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        news_list = "\n".join(
            f"{i+1}. {item[0]}" for i, item in enumerate(news_batch)
        )
        prompt = "分析以下每條美股新聞，每條用以下格式輸出，條目間用---分隔：\n"
        prompt += "TRANSLATION: 繁體中文翻譯\n"
        prompt += "IMPACT: 影響15字內\n"
        prompt += "SECTOR: tech或finance或energy或health或consumer或general\n"
        prompt += "PRIORITY: high或medium或low\n\n"
        prompt += news_list
        body = {
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": 1000,
            "messages": [{"role": "user", "content": prompt}]
        }
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers=headers, json=body, timeout=30
        )
        text = r.json()["content"][0]["text"].strip()
        blocks = text.split("---")
        results = []
        for block in blocks:
            translation = ""
            impact = ""
            sector = "general"
            priority = "medium"
            for line in block.strip().split("\n"):
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
            results.append((translation, impact, sector, priority))
        # 數量對不上時補空值
        while len(results) < len(news_batch):
            results.append(("", "", "general", "medium"))
        return results[:len(news_batch)]
    except Exception as e:
        print(f"analyze_batch 錯誤：{e}")
        return [("", "", "general", "medium")] * len(news_batch)

def send_telegram(chat_id, text):
    try:
        url = "https://api.telegram.org/bot" + TELEGRAM_TOKEN + "/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": False
        }
        r = requests.post(url, json=payload)
        if r.status_code != 200:
            print(f"Telegram 發送失敗 {chat_id}：{r.text}")
    except Exception as e:
        print(f"Telegram 錯誤：{e}")

def update_news_json(news_list):
    try:
        import base64
        api_url = "https://api.github.com/repos/" + GITHUB_REPO + "/contents/news.json"
        headers = {
            "Authorization": "Bearer " + MY_GITHUB_TOKEN,
            "Accept": "application/vnd.github.v3+json"
        }
        r = requests.get(api_url, headers=headers)
        sha = r.json().get("sha", "")
        data = {
            "updated": datetime.now().strftime("%Y/%m/%d %H:%M"),
            "news": news_list
        }
        content = json.dumps(data, ensure_ascii=False, indent=2)
        encoded = base64.b64encode(content.encode()).decode()
        payload = {
            "message": "update news",
            "content": encoded,
            "sha": sha
        }
        requests.put(api_url, headers=headers, json=payload)
        print("news.json 更新完成")
    except Exception as e:
        print(f"news.json 更新失敗：{e}")

def send_summary(results):
    try:
        now = datetime.now().strftime("%H:%M")
        high = [r for r in results if r[3] == "high"]
        medium = [r for r in results if r[3] == "medium"]
        low = [r for r in results if r[3] == "low"]
        sectors = {}
        for r in results:
            s = r[2]
            if s not in sectors:
                sectors[s] = []
            sectors[s].append(r[3])
        msg = "📋 <b>本次掃描摘要 " + now + "</b>\n"
        msg += "━━━━━━━━━━━━━━━\n"
        if high:
            msg += "\n🔴 <b>高重要 x" + str(len(high)) + "</b>\n"
            for r in high:
                msg += "• " + r[1] + "\n"
        if medium:
            msg += "\n🟡 <b>中重要 x" + str(len(medium)) + "</b>\n"
            for r in medium:
                msg += "• " + r[1] + "\n"
        if low:
            msg += "\n🟢 <b>一般關注 x" + str(len(low)) + "</b>\n"
            for r in low:
                msg += "• " + r[1] + "\n"
        if sectors:
            msg += "\n━━━━━━━━━━━━━━━\n"
            msg += "💹 <b>板塊動態</b>\n"
            icons = {
                "tech": "💻", "finance": "🏦", "energy": "⚡",
                "health": "💊", "consumer": "🛒"
            }
            for s, priorities in sectors.items():
                if s == "general":
                    continue
                icon = icons.get(s, "📰")
                top = "🔴" if "high" in priorities else "🟡" if "medium" in priorities else "🟢"
                msg += icon + " " + s + " " + top + "\n"
        send_telegram(CHANNELS["all"], msg)
    except Exception as e:
        print(f"send_summary 錯誤：{e}")

def main():
    seen = set()
    all_news = get_newsapi_titles() + get_rss_titles()
    unique_news = []
    seen_titles = []
    for item in all_news:
        h = hashlib.md5(item[0].encode()).hexdigest()
        if h in seen:
            continue
        is_dup = False
        for t in seen_titles:
            words_a = set(item[0].lower().split())
            words_b = set(t.lower().split())
            common = len(words_a & words_b)
            total = len(words_a | words_b)
            if total > 0 and common / total > 0.6:
                is_dup = True
                break
        if not is_dup:
            seen.add(h)
            seen_titles.append(item[0])
            unique_news.append(item)
    print(str(datetime.now()) + " 收集 " + str(len(unique_news)) + " 條")

    important_news = []
    for i in range(0, len(unique_news), 20):
        important_news += quick_filter(unique_news[i:i+20])
    print(str(datetime.now()) + " 篩後 " + str(len(important_news)) + " 條")

    results = []
    news_for_json = []

    # 批次分析，每次最多10條
    for i in range(0, len(important_news), 10):
        batch = important_news[i:i+10]
        analyzed = analyze_batch(batch)
        for (title, link, source), (zh, impact, sector, priority) in zip(batch, analyzed):
            emoji = PRIORITY_EMOJI.get(priority, "🟡")
            msg = emoji + " <b>" + title + "</b>\n"
            msg += "🇹🇼 " + zh + "\n"
            msg += "💡 " + impact + "\n\n"
            msg += "🔗 <a href='" + link + "'>閱讀全文</a>\n"
            msg += "📡 <code>" + source + "</code>"
            send_telegram(CHANNELS["all"], msg)
            if sector in CHANNELS and sector != "general":
                send_telegram(CHANNELS[sector], msg)
            results.append((title, zh, sector, priority))
            news_for_json.append({
                "title": title,
                "zh": zh,
                "impact": impact,
                "sector": sector,
                "priority": priority,
                "link": link,
                "source": source
            })

    if results:
        send_summary(results)
        update_news_json(news_for_json)
    print(str(datetime.now()) + " 推送 " + str(len(results)) + " 條")

if __name__ == "__main__":
    main()
