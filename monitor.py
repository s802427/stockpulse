import feedparser
import requests
import hashlib
import os
import json
import time
from datetime import datetime, timezone, timedelta

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

PRIORITY_SCORE = {
    "high": 10,
    "medium": 6,
    "low": 3,
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

TZ = timezone(timedelta(hours=8))
MAX_PER_SOURCE = 3

# Haiku 價格（美元/百萬tokens）
HAIKU_INPUT_PRICE = 0.80
HAIKU_OUTPUT_PRICE = 4.00

api_usage = {"input_tokens": 0, "output_tokens": 0}

def now_str():
    return datetime.now(TZ).strftime("%Y-%m-%d %H:%M")

def track_usage(response_json):
    """記錄 API token 使用量"""
    try:
        usage = response_json.get("usage", {})
        api_usage["input_tokens"] += usage.get("input_tokens", 0)
        api_usage["output_tokens"] += usage.get("output_tokens", 0)
    except:
        pass

def get_cost():
    """計算預估花費（美元）"""
    input_cost = api_usage["input_tokens"] / 1_000_000 * HAIKU_INPUT_PRICE
    output_cost = api_usage["output_tokens"] / 1_000_000 * HAIKU_OUTPUT_PRICE
    return round(input_cost + output_cost, 4)

def load_sent():
    """從 GitHub 載入已推送的 hash 清單，清除7天前記錄"""
    try:
        import base64
        api_url = "https://api.github.com/repos/" + GITHUB_REPO + "/contents/sent.json"
        headers = {
            "Authorization": "Bearer " + MY_GITHUB_TOKEN,
            "Accept": "application/vnd.github.v3+json"
        }
        r = requests.get(api_url, headers=headers)
        if r.status_code == 404:
            return set(), ""
        data = r.json()
        sha = data.get("sha", "")
        content = json.loads(base64.b64decode(data["content"]).decode())

        # 清除7天前的記錄
        cutoff = datetime.now(TZ) - timedelta(days=7)
        filtered = {
            h: date_str
            for h, date_str in content.get("hashes", {}).items()
            if datetime.fromisoformat(date_str) > cutoff
        }
        print(f"已推送記錄：{len(filtered)} 條（清除後）")
        return set(filtered.keys()), sha, filtered
    except Exception as e:
        print(f"load_sent 錯誤：{e}")
        return set(), "", {}

def save_sent(hashes_with_dates, sha):
    """把已推送的 hash 存回 GitHub（含日期）"""
    try:
        import base64
        api_url = "https://api.github.com/repos/" + GITHUB_REPO + "/contents/sent.json"
        headers = {
            "Authorization": "Bearer " + MY_GITHUB_TOKEN,
            "Accept": "application/vnd.github.v3+json"
        }
        content = json.dumps({"hashes": hashes_with_dates}, ensure_ascii=False)
        encoded = base64.b64encode(content.encode()).decode()
        payload = {
            "message": "update sent",
            "content": encoded,
        }
        if sha:
            payload["sha"] = sha
        requests.put(api_url, headers=headers, json=payload)
        print("sent.json 更新完成")
    except Exception as e:
        print(f"save_sent 錯誤：{e}")

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
        prompt = "篩選重要財經新聞，回覆格式：編號,分數（1-5）每行一條\n"
        prompt += "例如：1,4\n2,2\n3,5\n\n"
        prompt += "保留標準：財報、Fed政策、併購、裁員、IPO、經濟數據、央行決策、重大監管\n"
        prompt += "排除標準：娛樂、體育、生活、點擊誘餌（如『驚人數字』『你不知道的』『熱門股推薦』）、廣告式標題\n\n"
        prompt += news_list
        body = {
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": 200,
            "messages": [{"role": "user", "content": prompt}]
        }
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers=headers, json=body, timeout=10
        )
        rj = r.json()
        track_usage(rj)
        text = rj["content"][0]["text"].strip()
        results = []
        for line in text.split("\n"):
            line = line.strip()
            if "," in line:
                parts = line.split(",")
                if len(parts) == 2 and parts[0].strip().isdigit() and parts[1].strip().isdigit():
                    idx = int(parts[0].strip()) - 1
                    score = int(parts[1].strip())
                    if score >= 4 and idx < len(titles_batch):
                        results.append(titles_batch[idx])
        return results
    except Exception as e:
        print(f"quick_filter 錯誤：{e}")
        return []

def analyze_batch(news_batch):
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
        prompt += "PRIORITY: high或medium或low\n"
        prompt += "請務必使用繁體中文，不得使用簡體中文。\n\n"
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
        rj = r.json()
        track_usage(rj)
        text = rj["content"][0]["text"].strip()
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
        while len(results) < len(news_batch):
            results.append(("", "", "general", "medium"))
        return results[:len(news_batch)]
    except Exception as e:
        print(f"analyze_batch 錯誤：{e}")
        return [("", "", "general", "medium")] * len(news_batch)

def send_telegram(chat_id, text, retry=3):
    url = "https://api.telegram.org/bot" + TELEGRAM_TOKEN + "/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }
    for attempt in range(retry):
        try:
            r = requests.post(url, json=payload)
            if r.status_code == 200:
                time.sleep(1)
                return
            elif r.status_code == 429:
                wait = r.json().get("parameters", {}).get("retry_after", 30)
                print(f"Telegram 限速，等待 {wait} 秒")
                time.sleep(wait)
            else:
                print(f"Telegram 發送失敗 {chat_id}：{r.text}")
                return
        except Exception as e:
            print(f"Telegram 錯誤：{e}")
            return

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
            "updated": datetime.now(TZ).strftime("%Y/%m/%d %H:%M"),
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

def send_summary(results, cost):
    try:
        now = datetime.now(TZ).strftime("%H:%M")
        date = datetime.now(TZ).strftime("%Y/%m/%d")
        high = [r for r in results if r[3] == "high"]
        medium = [r for r in results if r[3] == "medium"]
        low = [r for r in results if r[3] == "low"]

        sectors = {}
        for r in results:
            s = r[2]
            if s not in sectors:
                sectors[s] = []
            sectors[s].append(PRIORITY_SCORE.get(r[3], 6))

        msg = "📋 <b>本次掃描摘要 " + now + "</b>\n"
        msg += "🗓 " + date + "\n"
        msg += "━━━━━━━━━━━━━━━\n"
        msg += "🔴 高重要 x" + str(len(high))
        msg += "  🟡 中重要 x" + str(len(medium))
        msg += "  🟢 一般 x" + str(len(low)) + "\n"
        msg += "共 " + str(len(results)) + " 條重要財經新聞\n"
        msg += "💰 本次花費：$" + str(cost) + " USD\n"

        if sectors:
            msg += "\n━━━━━━━━━━━━━━━\n"
            msg += "💹 <b>板塊動態</b>\n"
            icons = {
                "tech": "💻", "finance": "🏦", "energy": "⚡",
                "health": "💊", "consumer": "🛒"
            }
            sector_scores = {}
            for s, scores in sectors.items():
                if s == "general":
                    continue
                avg = round(sum(scores) / len(scores), 1)
                sector_scores[s] = (avg, len(scores))
            for s, (avg, count) in sorted(sector_scores.items(), key=lambda x: -x[1][0]):
                icon = icons.get(s, "📰")
                emoji = "🔴" if avg >= 8 else "🟡" if avg >= 5 else "🟢"
                msg += icon + " " + s + "  " + emoji + " " + str(avg) + "/10  x" + str(count) + "\n"

        if high:
            msg += "\n━━━━━━━━━━━━━━━\n"
            msg += "🔥 <b>重點摘要</b>\n"
            for i, r in enumerate(high[:5]):
                if r[1]:
                    msg += str(i+1) + ". " + r[1] + "\n"

        send_telegram(CHANNELS["all"], msg)
    except Exception as e:
        print(f"send_summary 錯誤：{e}")

def send_daily_summary(daily_results):
    try:
        date = datetime.now(TZ).strftime("%Y/%m/%d")
        high = [r for r in daily_results if r[3] == "high"]
        medium = [r for r in daily_results if r[3] == "medium"]

        sectors = {}
        for r in daily_results:
            s = r[2]
            if s not in sectors:
                sectors[s] = []
            sectors[s].append(PRIORITY_SCORE.get(r[3], 6))

        msg = "🌙 <b>每日總結 " + date + "</b>\n"
        msg += "━━━━━━━━━━━━━━━\n"
        msg += "今日共推送 " + str(len(daily_results)) + " 條財經新聞\n"
        msg += "🔴 高重要 x" + str(len(high)) + "  🟡 中重要 x" + str(len(medium)) + "\n"

        if sectors:
            msg += "\n💹 <b>今日板塊表現</b>\n"
            icons = {
                "tech": "💻", "finance": "🏦", "energy": "⚡",
                "health": "💊", "consumer": "🛒"
            }
            sector_scores = {}
            for s, scores in sectors.items():
                if s == "general":
                    continue
                avg = round(sum(scores) / len(scores), 1)
                sector_scores[s] = (avg, len(scores))
            for s, (avg, count) in sorted(sector_scores.items(), key=lambda x: -x[1][0]):
                icon = icons.get(s, "📰")
                emoji = "🔴" if avg >= 8 else "🟡" if avg >= 5 else "🟢"
                msg += icon + " " + s + "  " + emoji + " " + str(avg) + "/10  x" + str(count) + "\n"

        if high:
            msg += "\n🏆 <b>今日最重要</b>\n"
            for i, r in enumerate(high[:5]):
                if r[1]:
                    msg += str(i+1) + ". " + r[1] + "\n"

        send_telegram(CHANNELS["all"], msg)
        print("每日總結已發送")
    except Exception as e:
        print(f"send_daily_summary 錯誤：{e}")

def load_daily_results():
    try:
        import base64
        today = datetime.now(TZ).strftime("%Y-%m-%d")
        api_url = "https://api.github.com/repos/" + GITHUB_REPO + "/contents/daily.json"
        headers = {
            "Authorization": "Bearer " + MY_GITHUB_TOKEN,
            "Accept": "application/vnd.github.v3+json"
        }
        r = requests.get(api_url, headers=headers)
        if r.status_code == 404:
            return [], "", today
        data = r.json()
        sha = data.get("sha", "")
        content = json.loads(base64.b64decode(data["content"]).decode())
        if content.get("date") != today:
            return [], sha, today
        return content.get("results", []), sha, today
    except Exception as e:
        print(f"load_daily_results 錯誤：{e}")
        return [], "", datetime.now(TZ).strftime("%Y-%m-%d")

def save_daily_results(results, sha, today):
    try:
        import base64
        api_url = "https://api.github.com/repos/" + GITHUB_REPO + "/contents/daily.json"
        headers = {
            "Authorization": "Bearer " + MY_GITHUB_TOKEN,
            "Accept": "application/vnd.github.v3+json"
        }
        serializable = [list(r) for r in results]
        content = json.dumps({"date": today, "results": serializable}, ensure_ascii=False)
        encoded = base64.b64encode(content.encode()).decode()
        payload = {
            "message": "update daily",
            "content": encoded,
        }
        if sha:
            payload["sha"] = sha
        requests.put(api_url, headers=headers, json=payload)
        print("daily.json 更新完成")
    except Exception as e:
        print(f"save_daily_results 錯誤：{e}")

def main():
    sent_hashes, sent_sha, hashes_with_dates = load_sent()

    seen = set()
    all_news = get_newsapi_titles() + get_rss_titles()
    unique_news = []
    seen_titles = []
    source_count = {}

    for item in all_news:
        h = hashlib.md5(item[0].encode()).hexdigest()
        if h in seen:
            continue
        if h in sent_hashes:
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
            source = item[2]
            source_count[source] = source_count.get(source, 0) + 1
            if source_count[source] > MAX_PER_SOURCE:
                continue
            seen.add(h)
            seen_titles.append(item[0])
            unique_news.append(item)

    print(now_str() + " 收集 " + str(len(unique_news)) + " 條（新）")

    if not unique_news:
        print("沒有新新聞，結束")
        return

    important_news = []
    for i in range(0, len(unique_news), 20):
        important_news += quick_filter(unique_news[i:i+20])
    print(now_str() + " 篩後 " + str(len(important_news)) + " 條")

    results = []
    news_for_json = []
    new_hashes_with_dates = {}
    now_iso = datetime.now(TZ).isoformat()

    for i in range(0, len(important_news), 10):
        batch = important_news[i:i+10]
        analyzed = analyze_batch(batch)
        for (title, link, source), (zh, impact, sector, priority) in zip(batch, analyzed):
            if not zh:
                continue
            h = hashlib.md5(title.encode()).hexdigest()
            new_hashes_with_dates[h] = now_iso
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

    cost = get_cost()
    print(f"本次 API 花費：${cost} USD（input: {api_usage['input_tokens']} tokens, output: {api_usage['output_tokens']} tokens）")

    if results:
        send_summary(results, cost)
        update_news_json(news_for_json)
        hashes_with_dates.update(new_hashes_with_dates)
        save_sent(hashes_with_dates, sent_sha)

        daily_results, daily_sha, today = load_daily_results()
        daily_results = [tuple(r) for r in daily_results] + results
        save_daily_results(daily_results, daily_sha, today)

        hour = datetime.now(TZ).hour
        if hour == 5:
            send_daily_summary(daily_results)

    print(now_str() + " 推送 " + str(len(results)) + " 條")

if __name__ == "__main__":
    main()
