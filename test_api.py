"""
Gemini 3.7-flash (既存翻訳) vs Gemini 3.5-flash-lite (新規翻訳) の品質比較テスト
出エジプト記1章の本文と注釈の一部を使って比較する
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")

# --- テスト対象: 出エジプト記1章の一部 ---
test_verses = [
    {"verse": 7, "en": "The Israelites, however, were fruitful, increased greatly, multiplied, and became extremely strong, so that the land was filled with them."},
    {"verse": 10, "en": "Come, let's deal wisely with them. Otherwise they will continue to multiply, and if a war breaks out, they will ally themselves with our enemies and fight against us and leave the country."},
    {"verse": 19, "en": 'The midwives said to Pharaoh, "Because the Hebrew women are not like the Egyptian women—for the Hebrew women are vigorous; they give birth before the midwife gets to them!"'},
]

test_note = "The Hebrew word for vigorous (חָיוֹת, khayot) can mean 'lively' or 'vigorous' or even 'like animals.' The point is that the Hebrew women gave birth very rapidly, before the midwife could arrive."

# 既存の 3.7-flash による翻訳（正解）
existing_translations = {
    7:  "しかしイスラエルの子らは多くの子孫を残して満ちあふれ、数を増して非常に強くなり、その地は彼らで満ちた。",
    10: "さあ、彼らに巧みに対処しよう。そうでなければ彼らはさらに増え続け、戦いが起こったときには敵と同盟を結び、我々と戦ってこの国から立ち去ってしまうだろう」。",
    19: "助産婦たちはパロに答えた。「ヘブル人の女はエジプト人の女とは違い、力強いからです。助産婦が行く前に産んでしまうのです」。",
}
existing_note_ja = "ヘブル語の「力強い」を意味する語（חָיוֹת）は、「活発な」「力強い」、あるいは「動物のような」を意味することもできる。要点は、ヘブル人の女性たちが非常に素早く出産し、助産婦が到着する前に産み終えてしまったということである。"


def translate_with_model(model_name: str, verses: list, note: str) -> dict:
    prompt = (
        f"Translate the following Bible verses and note from English to Japanese. "
        f"The source is the NET Bible. Use formal, scholarly Japanese (である/だ調). "
        f"Return ONLY a JSON object in this exact format:\n"
        f"{{\"verses\": [{{\"verse\": 7, \"ja\": \"...\"}}, ...], \"note_ja\": \"...\"}}\n\n"
        f"Verses to translate:\n{json.dumps(verses, ensure_ascii=False)}\n\n"
        f"Note to translate:\n{note}"
    )
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={API_KEY}"
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json"}
    }
    resp = requests.post(url, json=payload, timeout=60)
    if resp.status_code == 200:
        text = resp.json()['candidates'][0]['content']['parts'][0]['text']
        return json.loads(text)
    else:
        raise Exception(f"API Error {resp.status_code}: {resp.text[:200]}")


print("=" * 60)
print("Gemini 3.5-flash-lite による翻訳テスト")
print("=" * 60)

result = translate_with_model("gemini-3.5-flash-lite", test_verses, test_note)

print("\n【節の比較】")
for v in test_verses:
    vn = v["verse"]
    new_ja = next((x["ja"] for x in result["verses"] if x["verse"] == vn), "(取得失敗)")
    old_ja = existing_translations[vn]
    print(f"\n--- 節 {vn} ---")
    print(f"[英語原文] {v['en']}")
    print(f"[3.7-flash] {old_ja}")
    print(f"[3.5-lite]  {new_ja}")

print("\n\n【注釈の比較】")
print(f"[英語原文] {test_note}")
print(f"[3.7-flash] {existing_note_ja}")
print(f"[3.5-lite]  {result.get('note_ja', '(取得失敗)')}")
print("\n" + "=" * 60)
print("テスト完了")
