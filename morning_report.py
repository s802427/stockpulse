import requests
import os
from datetime import datetime

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY")
CHAT_ID = "@stockpulse_news2"

WATCHLIST = ["^GSPC", "^DJI", "^IXIC", "GC=F", "CL=F", "BTC-USD", "DX-Y.NYB"]
NAMES = {
    "^GSPC": "S&P 500",
    "^DJI": "道瓊",
    "^IXIC": "那斯達克",
    "GC=F": "黃金",
    "CL=F": "原油",
    "BTC-USD": "比特幣",
    "DX-Y.NYB": "美元指數"
}

def get_market_data():
    results = []
    for symbol in WATCHLIST:
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=2d"
            headers = {"User-Agent": "Mozilla/5.0"}
            r = requests.get(url, headers=headers, timeout=10)
            data = r.json()
            meta = data["chart"]["result"][0]["meta"]
            price = meta.get("regularMarketPrice", 0)
            prev = meta.get("chartPreviousClose", price)
            change = price - prev
            pct = (change / prev * 100) if prev else 0
            arrow = "🟢" if change >= 0 else "🔴"
            name = NAMES.get(symbol, symbol)
            results.append(f"{arrow} {name}: {price:,.2f} ({pct:+.2f}%)")
        except:
            results.append(f"⚪ {NAMES.get(symbol, symbol)}: 數據獲取失敗")
    return "\n".join(results)

def get_news():
    from feedparser import parse
    headlines = []
    feeds = [
        "https://feeds.marketwatch.com/marketwatch/topstories/",
        "https://www.cnbc.com/id/100003114/device/rss/rss.html",
        "https://feeds.reuters.com/reuters/businessNews",
    ]
    for url in feeds:
        feed = parse(url)
        for entry in feed.entries[:5]:
            headlines.append(entry.get("title", ""))
    return headlines[:15]

def generate_report(market_data, headlines):
    try:
        headers = {
            "x-api-key": ANTHROPIC_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        news_text = "\n".join(f"- {h}" for h in headlines)
        today = datetime.now().strftime("%Y/%m/%d")
        body = {
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": 1000,
            "messages": [{
                "role": "user",
                "content": f"""你是專業美股分析師，根據以下資訊用繁體中文生成今日盤前早報。

今日日期：{today}

市場數據：
{market_data}

今日新聞標題：
{news_text}

請用以下格式生成早報，使用純文字不要用Markdown：

📊 StockPulse 盤前早報
{today} 美股開盤前必讀

━━━━━━━━━━━━━━━
🌍 昨日市場收盤
（整理市場數據重點）

━━━━━━━━━━━━━━━
🔥 今日Top3重點新聞
1. 標題＋一句影響分析
2. 標題＋一句影響分析
3. 標題＋一句影響分析

━━━━━━━━━━━━━━━
🏭 板塊動態
科技💻 金融🏦 能源⚡ 醫藥💊 消費🛒

━━━━━━━━━━━━━━━
😱 今日風險提醒
（潛在風險或需注意事項）

━━━━━━━━━━━━━━━
⚡ 今日市場情緒
（偏多/中性/偏空 + 理由）

━━━━━━━━━━━━━━━
💡 今日一句話策略
（給投資人的建議）"""
            }]
        }
        r = requests.post("https://api.anthropic.com/v1/messages", headers=headers, json=body, timeout=30)
        return r.json()["content"][0]["text"].strip()
    except:
        return "早報生成失敗，請稍後再試"

def send_telegram(message):
    url = "https://api.telegram.org/bot" + TELEGRAM_TOKEN + "/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    requests.post(url, json=payload)

def main():
    market_data = get_market_data()
    headlines = get_news()
    report = generate_report(market_data, headlines)
    send_telegram(report)
    print("早報已發送")

if __name__ == "__main__":
    main()
