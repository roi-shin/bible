# -*- coding: utf-8 -*-
import json
import sys

# Combine all dictionaries
import make_part1, make_part2, make_part3
d = {}
d.update(make_part1.data_dict)
d.update(make_part2.data_dict)
d.update(make_part3.data_dict)

with open('data/Acts/13/temp_in.json', 'r', encoding='utf-8') as f:
    orig = json.load(f)

result = []
for item in orig:
    id_ = item['id']
    ja = d[id_]
    if id_ == 'n_15_2':
        ja = ja.replace('同じニュアンスを完全には伝えない。', '同じ意味合いをそのまま伝えるわけではない。')
    elif id_ == 'n_43_3':
        ja = ja.replace('完全にユダヤ教に改宗して', 'ユダヤ教に改宗して')
    elif id_ == 'v_41':
        ja = "『見よ、嘲る者たちよ。驚き、滅びよ。わたしはあなたがたの時代に一つの業を行う。誰かが告げても、あなたがたが信じることのないような業を。』」"
    elif id_ == 'n_41_2':
        ja = ja.replace('今まさにパウロが', '今パウロが')
    result.append({'id': id_, 'ja': ja})

with open('final_output.json', 'w', encoding='utf-8') as f:
    json.dump(result, f, ensure_ascii=False)

print("Count:", len(result))
