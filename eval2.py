"""평가: 질의 50 × 정답 기준 2(strict/loose) × P@10·R@50·MRR.
사용: python3 eval2.py base mixed tuned2 tuned2s [--prefix m_] [--out results.json]
strict: 공백 제거 제목이 공백 제거 질의를 연속 부분문자열로 포함. loose: 질의 어절 각각이 제목에 포함.
"""
import argparse, json, re, collections
from common import docs, search

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('indices', nargs='+'); ap.add_argument('--prefix', default=''); ap.add_argument('--out', default='results.json'); ap.add_argument('--queries', default='queries.json')
    a = ap.parse_args()
    norm = lambda s: re.sub(r'\s+', '', s).lower()
    Q = json.load(open(a.queries, encoding='utf8')); N = {d['id']: norm(d['title']) for d in docs()}
    rel_strict = lambda q: {i for i, t in N.items() if norm(q) in t}
    rel_loose = lambda q: (lambda ws: {i for i, t in N.items() if all(w in t for w in ws)})([norm(w) for w in q.split()])
    res = {}
    for ix in a.indices:
        rows = []
        for qq in Q:
            q = qq['q']; rs = rel_strict(q); rl = rel_loose(q); ids = [h[0] for h in search(a.prefix + ix, q, 50)]
            def m(rel):
                p10 = sum(1 for i in ids[:10] if i in rel) / 10
                r50 = sum(1 for i in ids[:50] if i in rel) / min(len(rel), 50) if rel else 0
                rr = next((1 / k for k, i in enumerate(ids, 1) if i in rel), 0.0); return p10, r50, rr
            rows.append({'q': q, 'grp': qq['grp'], 'rel_s': len(rs), 'rel_l': len(rl), 'strict': m(rs), 'loose': m(rl)})
        res[ix] = rows
    json.dump(res, open(a.out, 'w'), ensure_ascii=False)
    print('criterion  index     group         P@10   R@50   MRR')
    for crit in ['strict', 'loose']:
        for ix in a.indices:
            by = collections.defaultdict(list)
            for r in res[ix]: by[r['grp']].append(r[crit]); by['ALL'].append(r[crit])
            for g in ['lossy', 'inconsistent', 'control', 'ALL']:
                v = by[g]; print(f'{crit:9s}  {ix:8s}  {g:13s} {sum(x[0] for x in v)/len(v):.3f}  {sum(x[1] for x in v)/len(v):.3f}  {sum(x[2] for x in v)/len(v):.3f}')
    a0, a1 = a.indices[0], a.indices[-1]
    print(f'\nloose, {a0} → {a1}, moves ≥0.1:')
    for ra, rb in zip(res[a0], res[a1]):
        x, y = ra['loose'], rb['loose']
        if abs(x[0] - y[0]) >= 0.1 or abs(x[1] - y[1]) >= 0.1:
            print(f"  {ra['q']:12s} {ra['grp']:12s} rel={ra['rel_l']:5d}  P@10 {x[0]:.1f}→{y[0]:.1f}  R@50 {x[1]:.2f}→{y[1]:.2f}")
