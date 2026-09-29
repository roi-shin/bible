"""
NET Bible スクレイピング + 翻訳 + 静的HTML生成スクリプト

1. labs.bible.org/api から本文をJSON取得
2. netbible.org/resource/netNote/ から注を個別取得
3. googletrans で英→日翻訳
4. 静的HTMLを docs/ フォルダに出力 (GitHub Pages用)
"""

import json
import os
import re
import sys
import time
import requests
import subprocess
from bs4 import BeautifulSoup

# --- 設定 ---
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "docs")
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

# 聖書の書名リスト (英語名, 章数)
BOOKS = {
    "Genesis": 50, "Exodus": 40, "Leviticus": 27, "Numbers": 36,
    "Deuteronomy": 34, "Joshua": 24, "Judges": 21, "Ruth": 4,
    "1 Samuel": 31, "2 Samuel": 24, "1 Kings": 22, "2 Kings": 25,
    "1 Chronicles": 29, "2 Chronicles": 36, "Ezra": 10, "Nehemiah": 13,
    "Esther": 10, "Job": 42, "Psalms": 150, "Proverbs": 31,
    "Ecclesiastes": 12, "Song of Solomon": 8, "Isaiah": 66, "Jeremiah": 52,
    "Lamentations": 5, "Ezekiel": 48, "Daniel": 12, "Hosea": 14,
    "Joel": 3, "Amos": 9, "Obadiah": 1, "Jonah": 4,
    "Micah": 7, "Nahum": 3, "Habakkuk": 3, "Zephaniah": 3,
    "Haggai": 2, "Zechariah": 14, "Malachi": 4,
    "Matthew": 28, "Mark": 16, "Luke": 24, "John": 21,
    "Acts": 28, "Romans": 16, "1 Corinthians": 16, "2 Corinthians": 13,
    "Galatians": 6, "Ephesians": 6, "Philippians": 4, "Colossians": 4,
    "1 Thessalonians": 5, "2 Thessalonians": 3, "1 Timothy": 6,
    "2 Timothy": 4, "Titus": 3, "Philemon": 1, "Hebrews": 13,
    "James": 5, "1 Peter": 5, "2 Peter": 3, "1 John": 5,
    "2 John": 1, "3 John": 1, "Jude": 1, "Revelation": 22,
}


def fetch_chapter_text(book: str, chapter: int) -> list[dict]:
    """labs.bible.org/api から章の本文をJSON取得"""
    url = "https://labs.bible.org/api/"
    params = {
        "passage": f"{book} {chapter}",
        "type": "json",
    }
    print(f"  本文取得中: {book} {chapter}")
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def fetch_note(book: str, chapter: int, verse: int, pos: int) -> str | None:
    """netbible.org から個別のNET Noteを取得"""
    url = f"https://netbible.org/resource/netNote/{book} {chapter}:{verse}/{pos}"
    try:
        resp = requests.get(url, timeout=15)
        if resp.status_code == 200 and resp.text.strip():
            return resp.text.strip()
    except requests.RequestException:
        pass
    return None


def fetch_all_notes_for_chapter(book: str, chapter: int, max_notes_per_verse: int = 20) -> dict:
    """
    章内の全節に対して注を取得する。
    戻り値: {verse_num: [(pos, note_text), ...], ...}
    """
    print(f"  注取得中: {book} {chapter}")
    notes = {}

    # まず本文から節数を把握
    text_data = fetch_chapter_text(book, chapter)
    verse_nums = sorted(set(int(v["verse"]) for v in text_data))

    for verse in verse_nums:
        verse_notes = []
        for pos in range(1, max_notes_per_verse + 1):
            note = fetch_note(book, chapter, verse, pos)
            if note is None:
                break  # このverseにはこれ以上の注がない
            verse_notes.append((pos, note))
            time.sleep(0.3)  # レート制限回避

        if verse_notes:
            notes[verse] = verse_notes

    return notes, text_data


def clean_note_html(note_text: str) -> str:
    """注のHTMLタグを除去してプレーンテキストに"""
    soup = BeautifulSoup(note_text, 'html.parser')
    
    # notetype（tn, sn, tcなど）を分かりやすい日本語ラベルに変換
    for span in soup.find_all('span', class_='notetype'):
        text = span.get_text().strip()
        if text == 'tn':
            span.string = "[翻訳注] "
        elif text == 'sn':
            span.string = "[解説] "
        elif text == 'tc':
            span.string = "[写本注] "
        elif text == 'map':
            span.string = "[地図] "
            
    return soup.get_text().strip()

def translate_with_agy(raw_data: dict) -> dict:
    """agy CLIを使ってJSON全体の英語を一括翻訳する"""
    # 送信用のデータ構造を整理
    payload = {
        "verses": [{"verse": v["verse"], "text": BeautifulSoup(v["text"], 'html.parser').get_text()} for v in raw_data["text_data"]],
        "notes": {}
    }
    for vn, notes_list in raw_data["notes"].items():
        payload["notes"][vn] = [{"pos": pos, "text": clean_note_html(text)} for pos, text in notes_list]

    json_str = json.dumps(payload, ensure_ascii=False)
    
    # テンポラリファイルに保存
    temp_in = temp_in_path if 'temp_in_path' in globals() else os.path.join(DATA_DIR, "temp_in.json")
    with open(temp_in, "w", encoding="utf-8") as f:
        f.write(json_str)

    prompt = (
        f"Read the file '{temp_in}'. It contains a JSON object with 'verses' and 'notes'. "
        f"Translate all English text in the 'verses' and 'notes' fields to natural Japanese. "
        f"CRITICAL INSTRUCTION: The 'notes' field contains highly detailed translator's notes (tn), study notes (sn), and text-critical notes (tc) that justify the specific English translation choices. "
        f"When translating the 'verses', you MUST carefully cross-reference and incorporate the nuances and justifications provided in the corresponding notes for that verse. "
        f"Ensure that the Japanese translation of the verses accurately reflects the theological and grammatical insights detailed in the notes, maintaining strict consistency between the verse text and its explanatory notes. "
        f"Return the output in exactly the same JSON structure, replacing the English text with Japanese in the 'ja' fields for verses, and adding 'ja' fields for notes. "
        f"Output ONLY raw JSON, do not use markdown code blocks."
    )

    # agy コマンドの構築
    cmd = [
        "agy", "-p",
        prompt,
        "--model", "gemini-3.7-flash-medium",
        "--output-format", "json",
        "--dangerously-skip-permissions"
    ]
    
    print("    agy CLI を呼び出して一括翻訳中...")
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    
    if result.returncode != 0:
        print(f"agyコマンドエラー:\n{result.stderr}")
        raise Exception("agy CLI translation failed")
        
    try:
        # agyの--output-format json は {"response": "..."} でラップされるので、
        # まず外側のJSONをパースし、その中のresponse文字列をさらにパースする
        outer_json_text = result.stdout.strip().split("\n")[-1] # エラーメッセージ等を無視して最後の行を取得
        outer_json = json.loads(outer_json_text)
        response_text = outer_json.get("response", "").strip()
        
        # Markdownのコードブロック記法 (```json ... ```) を除去
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
            
        translated = json.loads(response_text.strip())
        return translated
    except Exception as e:
        print(f"    agyが不正なJSONを返しました。エラー: {e}")
        print("    生の出力:", result.stdout)
        raise


def process_chapter(book: str, chapter: int) -> dict:
    """1章分のデータを取得・翻訳"""
    book_dir_name = book.replace(" ", "_")
    chap_dir = os.path.join(DATA_DIR, book_dir_name, str(chapter))
    os.makedirs(chap_dir, exist_ok=True)
    
    data_file = os.path.join(chap_dir, "data.json")
    raw_file = os.path.join(chap_dir, "raw.json")

    # キャッシュがあればロード
    if os.path.exists(data_file):
        print(f"  翻訳済みキャッシュ使用: {data_file}")
        with open(data_file, "r", encoding="utf-8") as f:
            return json.load(f)

    # Rawデータのキャッシュがあればロード、なければスクレイピング
    if os.path.exists(raw_file):
        print(f"  Rawデータキャッシュ使用: {raw_file}")
        with open(raw_file, "r", encoding="utf-8") as f:
            raw_data = json.load(f)
            notes = raw_data["notes"]
            text_data = raw_data["text_data"]
    else:
        notes, text_data = fetch_all_notes_for_chapter(book, chapter)
        with open(raw_file, "w", encoding="utf-8") as f:
            json.dump({"notes": notes, "text_data": text_data}, f, ensure_ascii=False, indent=2)

    # テンポラリファイル用にパスを上書き (translate_with_agy 内で使用するため)
    global temp_in_path
    temp_in_path = os.path.join(chap_dir, "temp_in.json")

    # 翻訳
    print(f"  翻訳中 (agy使用): {book} {chapter}")
    translated_data = translate_with_agy(raw_data) if "raw_data" in locals() else translate_with_agy({"notes": notes, "text_data": text_data})

    result = {
        "book": book,
        "chapter": chapter,
        "verses": [],
        "notes": {},
    }

    # 翻訳結果の構築
    for v in translated_data.get("verses", []):
        verse_num = int(v["verse"])
        # フォールバックで英語を残す
        ja_text = v.get("ja", v.get("text", ""))
        en_text = v.get("text", "")
        
        result["verses"].append({
            "verse": verse_num,
            "en": en_text,
            "ja": ja_text,
        })

    for verse_num_str, verse_notes in translated_data.get("notes", {}).items():
        translated_notes = []
        for n in verse_notes:
            ja_note = n.get("ja", n.get("text", ""))
            en_note = n.get("text", "")
            translated_notes.append({
                "pos": n["pos"],
                "en": en_note,
                "ja": ja_note,
            })
        result["notes"][str(verse_num_str)] = translated_notes

    # キャッシュ保存
    with open(data_file, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"  保存完了: {data_file}")
    
    return result

def export_markdown(data: dict):
    """ローカルAI用に、翻訳データを英語用と日本語用に分けてMarkdown出力する"""
    book = data["book"]
    chapter = data["chapter"]
    
    book_dir_name = book.replace(" ", "_")
    chap_dir = os.path.join(DATA_DIR, book_dir_name, str(chapter))
    os.makedirs(chap_dir, exist_ok=True)
    
    en_file = os.path.join(chap_dir, "en.md")
    ja_file = os.path.join(chap_dir, "ja.md")
    
    lines_en = [f"# {book} {chapter} (English)\n"]
    lines_ja = [f"# {book} {chapter} (Japanese)\n"]
    
    # 本文
    lines_en.append("## Text\n")
    lines_ja.append("## 本文\n")
    for v in data["verses"]:
        vn = v["verse"]
        lines_en.append(f"**{vn}** {v['en']}\n")
        lines_ja.append(f"**{vn}** {v['ja']}\n")
        
    # 注釈
    if data["notes"]:
        lines_en.append("## Notes\n")
        lines_ja.append("## 注釈\n")
        for vn_str, notes in data["notes"].items():
            for n in notes:
                pos = n["pos"]
                lines_en.append(f"### Verse {vn_str} - Note {pos}")
                lines_en.append(f"{n['en']}\n")
                lines_ja.append(f"### 節 {vn_str} - 注 {pos}")
                lines_ja.append(f"{n['ja']}\n")
                
    with open(en_file, "w", encoding="utf-8") as f:
        f.write("\n".join(lines_en))
    with open(ja_file, "w", encoding="utf-8") as f:
        f.write("\n".join(lines_ja))
        
    print(f"  Markdown出力完了: {en_file}, {ja_file}")


def generate_chapter_html(data: dict) -> str:
    """1章分のHTMLを生成"""
    book = data["book"]
    chapter = data["chapter"]

    verses_html = ""
    for v in data["verses"]:
        vn = v["verse"]
        note_markers = ""
        if str(vn) in data["notes"]:
            for n in data["notes"][str(vn)]:
                note_markers += f'<sup class="note-ref" data-verse="{vn}" data-pos="{n["pos"]}">{n["pos"]}</sup>'

        verses_html += f"""
        <div class="verse" id="v{vn}">
          <div class="verse-num">{vn}</div>
          <div class="verse-content">
            <div class="verse-ja">{v["ja"]}</div>
            <div class="verse-en">{v["en"]}</div>
            <div class="verse-markers">{note_markers}</div>
          </div>
        </div>"""

    notes_html = ""
    for verse_num_str, verse_notes in sorted(data["notes"].items(), key=lambda x: int(x[0])):
        for n in verse_notes:
            notes_html += f"""
            <div class="note" id="note-{verse_num_str}-{n['pos']}">
              <div class="note-header">{verse_num_str}:{n['pos']}</div>
              <div class="note-ja">{n['ja']}</div>
              <div class="note-en">{n['en']}</div>
            </div>"""

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{book} {chapter} - NET Bible 日本語対訳</title>
  <link rel="stylesheet" href="style.css">
</head>
<body>
  <header>
    <nav class="top-nav">
      <a href="index.html" class="nav-home">📖 NET Bible 対訳</a>
      <span class="nav-title">{book} {chapter}</span>
      <div class="nav-controls">
        <button id="toggleLang" class="nav-btn" title="言語切替">🌐</button>
        <button id="toggleNotes" class="nav-btn" title="注の表示切替">📝</button>
        <button id="toggleLayout" class="nav-btn" title="レイアウト切替">⇆</button>
      </div>
    </nav>
  </header>

  <main class="reader">
    <section class="text-panel" id="textPanel">
      <h1>{book} {chapter}</h1>
      <div class="verses">
        {verses_html}
      </div>
    </section>

    <aside class="notes-panel" id="notesPanel">
      <h2>NET Notes (翻訳者注)</h2>
      <div class="notes-content">
        {notes_html}
      </div>
    </aside>
  </main>

  <script src="app.js"></script>
</body>
</html>"""


def generate_css() -> str:
    """共通CSSを生成"""
    return """@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@300;400;500;700&family=Noto+Serif+JP:wght@400;700&family=Inter:wght@300;400;500;600&display=swap');

:root {
  --bg-primary: #0f0f13;
  --bg-secondary: #1a1a24;
  --bg-card: #22222e;
  --bg-card-hover: #2a2a38;
  --text-primary: #e8e6e3;
  --text-secondary: #9a9a9a;
  --text-muted: #6a6a7a;
  --accent-gold: #c9a84c;
  --accent-gold-dim: #8a7030;
  --accent-blue: #4a7fb5;
  --accent-red: #b54a4a;
  --border-color: #2a2a3a;
  --note-bg: #1e1e28;
  --note-border: #3a3a4a;
  --verse-ja-color: #e8e6e3;
  --verse-en-color: #8a8a9a;
  --shadow-sm: 0 1px 3px rgba(0,0,0,0.3);
  --shadow-md: 0 4px 12px rgba(0,0,0,0.4);
  --shadow-lg: 0 8px 24px rgba(0,0,0,0.5);
  --radius-sm: 6px;
  --radius-md: 10px;
  --radius-lg: 16px;
}

* { margin: 0; padding: 0; box-sizing: border-box; }

html {
  scroll-behavior: smooth;
  font-size: 16px;
}

body {
  font-family: 'Noto Sans JP', 'Inter', sans-serif;
  background: var(--bg-primary);
  color: var(--text-primary);
  line-height: 1.8;
  min-height: 100vh;
}

/* --- Header --- */
header {
  position: sticky;
  top: 0;
  z-index: 100;
  background: rgba(15, 15, 19, 0.85);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border-bottom: 1px solid var(--border-color);
}

.top-nav {
  max-width: 1600px;
  margin: 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.75rem 1.5rem;
}

.nav-home {
  color: var(--accent-gold);
  text-decoration: none;
  font-weight: 600;
  font-size: 1.1rem;
  letter-spacing: 0.02em;
  transition: opacity 0.2s;
}

.nav-home:hover { opacity: 0.8; }

.nav-title {
  font-family: 'Noto Serif JP', serif;
  font-size: 1.2rem;
  color: var(--text-primary);
  font-weight: 400;
}

.nav-controls {
  display: flex;
  gap: 0.5rem;
}

.nav-btn {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  color: var(--text-secondary);
  padding: 0.4rem 0.7rem;
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-size: 1rem;
  transition: all 0.2s;
}

.nav-btn:hover {
  background: var(--bg-card-hover);
  color: var(--text-primary);
}

.nav-btn.active {
  background: var(--accent-gold-dim);
  border-color: var(--accent-gold);
  color: var(--accent-gold);
}

/* --- Main Layout --- */
.reader {
  max-width: 1600px;
  margin: 0 auto;
  display: grid;
  grid-template-columns: 1fr 380px;
  gap: 0;
  min-height: calc(100vh - 60px);
}

.reader.notes-hidden {
  grid-template-columns: 1fr;
}

.reader.notes-hidden .notes-panel {
  display: none;
}

.reader.layout-reversed {
  grid-template-columns: 380px 1fr;
}

.reader.layout-reversed .notes-panel {
  order: -1;
}

/* --- Text Panel --- */
.text-panel {
  padding: 2rem 2.5rem;
}

.text-panel h1 {
  font-family: 'Noto Serif JP', serif;
  font-size: 1.8rem;
  font-weight: 700;
  color: var(--accent-gold);
  margin-bottom: 2rem;
  padding-bottom: 1rem;
  border-bottom: 1px solid var(--border-color);
}

/* --- Verse --- */
.verse {
  display: flex;
  gap: 1rem;
  padding: 0.8rem 0;
  border-bottom: 1px solid rgba(42, 42, 58, 0.5);
  transition: background 0.2s;
}

.verse:hover {
  background: rgba(42, 42, 58, 0.3);
  border-radius: var(--radius-sm);
}

.verse-num {
  font-family: 'Inter', sans-serif;
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--accent-gold);
  min-width: 2rem;
  text-align: right;
  padding-top: 0.3rem;
  user-select: none;
}

.verse-content {
  flex: 1;
}

.verse-ja {
  font-family: 'Noto Serif JP', serif;
  font-size: 1.05rem;
  line-height: 1.9;
  color: var(--verse-ja-color);
  margin-bottom: 0.4rem;
}

.verse-en {
  font-family: 'Inter', sans-serif;
  font-size: 0.85rem;
  line-height: 1.7;
  color: var(--verse-en-color);
}

.verse-markers {
  margin-top: 0.3rem;
  display: flex;
  flex-wrap: wrap;
  gap: 0.3rem;
}

.note-ref {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.2em;
  height: 1.2em;
  font-size: 0.65rem;
  background: var(--accent-gold-dim);
  color: var(--accent-gold);
  border-radius: 50%;
  margin-left: 2px;
  cursor: pointer;
  vertical-align: super;
  transition: all 0.2s;
  font-weight: 600;
}

.note-ref:hover {
  background: var(--accent-gold);
  color: var(--bg-primary);
  transform: scale(1.2);
}

/* --- Notes Panel --- */
.notes-panel {
  background: var(--bg-secondary);
  border-left: 1px solid var(--border-color);
  padding: 1.5rem;
  overflow-y: auto;
  max-height: calc(100vh - 60px);
  position: sticky;
  top: 60px;
}

.notes-panel h2 {
  font-family: 'Noto Serif JP', serif;
  font-size: 1rem;
  color: var(--accent-gold);
  margin-bottom: 1.5rem;
  padding-bottom: 0.75rem;
  border-bottom: 1px solid var(--border-color);
  font-weight: 500;
}

.note {
  background: var(--note-bg);
  border: 1px solid var(--note-border);
  border-radius: var(--radius-md);
  padding: 1rem;
  margin-bottom: 0.75rem;
  transition: all 0.2s;
}

.note:hover {
  border-color: var(--accent-gold-dim);
  box-shadow: var(--shadow-sm);
}

.note.highlight {
  border-color: var(--accent-gold);
  box-shadow: 0 0 0 1px var(--accent-gold-dim);
}

.note-header {
  font-family: 'Inter', sans-serif;
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--accent-gold);
  margin-bottom: 0.5rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.note-header::before {
  content: '§';
  opacity: 0.5;
}

.note-ja {
  font-size: 0.9rem;
  line-height: 1.7;
  color: var(--text-primary);
  margin-bottom: 0.5rem;
}

.note-en {
  font-family: 'Inter', sans-serif;
  font-size: 0.78rem;
  line-height: 1.6;
  color: var(--text-muted);
}

/* --- Index Page --- */
.index-container {
  max-width: 1000px;
  margin: 0 auto;
  padding: 3rem 2rem;
}

.index-container h1 {
  font-family: 'Noto Serif JP', serif;
  font-size: 2.2rem;
  color: var(--accent-gold);
  text-align: center;
  margin-bottom: 0.5rem;
}

.index-subtitle {
  text-align: center;
  color: var(--text-secondary);
  margin-bottom: 3rem;
  font-size: 0.95rem;
}

.book-section {
  margin-bottom: 2.5rem;
}

.book-section h2 {
  font-family: 'Noto Serif JP', serif;
  font-size: 1.3rem;
  color: var(--accent-gold);
  margin-bottom: 1rem;
  padding-bottom: 0.5rem;
  border-bottom: 1px solid var(--border-color);
}

.book-section h3 {
  font-size: 1rem;
  color: var(--text-secondary);
  margin: 1rem 0 0.5rem;
  font-weight: 500;
}

.chapter-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
}

.chapter-link {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 2.5rem;
  height: 2.5rem;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  color: var(--text-secondary);
  text-decoration: none;
  font-size: 0.85rem;
  font-weight: 500;
  transition: all 0.2s;
}

.chapter-link:hover {
  background: var(--accent-gold-dim);
  border-color: var(--accent-gold);
  color: var(--accent-gold);
  transform: translateY(-1px);
  box-shadow: var(--shadow-sm);
}

.chapter-link.available {
  border-color: var(--accent-gold-dim);
  color: var(--accent-gold);
}

.chapter-link.unavailable {
  opacity: 0.3;
  pointer-events: none;
}

/* --- Responsive --- */
@media (max-width: 1024px) {
  .reader {
    grid-template-columns: 1fr;
  }

  .notes-panel {
    border-left: none;
    border-top: 1px solid var(--border-color);
    position: static;
    max-height: none;
  }

  .text-panel {
    padding: 1.5rem;
  }
}

@media (max-width: 600px) {
  .text-panel {
    padding: 1rem;
  }

  .text-panel h1 {
    font-size: 1.4rem;
  }

  .verse {
    flex-direction: column;
    gap: 0.3rem;
  }

  .verse-num {
    text-align: left;
  }

  .verse-ja { font-size: 0.95rem; }
  .verse-en { font-size: 0.8rem; }
}

/* --- Scrollbar --- */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: var(--bg-primary); }
::-webkit-scrollbar-thumb {
  background: var(--border-color);
  border-radius: 3px;
}
::-webkit-scrollbar-thumb:hover { background: var(--text-muted); }

/* --- Language Toggle --- */
body.lang-ja-only .verse-en, body.lang-ja-only .note-en { display: none; }
body.lang-en-only .verse-ja, body.lang-en-only .note-ja { display: none; }
"""


def generate_js() -> str:
    """共通JavaScriptを生成"""
    return """// 注の参照クリック → 右パネルでハイライト
document.querySelectorAll('.note-ref').forEach(ref => {
  ref.addEventListener('click', () => {
    const verse = ref.dataset.verse;
    const pos = ref.dataset.pos;
    const noteId = `note-${verse}-${pos}`;
    const noteEl = document.getElementById(noteId);

    if (noteEl) {
      // 全ハイライト解除
      document.querySelectorAll('.note.highlight').forEach(n => n.classList.remove('highlight'));
      // ハイライト
      noteEl.classList.add('highlight');
      noteEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  });
});

// 注パネル表示切替
const toggleNotesBtn = document.getElementById('toggleNotes');
if (toggleNotesBtn) {
  toggleNotesBtn.addEventListener('click', () => {
    document.querySelector('.reader').classList.toggle('notes-hidden');
    toggleNotesBtn.classList.toggle('active');
  });
}

// レイアウト切替
const toggleLayoutBtn = document.getElementById('toggleLayout');
if (toggleLayoutBtn) {
  toggleLayoutBtn.addEventListener('click', () => {
    document.querySelector('.reader').classList.toggle('layout-reversed');
    toggleLayoutBtn.classList.toggle('active');
  });
}

// 言語切替
const toggleLangBtn = document.getElementById('toggleLang');
if (toggleLangBtn) {
  const langs = ['both', 'ja-only', 'en-only'];
  let currentLangIdx = 0;
  toggleLangBtn.addEventListener('click', () => {
    document.body.classList.remove('lang-' + langs[currentLangIdx]);
    currentLangIdx = (currentLangIdx + 1) % langs.length;
    if (langs[currentLangIdx] !== 'both') {
      document.body.classList.add('lang-' + langs[currentLangIdx]);
    }
    toggleLangBtn.classList.toggle('active', currentLangIdx !== 0);
  });
}
"""


def generate_index_html(available_chapters: dict) -> str:
    """目次ページを生成"""
    ot_books = list(BOOKS.keys())[:39]
    nt_books = list(BOOKS.keys())[39:]

    def make_book_section(book_name, total_chapters):
        links = ""
        for ch in range(1, total_chapters + 1):
            fname = f"{book_name.replace(' ', '_')}_{ch}.html"
            is_available = book_name in available_chapters and ch in available_chapters[book_name]
            cls = "chapter-link available" if is_available else "chapter-link unavailable"
            href = fname if is_available else "#"
            links += f'<a href="{href}" class="{cls}">{ch}</a>\n'
        return f"""<h3>{book_name}</h3><div class="chapter-grid">{links}</div>"""

    ot_html = "\n".join(make_book_section(b, BOOKS[b]) for b in ot_books)
    nt_html = "\n".join(make_book_section(b, BOOKS[b]) for b in nt_books)

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>NET Bible 日本語対訳</title>
  <link rel="stylesheet" href="style.css">
</head>
<body>
  <header>
    <nav class="top-nav">
      <a href="index.html" class="nav-home">📖 NET Bible 対訳</a>
      <span class="nav-title">目次</span>
    </nav>
  </header>

  <div class="index-container">
    <h1>NET Bible 日本語対訳</h1>
    <p class="index-subtitle">NET Bible (New English Translation) の本文と翻訳者注を日本語翻訳で閲覧</p>

    <div class="book-section">
      <h2>旧約聖書 (Old Testament)</h2>
      {ot_html}
    </div>

    <div class="book-section">
      <h2>新約聖書 (New Testament)</h2>
      {nt_html}
    </div>
  </div>
</body>
</html>"""


def main():
    import sys

    # コマンドライン引数: python scrape_and_translate.py Genesis 1
    if len(sys.argv) >= 3:
        book = sys.argv[1]
        chapter = int(sys.argv[2])
        books_to_process = [(book, chapter)]
    elif len(sys.argv) >= 2:
        book = sys.argv[1]
        books_to_process = [(book, ch) for ch in range(1, BOOKS.get(book, 1) + 1)]
    else:
        # デフォルト: Genesis 1
        books_to_process = [("Genesis", 1)]

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(DATA_DIR, exist_ok=True)

    # CSS, JS生成
    with open(os.path.join(OUTPUT_DIR, "style.css"), "w", encoding="utf-8") as f:
        f.write(generate_css())
    with open(os.path.join(OUTPUT_DIR, "app.js"), "w", encoding="utf-8") as f:
        f.write(generate_js())

    # 処理
    available_chapters = {}
    for book, chapter in books_to_process:
        print(f"\n=== {book} {chapter} ===")
        try:
            data = process_chapter(book, chapter)
            export_markdown(data)
            html = generate_chapter_html(data)
            fname = f"{book.replace(' ', '_')}_{chapter}.html"
            with open(os.path.join(OUTPUT_DIR, fname), "w", encoding="utf-8") as f:
                f.write(html)
            print(f"  HTML出力: {fname}")

            if book not in available_chapters:
                available_chapters[book] = set()
            available_chapters[book].add(chapter)
        except Exception as e:
            print(f"  エラー: {e}")
            import traceback
            traceback.print_exc()

    # 既存のデータからも available_chapters を構築
    if os.path.exists(DATA_DIR):
        for f in os.listdir(DATA_DIR):
            if f.endswith(".json"):
                parts = f.replace(".json", "").rsplit("_", 1)
                if len(parts) == 2:
                    b = parts[0].replace("_", " ")
                    try:
                        ch = int(parts[1])
                        if b not in available_chapters:
                            available_chapters[b] = set()
                        available_chapters[b].add(ch)
                    except ValueError:
                        pass

    # 目次生成
    index_html = generate_index_html(available_chapters)
    with open(os.path.join(OUTPUT_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(index_html)
    print(f"\n目次出力: index.html")
    print("完了!")


if __name__ == "__main__":
    main()
