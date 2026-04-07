import os
import json
import re
import requests
from datetime import datetime, timedelta, timezone
from anthropic import Anthropic

# ── 定数 ──────────────────────────────────────────────
JST = timezone(timedelta(hours=9))
TODAY = datetime.now(JST).strftime("%Y年%m月%d日")
TODAY_ISO = datetime.now(JST).strftime("%Y-%m-%d")
OUTPUT_FILE = "index.html"
DATA_FILE = "news_data.json"
KEEP_DAYS = 7

NEWS_API_KEY = os.environ["NEWS_API_KEY"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
client = Anthropic(api_key=ANTHROPIC_API_KEY)

# AIニュース専用キーワード（関係性の高い順に並べた複数クエリ）
AI_QUERIES = [
    "artificial intelligence new model release 2026",
    "OpenAI GPT Claude Gemini announcement",
    "AI research breakthrough machine learning",
    "Elon Musk xAI Grok technology",
    "AI regulation policy government",
    "generative AI startup funding",
    "robotics autonomous AI humanoid",
    "AI chip semiconductor Nvidia compute",
]

# ── NewsAPIからニュースを取得 ──────────────────────────
def fetch_articles() -> list[dict]:
    """複数クエリで検索し、重複を除いてAI記事を最大40件収集"""
    seen_urls = set()
    seen_titles = set()
    articles = []

    for query in AI_QUERIES:
        if len(articles) >= 40:
            break
        try:
            resp = requests.get(
                "https://newsapi.org/v2/everything",
                params={
                    "q": query,
                    "language": "en",
                    "sortBy": "publishedAt",
                    "pageSize": 10,
                    "from": (datetime.now(JST) - timedelta(days=2)).strftime("%Y-%m-%d"),
                    "apiKey": NEWS_API_KEY,
                },
                timeout=15,
            )
            resp.raise_for_status()
            for a in resp.json().get("articles", []):
                url = a.get("url", "")
                title = (a.get("title") or "").strip()
                if not title or not url:
                    continue
                title_key = re.sub(r"\W+", "", title.lower())[:60]
                if url in seen_urls or title_key in seen_titles:
                    continue
                seen_urls.add(url)
                seen_titles.add(title_key)
                articles.append({
                    "title": title,
                    "description": (a.get("description") or "").strip(),
                    "url": url,
                    "source": a.get("source", {}).get("name", ""),
                    "publishedAt": a.get("publishedAt", ""),
                })
        except Exception as e:
            print(f"[fetch] {query}: {e}")

    # 日本語AIニュースも追加
    try:
        resp = requests.get(
            "https://newsapi.org/v2/everything",
            params={
                "q": "AI 人工知能 OR 生成AI OR LLM OR ChatGPT OR Claude",
                "language": "ja",
                "sortBy": "publishedAt",
                "pageSize": 10,
                "from": (datetime.now(JST) - timedelta(days=2)).strftime("%Y-%m-%d"),
                "apiKey": NEWS_API_KEY,
            },
            timeout=15,
        )
        resp.raise_for_status()
        for a in resp.json().get("articles", []):
            url = a.get("url", "")
            title = (a.get("title") or "").strip()
            if not title or not url:
                continue
            title_key = re.sub(r"\W+", "", title.lower())[:60]
            if url in seen_urls or title_key in seen_titles:
                continue
            seen_urls.add(url)
            seen_titles.add(title_key)
            articles.append({
                "title": title,
                "description": (a.get("description") or "").strip(),
                "url": url,
                "source": a.get("source", {}).get("name", ""),
                "publishedAt": a.get("publishedAt", ""),
                "lang": "ja",
            })
    except Exception as e:
        print(f"[fetch-ja] {e}")

    return articles

# ── Claudeで翻訳・フィルタリング ────────────────────────
def process_with_claude(articles: list[dict]) -> list[dict]:
    """
    Claudeに記事リストを渡し、
    1. AIと無関係な記事を除外
    2. タイトル・本文をできるだけ全文日本語翻訳
    して20件を返す
    """
    articles_text = json.dumps(
        [{"id": i, "title": a["title"], "description": a["description"]}
         for i, a in enumerate(articles)],
        ensure_ascii=False,
        indent=2,
    )

    prompt = f"""あなたはAI専門の翻訳者です。
以下の記事リストから「AIに直接関係するニュース」だけを厳選し、最大20件を選んでください。

【選ぶ基準（これらに該当する記事を優先）】
- AI・LLM・生成AIの新機能・新モデルのリリース発表
- OpenAI / Anthropic / Google / Meta / xAI / Mistral などAI企業の動向
- AIチップ・データセンター・コンピューティングインフラ
- AI規制・政策・倫理・安全性に関する議論
- AIスタートアップの資金調達・買収・合併
- AI研究者・専門家・著名人のAIに関する発言や討論
- ロボティクス・自動運転などAI応用技術

【除外する記事】
- AIと直接無関係なニュース（食品、スポーツ、一般政治、エンタメ等）
- AIを軽く言及しているだけで本質がAI以外の記事

【翻訳の方針】
- タイトルと本文をできるだけ忠実に日本語へ全文翻訳してください
- 意訳や要約はせず、原文の内容をそのまま日本語にしてください
- 日本語の記事はそのまま使用してください

【出力形式】
選んだ記事を以下のJSON配列で返してください（前後の説明文は不要、JSONのみ）:
[
  {{
    "id": 元のid番号,
    "title_ja": "タイトルの日本語翻訳",
    "body_ja": "本文（description）の日本語全文翻訳",
    "category": "モデル発表|企業動向|研究|規制・政策|資金・M&A|人物発言|応用技術|その他" のうち1つ
  }},
  ...
]

記事リスト:
{articles_text}
"""

    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=8000,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()
    match = re.search(r"\[.*\]", raw, re.DOTALL)
    if not match:
        print("[claude] JSON parse failed, raw:", raw[:200])
        return []

    processed = json.loads(match.group())
    result = []
    for item in processed:
        orig = articles[item["id"]]
        result.append({
            "title": item.get("title_ja", orig["title"]),
            "body": item.get("body_ja", ""),
            "category": item.get("category", "その他"),
            "url": orig["url"],
            "source": orig["source"],
            "publishedAt": orig["publishedAt"],
        })
    return result[:20]

# ── カテゴリバッジの色設定 ────────────────────────────
CATEGORY_STYLE = {
    "モデル発表":   ("🚀", "#6366f1"),
    "企業動向":     ("🏢", "#0ea5e9"),
    "研究":         ("🔬", "#10b981"),
    "規制・政策":   ("⚖️",  "#f59e0b"),
    "資金・M&A":    ("💰", "#ec4899"),
    "人物発言":     ("💬", "#8b5cf6"),
    "応用技術":     ("🤖", "#14b8a6"),
    "その他":       ("📰", "#6b7280"),
}

# ── HTML生成 ─────────────────────────────────────────
def build_html(all_days: dict) -> str:
    days_html = ""
    for date_str in sorted(all_days.keys(), reverse=True):
        articles = all_days[date_str]
        cards = ""
        for a in articles:
            cat = a.get("category", "その他")
            icon, color = CATEGORY_STYLE.get(cat, ("📰", "#6b7280"))
            source = a.get("source", "")
            body = a.get("body", "")
            url = a.get("url", "#")
            title = a.get("title", "")
            cards += f"""
        <article class="card">
          <div class="card-meta">
            <span class="badge" style="background:{color}20;color:{color};border-color:{color}40">{icon} {cat}</span>
            <span class="source">{source}</span>
          </div>
          <h2 class="card-title">
            <a href="{url}" target="_blank" rel="noopener">{title}</a>
          </h2>
          <p class="card-body">{body}</p>
          <a href="{url}" class="read-more" target="_blank" rel="noopener">記事を読む →</a>
        </article>"""

        days_html += f"""
    <section class="day-section">
      <div class="day-header">
        <h2 class="day-title">📅 {date_str}</h2>
        <span class="day-count">{len(articles)}件</span>
      </div>
      <div class="cards-grid">{cards}
      </div>
    </section>"""

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>🤖 AIニュースダイジェスト</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700&family=Space+Mono:wght@400;700&display=swap" rel="stylesheet">
  <style>
    :root {{
      --bg: #0d0f17;
      --surface: #151824;
      --surface2: #1c2133;
      --border: #ffffff10;
      --text: #e2e8f0;
      --text-muted: #8892a4;
      --accent: #6366f1;
      --accent2: #0ea5e9;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: 'Noto Sans JP', sans-serif;
      background: var(--bg);
      color: var(--text);
      min-height: 100vh;
      line-height: 1.7;
    }}
    header {{
      background: linear-gradient(135deg, #0d0f17 0%, #151824 50%, #0d1428 100%);
      border-bottom: 1px solid var(--border);
      padding: 2rem 1.5rem 1.5rem;
      text-align: center;
      position: sticky;
      top: 0;
      z-index: 100;
      backdrop-filter: blur(20px);
    }}
    .header-title {{
      font-family: 'Space Mono', monospace;
      font-size: clamp(1.2rem, 4vw, 1.8rem);
      font-weight: 700;
      background: linear-gradient(90deg, #6366f1, #0ea5e9, #10b981);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      background-clip: text;
      letter-spacing: -0.02em;
    }}
    .header-sub {{
      font-family: 'Space Mono', monospace;
      font-size: 0.7rem;
      color: var(--text-muted);
      margin-top: 0.4rem;
      letter-spacing: 0.1em;
    }}
    main {{
      max-width: 860px;
      margin: 0 auto;
      padding: 2rem 1rem 4rem;
    }}
    .day-section {{ margin-bottom: 3rem; }}
    .day-header {{
      display: flex;
      align-items: center;
      gap: 0.75rem;
      margin-bottom: 1.25rem;
      padding-bottom: 0.75rem;
      border-bottom: 1px solid var(--border);
    }}
    .day-title {{
      font-family: 'Space Mono', monospace;
      font-size: 0.95rem;
      font-weight: 700;
      color: var(--accent2);
      letter-spacing: 0.05em;
    }}
    .day-count {{
      font-family: 'Space Mono', monospace;
      font-size: 0.7rem;
      color: var(--text-muted);
      background: var(--surface2);
      padding: 0.15rem 0.5rem;
      border-radius: 9999px;
      border: 1px solid var(--border);
    }}
    .cards-grid {{ display: grid; gap: 1rem; }}
    .card {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 1.25rem 1.5rem;
      transition: border-color 0.2s, transform 0.2s, box-shadow 0.2s;
    }}
    .card:hover {{
      border-color: #6366f130;
      transform: translateY(-2px);
      box-shadow: 0 8px 32px #00000040;
    }}
    .card-meta {{
      display: flex;
      align-items: center;
      gap: 0.6rem;
      margin-bottom: 0.75rem;
      flex-wrap: wrap;
    }}
    .badge {{
      font-size: 0.68rem;
      font-weight: 700;
      padding: 0.2rem 0.6rem;
      border-radius: 9999px;
      border: 1px solid;
      letter-spacing: 0.03em;
    }}
    .source {{
      font-family: 'Space Mono', monospace;
      font-size: 0.65rem;
      color: var(--text-muted);
    }}
    .card-title {{
      font-size: clamp(0.95rem, 2.5vw, 1.05rem);
      font-weight: 700;
      line-height: 1.5;
      margin-bottom: 0.6rem;
    }}
    .card-title a {{
      color: var(--text);
      text-decoration: none;
      transition: color 0.2s;
    }}
    .card-title a:hover {{ color: var(--accent2); }}
    .card-body {{
      font-size: 0.88rem;
      color: #a0aab8;
      line-height: 1.75;
      margin-bottom: 0.75rem;
    }}
    .read-more {{
      font-family: 'Space Mono', monospace;
      font-size: 0.7rem;
      color: var(--accent);
      text-decoration: none;
      letter-spacing: 0.05em;
      transition: color 0.2s;
    }}
    .read-more:hover {{ color: var(--accent2); }}
    footer {{
      text-align: center;
      padding: 2rem;
      font-family: 'Space Mono', monospace;
      font-size: 0.65rem;
      color: var(--text-muted);
      letter-spacing: 0.08em;
      border-top: 1px solid var(--border);
    }}
    @media (max-width: 480px) {{
      header {{ padding: 1.25rem 1rem 1rem; }}
      .card {{ padding: 1rem; }}
    }}
  </style>
</head>
<body>
  <header>
    <div class="header-title">🤖 AI NEWS DIGEST</div>
    <div class="header-sub">LAST UPDATED: {TODAY} — POWERED BY CLAUDE</div>
  </header>
  <main>{days_html}
  </main>
  <footer>
    © {datetime.now(JST).year} AI NEWS DIGEST — AUTOMATED BY CLAUDE &amp; GITHUB ACTIONS
  </footer>
</body>
</html>"""

# ── データ管理（7日分保持） ───────────────────────────
def load_data() -> dict:
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_data(data: dict):
    cutoff = (datetime.now(JST) - timedelta(days=KEEP_DAYS)).strftime("%Y-%m-%d")
    pruned = {k: v for k, v in data.items() if k >= cutoff}
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(pruned, f, ensure_ascii=False, indent=2)
    return pruned

# ── メイン ───────────────────────────────────────────
def main():
    print(f"[{TODAY}] AIニュース収集開始")

    raw_articles = fetch_articles()
    print(f"  収集: {len(raw_articles)}件")

    processed = process_with_claude(raw_articles)
    print(f"  AI関連に絞り込み: {len(processed)}件")

    display_date = TODAY

    data = load_data()
    data[TODAY_ISO] = {"display": display_date, "articles": processed}
    data = save_data(data)

    display_data = {v["display"]: v["articles"] for v in data.values()}
    html = build_html(display_data)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"  HTML生成完了: {OUTPUT_FILE}")
    print(f"  保持日数: {len(data)}日分")

if __name__ == "__main__":
    main()

