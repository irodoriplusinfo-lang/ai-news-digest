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

def translate_and_summarize(title, description):
    prompt = f"""以下のニュース記事を日本語に翻訳し、内容を3行以内で要約してください。
出力形式：
タイトル翻訳: （日本語タイトル）
要約: （3行以内の日本語要約）

タイトル: {title}
内容: {description or 'なし'}"""
    message = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}]
    )
    text = message.content[0].text
    jp_title = title
    summary = ""
    for line in text.split("\n"):
        if line.startswith("タイトル翻訳:"):
            jp_title = line.replace("タイトル翻訳:", "").strip()
        elif line.startswith("要約:"):
            summary = line.replace("要約:", "").strip()
    return jp_title, summary

def load_existing_data():
    if os.path.exists("news_data.json"):
        with open("news_data.json", "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_data(data):
    with open("news_data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def delete_old_data(data):
    cutoff = datetime.now() - timedelta(days=DAYS_TO​​​​​​​​​​​​​​​​
