import json

with open('data/Genesis/37/temp_in.json', 'r', encoding='utf-8') as f:
    d = json.load(f)

print(f"Verses count: {len(d['verses'])}")
for v in d['verses']:
    print(f"Verse {v['verse']}: {v['text']}")

print("\nNotes:")
for v_num, notes in d['notes'].items():
    print(f"\n--- Verse {v_num} ---")
    for n in notes:
        print(f"[{n['pos']}] {n['text']}")
