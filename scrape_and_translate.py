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
from jinja2 import Environment, FileSystemLoader
import shutil
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

JA_BOOK_NAMES = {
    "Genesis": "創世記", "Exodus": "出エジプト記", "Leviticus": "レビ記",
    "Numbers": "民数記", "Deuteronomy": "申命記", "Joshua": "ヨシュア記",
    "Judges": "士師記", "Ruth": "ルツ記", "1 Samuel": "サムエル記上",
    "2 Samuel": "サムエル記下", "1 Kings": "列王記上", "2 Kings": "列王記下",
    "1 Chronicles": "歴代誌上", "2 Chronicles": "歴代誌下", "Ezra": "エズラ記",
    "Nehemiah": "ネヘミヤ記", "Esther": "エステル記", "Job": "ヨブ記",
    "Psalms": "詩編", "Proverbs": "箴言", "Ecclesiastes": "コヘレトの言葉",
    "Song of Solomon": "雅歌", "Isaiah": "イザヤ書", "Jeremiah": "エレミヤ書",
    "Lamentations": "哀歌", "Ezekiel": "エゼキエル書", "Daniel": "ダニエル書",
    "Hosea": "ホセア書", "Joel": "ヨエル書", "Amos": "アモス書",
    "Obadiah": "オバデヤ書", "Jonah": "ヨナ書", "Micah": "ミカ書",
    "Nahum": "ナホム書", "Habakkuk": "ハバクク書", "Zephaniah": "ゼファニヤ書",
    "Haggai": "ハガイ書", "Zechariah": "ゼカリヤ書", "Malachi": "マラキ書",
    "Matthew": "マタイによる福音書", "Mark": "マルコによる福音書",
    "Luke": "ルカによる福音書", "John": "ヨハネによる福音書",
    "Acts": "使徒言行録", "Romans": "ローマの信徒への手紙",
    "1 Corinthians": "コリントの信徒への手紙一", "2 Corinthians": "コリントの信徒への手紙二",
    "Galatians": "ガラテヤの信徒への手紙", "Ephesians": "エフェソの信徒への手紙",
    "Philippians": "フィリピの信徒への手紙", "Colossians": "コロサイの信徒への手紙",
    "1 Thessalonians": "テサロニケの信徒への手紙一", "2 Thessalonians": "テサロニケの信徒への手紙二",
    "1 Timothy": "テモテへの手紙一", "2 Timothy": "テモテへの手紙二",
    "Titus": "テトスへの手紙", "Philemon": "フィレモンへの手紙",
    "Hebrews": "ヘブライ人への手紙", "James": "ヤコブの手紙",
    "1 Peter": "ペトロの手紙一", "2 Peter": "ペトロの手紙二",
    "1 John": "ヨハネの手紙一", "2 John": "ヨハネの手紙二",
    "3 John": "ヨハネの手紙三", "Jude": "ユダの手紙", "Revelation": "ヨハネの黙示録"
}

BOOK_REVIEWS = {
    "Genesis": {"rank": "S", "comment": "天地創造、ノアの箱舟、バベルの塔などファンタジーやSFの元ネタの宝庫。後半のヨセフのサクセスストーリーも必読。"},
    "Exodus": {"rank": "A", "comment": "海が真っ二つに割れる「十戒」のハイライトまで読めばOK。後半の「幕屋（テント）の作り方」はスルー推奨。"},
    "Leviticus": {"rank": "C", "comment": "延々と続く生贄や生活のルール。「レビ記の壁」と呼ばれる最大の挫折ポイント。"},
    "Numbers": {"rank": "C", "comment": "部族の人口調査と荒野の放浪の記録。通読にはかなりの忍耐が必要。"},
    "Deuteronomy": {"rank": "C", "comment": "モーセの長い遺言と律法の再確認。"},
    "Joshua": {"rank": "B", "comment": "エリコの城壁崩壊など、約束の地カナン征服の血生臭い戦記。（おすすめ: 6章）"},
    "Judges": {"rank": "A", "comment": "怪力サムソンなど、野性的でバイオレンスな英雄たちの物語。士師（リーダー）たちの活躍。"},
    "Ruth": {"rank": "A", "comment": "士師時代の殺伐とした空気を和ませる、心温まる嫁姑の美しい物語。"},
    "1 Samuel": {"rank": "S", "comment": "羊飼いダビデの台頭、ゴリアテ討伐、サウル王との愛憎劇。海外ドラマ顔負けの大河ドラマの傑作。"},
    "2 Samuel": {"rank": "S", "comment": "ダビデ王の栄華と、不倫・殺人に端を発する息子たちとの骨肉の争い。"},
    "1 Kings": {"rank": "A", "comment": "ソロモン王の栄華から王国の分裂へ。預言者エリヤの奇跡バトルなど見どころが多い。"},
    "2 Kings": {"rank": "B", "comment": "分裂した王国が次々と悪王によって腐敗し、ついに滅亡するまでの歴史。（おすすめ: 2章, 25章）"},
    "1 Chronicles": {"rank": "C", "comment": "サムエル記のダイジェスト版。ひたすら家系図が続くためスルー推奨。"},
    "2 Chronicles": {"rank": "C", "comment": "列王記のダイジェスト版（南ユダ王国視点）。"},
    "Ezra": {"rank": "B", "comment": "バビロン捕囚からエルサレムへの帰還と、神殿の再建ドラマ。（おすすめ: 1章, 3章）"},
    "Nehemiah": {"rank": "B", "comment": "廃墟となったエルサレムの城壁を再建する、熱いリーダーシップの物語。（おすすめ: 2章, 8章）"},
    "Esther": {"rank": "A", "comment": "神の名が一度も出てこない、ペルシャ王宮を舞台にしたユダヤ人女性のシンデレラ＆逆転劇。"},
    "Job": {"rank": "A", "comment": "「なぜ善人に理不尽な不幸が起きるのか？」に挑んだ哲学的で美しい長編詩。"},
    "Psalms": {"rank": "B", "comment": "古代イスラエルの賛美歌集。気が向いた時に文学としてつまみ食い推奨。（おすすめ: 23編, 51編）"},
    "Proverbs": {"rank": "B", "comment": "「知恵」をテーマにした格言集。ビジネスや日常に生きる教えも。（おすすめ: 3章, 31章）"},
    "Ecclesiastes": {"rank": "S", "comment": "「空の空、すべては空」。数千年前の虚無主義的で鋭い人間観察の傑作。現代人にも刺さる。"},
    "Song of Solomon": {"rank": "B", "comment": "神と人の愛を男女の官能的な恋愛詩に託した異色の書。（おすすめ: 8章）"},
    "Isaiah": {"rank": "B", "comment": "メシア（救い主）到来の預言。文学的価値は高いが、背景知識がないと難しい。（おすすめ: 6章, 53章）"},
    "Jeremiah": {"rank": "C", "comment": "滅びゆく国を前に涙する預言者エレミヤの警告。長い。"},
    "Lamentations": {"rank": "C", "comment": "エルサレム滅亡の悲惨さを嘆く詩。"},
    "Ezekiel": {"rank": "C", "comment": "幻（ビジョン）や象徴的な行動が多い、ちょっとサイケデリックな預言書。"},
    "Daniel": {"rank": "A", "comment": "ライオンの穴、燃える炉など奇跡の連続。後半は黙示録的なビジョン。"},
    "Hosea": {"rank": "C", "comment": "不貞の妻を愛し続ける預言者の姿を通して神の愛を描く。"},
    "Joel": {"rank": "C", "comment": "いなごの大群による災害と「主の日」の預言。"},
    "Amos": {"rank": "C", "comment": "社会の不正義を厳しく糾弾した預言。"},
    "Obadiah": {"rank": "C", "comment": "エドムに対する裁きの預言（全1章）。"},
    "Jonah": {"rank": "A", "comment": "巨大な魚に飲み込まれるおじさんのコミカルな逃亡劇。唯一物語として面白い預言書。"},
    "Micah": {"rank": "C", "comment": "メシアがベツレヘムで生まれるという預言が含まれる。"},
    "Nahum": {"rank": "C", "comment": "アッシリアの首都ニネベの滅亡を預言。"},
    "Habakkuk": {"rank": "C", "comment": "なぜ悪人が栄えるのかと神に問い詰める対話。"},
    "Zephaniah": {"rank": "C", "comment": "全世界への裁きと回復の預言。"},
    "Haggai": {"rank": "C", "comment": "神殿再建を励ます預言。"},
    "Zechariah": {"rank": "C", "comment": "幻視的で難解。メシアがろばに乗って来る預言など。"},
    "Malachi": {"rank": "C", "comment": "旧約聖書最後の書。人々の堕落を叱責。"},
    "Matthew": {"rank": "S", "comment": "山上の垂訓などイエスの教えが豊富。「最後の晩餐」や十字架の物語の基本。"},
    "Mark": {"rank": "A", "comment": "一番短く、スピーディに行動を描く。"},
    "Luke": {"rank": "S", "comment": "異邦人向けで分かりやすく、放蕩息子の例え話やクリスマスのエピソードが豊富。"},
    "John": {"rank": "A", "comment": "哲学的なアプローチでイエスを描く。「初めにことばがあった」。"},
    "Acts": {"rank": "B", "comment": "ペテロやパウロが大暴れしてキリスト教を世界に広める胸熱ドキュメンタリー。（おすすめ: 2章, 9章）"},
    "Romans": {"rank": "C", "comment": "パウロの神学の集大成。キリスト教徒以外には退屈。"},
    "1 Corinthians": {"rank": "C", "comment": "教会の問題解決に向けたパウロの手紙。「愛の賛歌」が有名。"},
    "2 Corinthians": {"rank": "C", "comment": "パウロの個人的な苦難と使徒としての権威の弁明。"},
    "Galatians": {"rank": "C", "comment": "「信仰による義認」を熱く語る手紙。"},
    "Ephesians": {"rank": "C", "comment": "教会とキリストの神秘的な関係。"},
    "Philippians": {"rank": "C", "comment": "獄中から書かれた喜びの手紙。"},
    "Colossians": {"rank": "C", "comment": "キリストの優位性を説く。"},
    "1 Thessalonians": {"rank": "C", "comment": "キリストの再臨についての励まし。"},
    "2 Thessalonians": {"rank": "C", "comment": "再臨の前の「不法の者」についての警告。"},
    "1 Timothy": {"rank": "C", "comment": "牧会（教会の指導）についてのマニュアル。"},
    "2 Timothy": {"rank": "C", "comment": "パウロの遺言とも言える最後の手紙。"},
    "Titus": {"rank": "C", "comment": "教会の秩序についての指示。"},
    "Philemon": {"rank": "C", "comment": "逃亡奴隷の許しを願う非常に短い手紙。"},
    "Hebrews": {"rank": "C", "comment": "キリストが旧約のいけにえや祭司より優れていることを論証。"},
    "James": {"rank": "C", "comment": "「行いのない信仰は死んだもの」という実践的な手紙。"},
    "1 Peter": {"rank": "C", "comment": "迫害の中にある信者への励まし。"},
    "2 Peter": {"rank": "C", "comment": "偽教師への警告と再臨の確実性。"},
    "1 John": {"rank": "C", "comment": "「神は愛である」ことを強調。"},
    "2 John": {"rank": "C", "comment": "真理と愛のうちに歩むこと（全1章）。"},
    "3 John": {"rank": "C", "comment": "教会内の対立への対処（全1章）。"},
    "Jude": {"rank": "C", "comment": "偽教師への厳しい警告（全1章）。"},
    "Revelation": {"rank": "A", "comment": "「ハルマゲドン」「666」など、中二病・ファンタジー・SFの元ネタの宝庫。"}
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

import os
from dotenv import load_dotenv
load_dotenv()

# config.json のロード
CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config.json")
def load_api_configs():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            content = f.read()
            import re
            # JSONC形式（//コメント）のサポートのためコメント行を除去
            content = re.sub(r'^\s*//.*$', '', content, flags=re.MULTILINE)
            # コメント削除によって残ってしまった末尾のカンマ（Trailing comma）を除去
            content = re.sub(r',\s*([\]}])', r'\1', content)
            return json.loads(content).get("api_configs", [])
    # フォールバックのデフォルト
    return [{
        "key_env": "GEMINI_API_KEY",
        "exclude_models": []
    }]

API_CONFIGS = load_api_configs()

def translate_with_agy(raw_data: dict, use_api: bool = False) -> dict:
    """agy CLIを使ってJSON全体の英語を一括翻訳する"""
    # LLMの負担を減らすため、送信用のデータ構造をフラットなリストに整理（候補1の実装）
    flat_payload = []
    for v in raw_data["text_data"]:
        flat_payload.append({
            "id": f"v_{v['verse']}",
            "text": BeautifulSoup(v["text"], 'html.parser').get_text()
        })
    for vn, notes_list in raw_data["notes"].items():
        for pos, text in notes_list:
            flat_payload.append({
                "id": f"n_{vn}_{pos}",
                "text": clean_note_html(text)
            })

    json_str = json.dumps(flat_payload, ensure_ascii=False)
    
    # テンポラリファイルに保存
    temp_in = temp_in_path if 'temp_in_path' in globals() else os.path.join(DATA_DIR, "temp_in.json")
    with open(temp_in, "w", encoding="utf-8") as f:
        f.write(json_str)

    prompt = (
        f"Read the file '{temp_in}'. It contains a JSON array of Bible verses (id: v_X) and notes (id: n_X_Y). "
        f"Translate all English text in the provided JSON array to natural, dignified Japanese. "
        f"CRITICAL INSTRUCTION 1 (Notes Context): Notes contain highly detailed translator's notes, study notes, and text-critical notes that justify the specific English translation choices. "
        f"When translating the verses, you MUST carefully cross-reference and incorporate the nuances and justifications provided in the corresponding notes for that verse. "
        f"Ensure that the Japanese translation of the verses accurately reflects the theological and grammatical insights detailed in the notes. "
        f"CRITICAL INSTRUCTION 2 (Consistency & Tone): Maintain a consistent biblical tone across all chapters. Use the 'である/だ' (dearu/da) style consistently for the verse text, and polite 'です/ます' (desu/masu) or 'である/だ' style consistently for notes. Use standard Japanese Christian terminology (e.g. 神, 主, 創造, 恵み, 契約). "
        f"Return the output as a JSON array of objects, where each object has exactly two keys: 'id' (copied exactly from the input) and 'ja' (the Japanese translation). "
        f"Example output format: [{{\"id\": \"v_1\", \"ja\": \"...\"}}, {{\"id\": \"n_1_1\", \"ja\": \"...\"}}]\n"
        f"Output ONLY raw JSON array, do not use markdown code blocks."
    )

    import time
    max_retries = 3
    
    def rebuild_translated_data(flat_response: list) -> dict:
        """フラットなリストを元のネストされた構造に戻す"""
        rebuilt = {"verses": [], "notes": {}}
        for item in flat_response:
            if not isinstance(item, dict):
                continue
            item_id = item.get("id", "")
            ja_text = item.get("ja", item.get("text", ""))
            if item_id.startswith("v_"):
                parts = item_id.split("_")
                if len(parts) >= 2:
                    rebuilt["verses"].append({"verse": parts[1], "ja": ja_text})
            elif item_id.startswith("n_"):
                parts = item_id.split("_")
                if len(parts) >= 3:
                    verse_num, pos = parts[1], parts[2]
                    if verse_num not in rebuilt["notes"]:
                        rebuilt["notes"][verse_num] = []
                    rebuilt["notes"][verse_num].append({"pos": int(pos), "ja": ja_text})
        return rebuilt

    if use_api:
        all_available_models = [
            "gemini-3.5-flash-lite",
            "gemini-3.8-flash",
            "gemini-3.7-flash",
            "gemini-3.6-flash",
            "gemini-3.5-flash",
            "gemini-3-flash-preview",
        ]
        api_prompt = prompt + "\n\nHere is the JSON data to translate:\n" + json_str
        
        for config in API_CONFIGS:
            api_key = config.get("key_raw")
            if not api_key and config.get("key_env"):
                api_key = os.getenv(config.get("key_env"))
            if not api_key:
                continue

            exclude_models = set(config.get("exclude_models", []))
            models_to_try = [m for m in all_available_models if m not in exclude_models]
            
            for model_name in models_to_try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
                payload = {
                    "contents": [{"role": "user", "parts": [{"text": api_prompt}]}],
                    "generationConfig": {"responseMimeType": "application/json"}
                }
                max_retries_api = 3
                for attempt in range(max_retries_api):
                    resp = requests.post(url, json=payload, timeout=120)
                    if resp.status_code == 200:
                        try:
                            text = resp.json()['candidates'][0]['content']['parts'][0]['text']
                            print(f"    [{model_name}] 成功")
                            flat_resp = json.loads(text)
                            if isinstance(flat_resp, dict) and "response" in flat_resp:
                                flat_resp = json.loads(flat_resp["response"])
                            return rebuild_translated_data(flat_resp)
                        except Exception as e:
                            print(f"    [{model_name}] レスポンス形式エラー: {e}")
                            break
                    elif resp.status_code in (429, 503):
                        err_msg = resp.json().get("error", {}).get("message", "")
                        if "quota" in err_msg.lower() or resp.status_code == 429:
                            print(f"    [{model_name}] RPD上限に達しました。次のモデルへ切替...")
                            break  # このモデルを諦めて次へ
                        else:
                            print(f"    [{model_name}] 一時的なエラー (試行 {attempt + 1}/{max_retries_api})、10秒後に再試行...")
                            time.sleep(10)
                    else:
                        print(f"    [{model_name}] エラー {resp.status_code}: {resp.text[:100]}")
                        break
        raise Exception("全ての設定キー、全フォールバックモデルのAPI呼び出しに失敗しました")

    else:
        # agy コマンドの構築
        cmd = [
            "agy", "-p",
            prompt,
            "--model", "gemini-3.7-flash-medium",
            "--output-format", "json",
            "--dangerously-skip-permissions"
        ]
        
        print("    agy CLI を呼び出して一括翻訳中...")
        for attempt in range(max_retries):
            result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
            if result.returncode == 0:
                break
            print(f"    [警告] agyコマンドエラー (試行 {attempt + 1}/{max_retries}):\n{result.stderr}")
            if attempt < max_retries - 1:
                print("    10秒待機して再試行します...")
                time.sleep(10)
            else:
                raise Exception("agy CLI translation failed after retries")
        else:
            raise Exception("agy CLI translation failed after retries")
        
    try:
        # agyの--output-format json は {"response": "..."} でラップされるので、
        # まず外側のJSONをパースし、その中のresponse文字列をさらにパースする
        outer_json_text = result.stdout.strip().split("\n")[-1] # エラーメッセージ等を無視して最後の行を取得
        outer_json = json.loads(outer_json_text)
        response_text = outer_json.get("response", "").strip()
        flat_resp = json.loads(response_text)
        return rebuild_translated_data(flat_resp)
        
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


def process_chapter(book: str, chapter: int, use_api: bool = False) -> dict:
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
        raw_data = {"notes": notes, "text_data": text_data}
        with open(raw_file, "w", encoding="utf-8") as f:
            json.dump(raw_data, f, ensure_ascii=False, indent=2)

    # テンポラリファイル用にパスを上書き (translate_with_agy 内で使用するため)
    global temp_in_path
    temp_in_path = os.path.join(chap_dir, "temp_in.json")

    # 翻訳
    print(f"  翻訳中 (agy使用): {book} {chapter}")
    translated_data = translate_with_agy(raw_data, use_api)

    result = {
        "book": book,
        "chapter": chapter,
        "verses": [],
        "notes": {},
    }

    # raw_dataから英語原文のマップを作成（補填用）
    en_text_map = {}
    for v in raw_data.get("text_data", []):
        vn = int(v.get("verse_num", v.get("verse", 0)))
        en_text_map[vn] = v.get("text", "")

    # raw_dataからノートの英語原文マップを作成
    en_notes_map = {}
    for v_num_str, notes_list in raw_data.get("notes", {}).items():
        v_num = int(v_num_str) if str(v_num_str).strip().isdigit() else 0
        en_notes_map[v_num] = {}
        for pos, text in notes_list:
            en_notes_map[v_num][pos] = text

    def extract_text(value):
        if isinstance(value, str):
            return value
        if isinstance(value, list):
            return " ".join(extract_text(v) for v in value)
        if isinstance(value, dict):
            return " ".join(extract_text(v) for v in value.values())
        return str(value)

    # 翻訳結果の構築
    for i, v in enumerate(translated_data.get("verses", [])):
        verse_num_raw = v.get("verse", v.get("verse_num"))
        verse_num = None
        if verse_num_raw is not None:
            # 数字以外の文字が含まれている場合（'8, ' など）を除去して安全にキャスト
            cleaned_num = ''.join(c for c in str(verse_num_raw) if c.isdigit())
            if cleaned_num:
                verse_num = int(cleaned_num)
        
        if verse_num is None:
            # モデルが節番号を省略したり不正な値の場合、元のテキストデータの順番から推測
            raw_verses = raw_data.get("text_data", [])
            if i < len(raw_verses):
                verse_num = int(raw_verses[i].get("verse_num", raw_verses[i].get("verse", 0)))
            else:
                continue
        
        ja_text = v.get("ja", v.get("text", ""))
        # 英語原文はAPIレスポンスに頼らず、raw_dataから確実に取得
        en_text = en_text_map.get(verse_num, v.get("text", v.get("en", "")))

        result["verses"].append({
            "verse": verse_num,
            "en": en_text,
            "ja": ja_text,
        })

    # モデルによっては notes が list[{verse_num, pos, ja, text}] 形式で返る場合があるため正規化
    raw_notes = translated_data.get("notes", {})
    if isinstance(raw_notes, list):
        normalized = {}
        for n in raw_notes:
            key = str(n.get("verse_num", n.get("verse", "")))
            if not key.strip():  # 空キーは無視
                continue
            if key not in normalized:
                normalized[key] = []
            normalized[key].append(n)
        raw_notes = normalized

    # raw_dataのnotesをベースに結果を構築（モデル出力の欠落・省略を防ぐため）
    for v_num_str, notes_list in raw_data.get("notes", {}).items():
        translated_notes = []
        # モデルが返した対応する節のノート
        model_verse_notes = raw_notes.get(str(v_num_str), [])
        
        for i, raw_note in enumerate(notes_list):
            pos = raw_note[0]
            en_note = clean_note_html(raw_note[1])
            
            # モデルの出力から対応するposのjaを探す
            ja_note = ""
            found = False
            for mn in model_verse_notes:
                if isinstance(mn, dict):
                    mn_pos = mn.get("pos", mn.get("note_pos"))
                    if str(mn_pos) == str(pos):
                        ja_note = extract_text(mn.get("ja", mn.get("text", "")))
                        found = True
                        break
            
            # posでマッチしなかった場合、順番でフォールバック
            if not found and i < len(model_verse_notes):
                mn = model_verse_notes[i]
                if isinstance(mn, dict):
                    ja_note = extract_text(mn.get("ja", mn.get("text", "")))
            
            translated_notes.append({
                "pos": pos,
                "en": en_note,
                "ja": ja_note,
            })
            
        result["notes"][str(v_num_str)] = translated_notes

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


def main():
    import sys

    args = sys.argv[1:]
    use_api = False
    if "--api" in args:
        use_api = True
        args.remove("--api")

    # コマンドライン引数: python scrape_and_translate.py Genesis 1
    # 範囲指定: python scrape_and_translate.py Genesis 4-10 (または 4~10)
    if len(args) >= 2:
        book = args[0]
        ch_arg = args[1]
        if "-" in ch_arg or "~" in ch_arg:
            delimiter = "-" if "-" in ch_arg else "~"
            try:
                start_ch, end_ch = map(int, ch_arg.split(delimiter))
                books_to_process = [(book, ch) for ch in range(start_ch, end_ch + 1)]
            except ValueError:
                print(f"エラー: 無効な章の範囲指定です ({ch_arg})")
                sys.exit(1)
        else:
            chapter = int(ch_arg)
            books_to_process = [(book, chapter)]
    elif len(args) == 1:
        book = args[0]
        books_to_process = [(book, ch) for ch in range(1, BOOKS.get(book, 1) + 1)]
    else:
        # デフォルト: Genesis 1
        books_to_process = [("Genesis", 1)]

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(DATA_DIR, exist_ok=True)

    # CSS, JS, ガイドは templates/ から直接コピーまたはそのまま書き出す
    shutil.copy(os.path.join("templates", "style.css"), os.path.join(OUTPUT_DIR, "style.css"))
    shutil.copy(os.path.join("templates", "app.js"), os.path.join(OUTPUT_DIR, "app.js"))
    shutil.copy(os.path.join("templates", "guide.html"), os.path.join(OUTPUT_DIR, "guide.html"))
    print("CSS, JS, ガイド出力: 完了")

    # Jinja2 環境の設定
    env = Environment(loader=FileSystemLoader("templates"))
    chapter_template = env.get_template("chapter.html")
    index_template = env.get_template("index.html")

    # 処理 (データ取得)
    # ここでは自分自身の担当分だけを処理・保存する
    for book, chapter in books_to_process:
        print(f"\n=== {book} {chapter} ===")
        try:
            data = process_chapter(book, chapter, use_api)
            export_markdown(data)
        except Exception as e:
            print(f"  エラー: {e}")
            import traceback
            traceback.print_exc()

    # 自分の処理が全て終わった後、HTML生成の直前で「現在のディスク上の最新状態」をスキャンする
    available_chapters = {}
    if os.path.exists(DATA_DIR):
        for b_dir in os.listdir(DATA_DIR):
            book_path = os.path.join(DATA_DIR, b_dir)
            if os.path.isdir(book_path):
                b_name = b_dir.replace("_", " ")
                for c_dir in os.listdir(book_path):
                    ch_path = os.path.join(book_path, c_dir)
                    if os.path.isdir(ch_path) and os.path.exists(os.path.join(ch_path, "data.json")):
                        try:
                            ch = int(c_dir)
                            if b_name not in available_chapters:
                                available_chapters[b_name] = set()
                            available_chapters[b_name].add(ch)
                        except ValueError:
                            pass

    # 全ての available_chapters の HTML を再生成
    print("\n=== HTML一括再生成 ===")
    for b_name, chapters in available_chapters.items():
        for ch in chapters:
            try:
                ch_path = os.path.join(DATA_DIR, b_name.replace(" ", "_"), str(ch), "data.json")
                if os.path.exists(ch_path):
                    with open(ch_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    
                    book = data["book"]
                    chapter = data["chapter"]
                    ja_book = JA_BOOK_NAMES.get(book, book)
                    title_ja = f"{ja_book} {chapter}"
                    title_en = f"{book} {chapter}"
                    
                    prev_ch_available = book in available_chapters and (chapter - 1) in available_chapters[book]
                    next_ch_available = book in available_chapters and (chapter + 1) in available_chapters[book]
                    prev_link = f"{book.replace(' ', '_')}_{chapter-1}.html" if prev_ch_available else None
                    next_link = f"{book.replace(' ', '_')}_{chapter+1}.html" if next_ch_available else None

                    sorted_notes = sorted(data.get("notes", {}).items(), key=lambda x: int(x[0]) if x[0].strip().isdigit() else 0)

                    html = chapter_template.render(
                        title_ja=title_ja,
                        title_en=title_en,
                        prev_link=prev_link,
                        next_link=next_link,
                        verses=data.get("verses", []),
                        notes=data.get("notes", {}),
                        sorted_notes=sorted_notes,
                        summary=data.get("summary"),
                        map_context=data.get("map_context")
                    )
                    
                    fname = f"{book.replace(' ', '_')}_{ch}.html"
                    with open(os.path.join(OUTPUT_DIR, fname), "w", encoding="utf-8") as f:
                        f.write(html)
            except Exception as e:
                print(f"  HTML生成エラー ({b_name} {ch}): {e}")

    # 目次生成
    ot_books_data = []
    for b in list(BOOKS.keys())[:39]:
        review = BOOK_REVIEWS.get(b, {"rank": "-", "comment": ""})
        rank = review["rank"]
        rank_class = f"rank-{rank.lower()}" if rank in ["S", "A", "B", "C"] else "rank-none"
        ot_books_data.append({
            "en_name": b,
            "ja_name": JA_BOOK_NAMES.get(b, b),
            "total_chapters": BOOKS[b],
            "rank": rank,
            "rank_class": rank_class,
            "comment": review["comment"]
        })
        
    nt_books_data = []
    for b in list(BOOKS.keys())[39:]:
        review = BOOK_REVIEWS.get(b, {"rank": "-", "comment": ""})
        rank = review["rank"]
        rank_class = f"rank-{rank.lower()}" if rank in ["S", "A", "B", "C"] else "rank-none"
        nt_books_data.append({
            "en_name": b,
            "ja_name": JA_BOOK_NAMES.get(b, b),
            "total_chapters": BOOKS[b],
            "rank": rank,
            "rank_class": rank_class,
            "comment": review["comment"]
        })

    index_html = index_template.render(
        ot_books=ot_books_data,
        nt_books=nt_books_data,
        available_chapters=available_chapters
    )
    with open(os.path.join(OUTPUT_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(index_html)
    print("\n目次出力: index.html")
    
    print("完了!")


if __name__ == "__main__":
    main()
