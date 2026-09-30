import requests
import json

import os
API_KEY = os.getenv("GEMINI_API_KEY")

def test_generate(model_name):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={API_KEY}"
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": "Translate 'In the beginning God created the heavens and the earth' to Japanese. Respond with only a JSON like {\"ja\": \"...\"}"}]
            }
        ]
    }
    response = requests.post(url, json=payload)
    print(f"\n--- Model: {model_name} ---")
    if response.status_code == 200:
        res_json = response.json()
        try:
            text = res_json['candidates'][0]['content']['parts'][0]['text']
            print("Success!")
            print(text)
        except Exception as e:
            print("Format error:", res_json)
    else:
        print("Error:", response.status_code, response.text)

if __name__ == "__main__":
    test_generate("antigravity-preview-latest")
    test_generate("gemini-3.7-flash")
