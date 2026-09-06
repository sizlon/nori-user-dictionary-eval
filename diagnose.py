"""진단 + 사전 후보 추출. base 분석기로 제목 전체를 분석해 어절(한글 3~10자)별 분절을 오프셋으로 귀속한다.
사용: python3 diagnose.py [--index base] [--min 30]
출력: word_freq.json(어절 빈도), seg_inconsistency.json(문맥별 분절이 둘 이상인 어절), dict_candidates.json(사전 후보)
"""
import argparse, json, re, collections, bisect
from common import docs, analyze

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--index', default='base'); ap.add_argument('--min', type=int, default=30); ap.add_argument('--batch', type=int, default=500)
    a = ap.parse_args()
    titles = [d['title'] for d in docs()]
    word_re = re.compile(r'[가-힣]{3,10}')
    seg = collections.defaultdict(collections.Counter); freq = collections.Counter()
    for i in range(0, len(titles), a.batch):
        batch = titles[i:i + a.batch]
        toks = analyze(a.index, batch)               # ES 는 배열 입력의 오프셋을 이어붙여(요소 사이 +1) 누적한다
        offs = []; cur = 0
        for t in batch: offs.append(cur); cur += len(t) + 1
        per = collections.defaultdict(list)
        for tk in toks:
            j = bisect.bisect_right(offs, tk['start_offset']) - 1
            per[j].append((tk['start_offset'] - offs[j], tk['end_offset'] - offs[j], tk['token']))
        for j, t in enumerate(batch):
            for m in word_re.finditer(t):
                s, e = m.span(); w = m.group()
                parts = tuple(tok for (x, y, tok) in per.get(j, []) if x >= s and y <= e)
                seg[w][parts] += 1; freq[w] += 1
        if (i // a.batch) % 50 == 0: print(f'  analyzed {i + len(batch)}/{len(titles)}')
    common = [w for w in freq if freq[w] >= a.min]
    incons = {w: seg[w] for w in common if len(seg[w]) >= 2}
    minority = sum(freq[w] - seg[w].most_common(1)[0][1] for w in incons); total = sum(freq[w] for w in incons)
    print(f'titles {len(titles)} | words >={a.min}: {len(common)} | inconsistently segmented: {len(incons)} ({len(incons)/len(common):.1%})')
    print(f'occurrences in minority segmentation: {minority}/{total} = {minority/total:.1%}')
    rows = sorted(incons.items(), key=lambda kv: -(freq[kv[0]] - kv[1].most_common(1)[0][1]))
    for w, c in rows[:15]: print(f'  {w:9s} n={freq[w]:5d} ', ' | '.join(f"{'+'.join(p)}×{k}" for p, k in c.most_common(3)))
    json.dump({w: {'+'.join(p): k for p, k in c.items()} for w, c in rows}, open('seg_inconsistency.json', 'w'), ensure_ascii=False)
    cand = []
    for w in common:
        parts, k = seg[w].most_common(1)[0]; joined = ''.join(parts)
        if len(parts) >= 2 or len(joined) < len(w):
            cand.append({'w': w, 'n': freq[w], 'seg': '+'.join(parts), 'lost': len(w) - len(joined)})
    cand.sort(key=lambda r: -r['n'])
    print(f'dictionary candidates (split or lossy, freq>={a.min}): {len(cand)}')
    for r in cand[:10]: print(f"  {r['w']:9s} n={r['n']:5d} {r['seg']}  lost={r['lost']}")
    json.dump(cand, open('dict_candidates.json', 'w'), ensure_ascii=False)
    json.dump(freq, open('word_freq.json', 'w'), ensure_ascii=False)
