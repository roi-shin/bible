import json

with open('data/Genesis/37/temp_in.json', 'r', encoding='utf-8') as f:
    orig = json.load(f)

with open('scratch/gen37_out.json', 'r', encoding='utf-8') as f:
    out = json.load(f)

# 1. Verses count and keys check
assert len(orig['verses']) == len(out['verses']), f"Verses length mismatch: {len(orig['verses'])} vs {len(out['verses'])}"
for o_v, out_v in zip(orig['verses'], out['verses']):
    assert o_v['verse'] == out_v['verse'], f"Verse num mismatch: {o_v['verse']} vs {out_v['verse']}"
    assert o_v['text'] == out_v['text'], f"Verse text mismatch in v{o_v['verse']}"
    assert 'ja' in out_v and len(out_v['ja'].strip()) > 0, f"Missing or empty ja in verse {out_v['verse']}"

# 2. Notes count and keys check
assert set(orig['notes'].keys()) == set(out['notes'].keys()), f"Notes keys mismatch: {set(orig['notes'].keys()) ^ set(out['notes'].keys())}"
for v_key, orig_notes in orig['notes'].items():
    out_notes = out['notes'][v_key]
    assert len(orig_notes) == len(out_notes), f"Notes length mismatch in verse {v_key}"
    for o_n, out_n in zip(orig_notes, out_notes):
        assert o_n['pos'] == out_n['pos'], f"Pos mismatch in v{v_key}"
        assert o_n['text'] == out_n['text'], f"Note text mismatch in v{v_key}:{o_n['pos']}"
        assert 'ja' in out_n and len(out_n['ja'].strip()) > 0, f"Missing or empty ja in v{v_key}:{out_n['pos']}"

print("All validations PASSED successfully!")
