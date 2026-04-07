import os
import json
import requests
from datetime import datetime, timedelta
from anthropic import Anthropic

client = Anthropic()

NEWS_API_KEY = os.environ.get("NEWS_API_KEY")
DAYS_TO_KEEP = 7

def fetch_english_news():
    url = "https://newsapi.org/v2/everything"
    params = {
        "q": "artificial intelligence OR AI OR machine learning",
        "language": "en",
        "sortBy": "publishedAt",
        "pageSize": 15,
        "apiKey": NEWS_API_KEY
    }
    res = requests.get(url, params=params)
    return res.json().get("articles", [])

def fetch_japanese_news():
    url = "https://newsapi.org/v2/everything"
    params = {
        "q": "人工知能 OR AI OR 機械学習",
        "language": "ja",
        "sortBy": "publishedAt",
        "pageSize": 5,
        "apiKey": NEWS_API_KEY
    }
    res = requests.get(url, params=params)
    return res.json().get("articles", [])

def summarize_article(title, description, is_english=True):
    prompt = f"""以下のニュース記事を日本語で3行以内に要約してください。

タイトル: {title}
内容: {description or 'なし'}

要約:"""
    message = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=200,
        messages=[{"role": "user", "content": prompt}]
    )
    return message.content[0].text

def load_existing_data():
    if os.path.exists("news_data.json"):
        with open("news_data.json", "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_data(data):
    with open("news_data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def delete_old_data(data):
    cutoff = datetime.now() - timedelta(days=DAYS_TO_KEEP)
    keys_to_delete = [
        k for k in data.keys()
        if datetime.strptime(k, "%Y-%m-%d") < cutoff
    ]
    for k in keys_to_delete:
        del data[k]
    return data

def generate_html(data):
    today = datetime.now().strftime("%Y年%m月%d日")
    articles_html = ""
    for date in sorted(data.keys(), reverse=True):
        articles = data[date]
        d = datetime.strptime(date, "%Y-%m-%d")
        label = d.strftime("%Y年%m月%d日")
        articles_html += f'<div class="day-block"><h2>📅 {label}</h2>'
        for a in articles:
            articles_html += f'''
            <div class="card">
                <a href="{a["url"]}" target="_blank"><h3>{a["title"]}</h3></a>
                <p>{a["summary"]}</p>
                <span class="tag">{a["source"]}</span>
            </div>'''
        articles_html += '</div>'

    html = f'''<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AIニュースダイジェスト</title>
<style>
  body {{ font-family: sans-serif; background: #f5f5f5; margin: 0; padding: 16px; }}
  h1 {{ color: #1a1a2e; font-size: 1.4em; text-align: center; }}
  .day-block {{ margin-bottom: 24px; }}
  h2 {{ font-size: 1em; color: #444; border-bottom: 2px solid #4CAF50; padding-bottom: 4px; }}
  .card {{ background: white; border-radius: 12px; padding: 12px; margin: 8px 0; box-shadow: 0 2px 6px rgba(0,0,0,0.08); }}
  .card a {{ text-decoration: none; color: #1a1a2e; font-size: 0.95em; font-weight: bold; }}
  .card p {{ font-size: 0.85em; color: #555; margin: 6px 0; }}
  .tag {{ font-size: 0.75em; background: #e8f5e9; color: #2e7d32; padding: 2px 8px; border-radius: 20px; }}
</style>
</head>
<body>
<h1>🤖 AIニュースダイジェスト</h1>
<p style="text-align:center;color:#888;font-size:0.8em;">最終更新: {today}</p>
{articles_html}
</body>
</html>'''
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)

def main():
    today = datetime.now().strftime("%Y-%m-%d")
    data = load_existing_data()
    data = delete_old_data(data)
    eng_articles = fetch_english_news()
    jpn_articles = fetch_japanese_news()
    today_articles = []
    for a in eng_articles:
        summary = summarize_article(a["title"], a.get("description"), is_english=True)
        today_articles.append({"title": a["title"], "url": a["url"], "summary": summary, "source": a["source"]["name"]})
    for a in jpn_articles:
        summary = summarize_article(a["title"], a.get("description"), is_english=False)
        today_articles.append({"title": a["title"], "url": a["url"], "summary": summary, "source": a["source"]["name"]})
    data[today] = today_articles
    save_data(data)
    generate_html(data)

if __name__ == "__main__":
    main()
