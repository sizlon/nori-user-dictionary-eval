"""dict_candidates.json → Nori user_dictionary_rules.
자동: 쪼개지되 글자가 안 사라지는 어절은 "어절 분절1 분절2"(mixed 모드에서 전체+분절), 글자가 사라지는 어절은 통째 한 토큰.
수동: 긴 어절 안에서만 나오거나 부분 검색이 필요한 탈락형에 사람이 분절을 붙인다(아래 MANUAL 목록). 같은 표면형은 수동이 자동을 대체.
사용: python3 build_rules.py [--out user_rules2.json] [--no-manual]
"""
import argparse, json

MANUAL = ['맨홀', '재선충병', '소나무재선충병 소나무 재선충병', '과업지시서 과업 지시서', '제안요청서 제안 요청서', '옹벽',
          '보안관제 보안 관제', '급경사지', '상수도관 상수도 관', '위험목', '간판정비 간판 정비', '전자견적 전자 견적',
          '수의계약 수의 계약', '소액수의 소액 수의', '단가계약 단가 계약', '하수관로 하수 관로', '우수관', '오수관', '용배수로 용배수 로']

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--out', default='user_rules2.json'); ap.add_argument('--no-manual', action='store_true')
    a = ap.parse_args()
    cand = json.load(open('dict_candidates.json', encoding='utf8'))
    rules = []; seen = set()
    for r in cand:
        w = r['w']
        if w in seen: continue
        seen.add(w); parts = r['seg'].split('+')
        rules.append(w + ' ' + ' '.join(parts) if (r['lost'] == 0 and len(parts) >= 2 and ''.join(parts) == w) else w)
    auto = len(rules)
    if not a.no_manual:
        have = {r.split()[0] for r in rules}
        rules += [m for m in MANUAL if m.split()[0] not in have]                 # 자동에 없는 표면형은 추가
        for m in MANUAL:                                                          # 자동에 있는데 수동에 분절이 있으면 교체
            w = m.split()[0]
            if w in have and ' ' in m: rules = [m if r.split()[0] == w else r for r in rules]
    json.dump(rules, open(a.out, 'w'), ensure_ascii=False)
    print(f'rules: {len(rules)} (auto {auto}, with-segmentation {sum(1 for r in rules if " " in r)}) → {a.out}')
