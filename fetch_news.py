import os
import json
import requests
from datetime import datetime, timedelta
from anthropic import Anthropic

client = Anthropic()
NEWS_API_KEY = os.environ.get("NEWS_API_KEY")
DAYS_TO_KEEP = 7

def fetch_news():
    articles = []
    for lang, q in [("en", "artificial intelligence OR AI"), ("ja", "人工知能 OR AI")]:
        size = 15 if lang == "en" else 5
        r = requests.get("https://newsapi.org/v2/everything", params={
            "q": q, "language": lang, "sortBy": "publishedAt",
            "pageSize": size, "apiKey": NEWS_API_KEY
        })
        articles += r.json().get("articles", [])
    return articles

def process(title, desc):
    msg = client.messages.create(
        model="claude-opus-4-5", max_tokens=300,
        messages=[{"role": "user", "content": (
            "以下のニュースを日本語に翻訳し要約してください。\n"
            "形式:\nタイトル翻訳: XXX\n要約: XXX\n\n"
            f"タイトル: {title}\n内容: {desc or 'なし'}"
        )}]
    )
    t, s = title, ""
    for line in msg.content[0].text.split("\n"):
        if line.startswith("タイトル翻訳:"):
            t = line.replace("タイトル翻訳:", "").strip()
        elif line.startswith("要約:"):
            s = line.replace("要約:", "").strip()
    return t, s

def main():
    today = datetime.now().strftime("%Y-%m-%d")
    data = {}
    if os.path.exists("news_data.json"):
        with open("news_data.json", "r", encoding="utf-8") as f:
            data = json.load(f)
    cutoff = datetime.now() - timedelta(days=DAYS_TO_KEEP)
    data = {k: v for k, v in data.items() if datetime.strptime(k, "%Y-%m-%d") >= cutoff}
    items = []
    for a in fetch_news():
        t, s = process(a["title"], a.get("description"))
        items.append({"title": t, "url": a["url"], "summary": s, "source": a["source"]["name"]})
    data[today] = items
    with open("news_data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    rows = ""
    for date in sorted(data.keys(), reverse=True):
        d = datetime.strptime(date, "%Y-%m-%d").strftime("%Y年%m月%d日")
        rows += f'<div class="day"><h2>📅 {d}</h2>'
        for a in data[date]:
            rows += f'<div class="card"><h3>{a["title"]}</h3><p>{a["summary"]}</p><a href="{a["url"]}" target="_blank">📎 {a["source"]}</a></div>'
        rows += '</div>'
    html = f'''<!DOCTYPE html><html lang="ja"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><title>AIニュース</title><style>body{{font-family:sans-serif;background:#f5f5f5;margin:0;padding:16px}}h1{{text-align:center;color:#1a1a2e}}.day{{margin-bottom:24px}}h2{{font-size:1em;color:#444;border-bottom:2px solid #4CAF50;padding-bottom:4px}}.card{{background:white;border-radius:12px;padding:12px;margin:8px 0;box-shadow:0 2px 6px rgba(0,0,0,.08)}}.card h3{{font-size:.95em;color:#1a1a2e;margin:0 0 6px}}.card p{{font-size:.85em;color:#555;margin:6px 0}}.card a{{font-size:.75em;color:#2e7d32;text-decoration:none}}</style></head><body><h1>🤖 AIニュースダイジェスト</h1><p style="text-align:center;color:#888;font-size:.8em">最終更新: {datetime.now().strftime("%Y年%m月%d日")}</p>{rows}</body></html>'''
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)

if __name__ == "__main__":
    main()
