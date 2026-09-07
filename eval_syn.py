"""동의어 평가: 질의 42 × 정답 기준 2(single/expanded) × P@10·R@50·MRR.
사용: python3 eval_syn.py tuned2s syn [--out results_syn.json]
single: 기존 loose — 질의 어절 각각이 제목에 포함. expanded: 어절이 동의어 군에 속하면 군의 어떤 표기든 포함하면 정답.
영문 약어는 단어 경계 요구(ai 가 air 에 걸리지 않게). 두 기준의 차이가 "표기 하나로 검색하면 놓치는 문서" 다.
"""
import argparse, json, re, collections
from common import docs, requests, ES

def search(ix, q, size=50, mode='plain'):
    if mode == 'plain': body = {'match': {'title': q}}
    elif mode == 'nophrase': body = {'match': {'title': {'query': q, 'auto_generate_synonyms_phrase_query': False}}}
    elif mode.startswith('twofield'):
        syn = {'query': q}
        if mode.endswith('_np'): syn['auto_generate_synonyms_phrase_query'] = False
        body = {'bool': {'should': [{'match': {'title': {'query': q, 'boost': 2}}}, {'match': {'title.syn': syn}}]}}
    r = requests.post(f'{ES}/{ix}/_search', json={'size': size, '_source': ['title'], 'query': body}); r.raise_for_status()
    return [(h['_id'], h['_source']['title'], h['_score']) for h in r.json()['hits']['hits']]

def matcher(term):
    t = re.sub(r'\s+', '', term).lower()
    if re.fullmatch(r'[a-z0-9/&-]+', t): rx = re.compile(r'(?<![a-z])' + re.escape(t) + r'(?![a-z])'); return lambda s: bool(rx.search(s))
    return lambda s: t in s

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('indices', nargs='+'); ap.add_argument('--out', default='results_syn.json'); ap.add_argument('--queries', default='queries_syn.json'); ap.add_argument('--synonyms', default='synonyms.json'); ap.add_argument('--mode', default='plain', help='plain|nophrase|twofield|twofield_np — 인덱스 이름 뒤에 :mode 로 개별 지정 가능'); ap.add_argument('--brief', action='store_true'); ap.add_argument('--diff', default='', help='질의별 비교 쌍 a,b (기본: 첫·마지막)')
    a = ap.parse_args()
    norm = lambda s: re.sub(r'\s+', '', s).lower()
    groups = json.load(open(a.synonyms, encoding='utf8'))['groups']; G = {}
    for g in groups:
        for t in g['terms']: G[norm(t)] = g['terms']
    Q = json.load(open(a.queries, encoding='utf8')); N = {d['id']: norm(d['title']) for d in docs()}
    def rel(q, expand):
        ms = []
        for w in q.split():
            variants = G.get(norm(w), [w]) if expand else [w]; fs = [matcher(v) for v in variants]; ms.append(lambda s, fs=fs: any(f(s) for f in fs))
        return {i for i, t in N.items() if all(m(t) for m in ms)}
    res = {}
    for ix in a.indices:
        rows = []
        for qq in Q:
            q = qq['q']; rs = rel(q, False); rx = rel(q, True); name, _, mode = ix.partition(':'); ids = [h[0] for h in search(name, q, 50, mode or a.mode)]
            def m(r):
                p10 = sum(1 for i in ids[:10] if i in r) / 10
                r50 = sum(1 for i in ids[:50] if i in r) / min(len(r), 50) if r else 0
                rr = next((1 / k for k, i in enumerate(ids, 1) if i in r), 0.0); return p10, r50, rr
            rows.append({'q': q, 'grp': qq['grp'], 'rel_single': len(rs), 'rel_expanded': len(rx), 'single': m(rs), 'expanded': m(rx), 'top50': ids})
        res[ix] = rows
    json.dump(res, open(a.out, 'w'), ensure_ascii=False)
    print('criterion  index     group    n   P@10   R@50   MRR')
    for crit in ['single', 'expanded']:
        for ix in a.indices:
            by = collections.defaultdict(list)
            for r in res[ix]: by[r['grp']].append(r[crit]); by['ALL'].append(r[crit])
            for g in ['exact', 'near', 'control', 'ALL']:
                v = by[g]; print(f'{crit:9s}  {ix:8s}  {g:8s} {len(v):2d}  {sum(x[0] for x in v)/len(v):.3f}  {sum(x[1] for x in v)/len(v):.3f}  {sum(x[2] for x in v)/len(v):.3f}')
    a0, a1 = a.diff.split(',') if a.diff else (a.indices[0], a.indices[-1])
    if a.brief: raise SystemExit
    print(f'\n질의별 ({a0} → {a1}); rel single/expanded; expanded R@50; single P@10 (희석 비용); 상위50 동일?')
    for ra, rb in zip(res[a0], res[a1]):
        same = ra['top50'] == rb['top50']
        print(f"  {ra['q']:12s} {ra['grp']:8s} rel {ra['rel_single']:5d}/{ra['rel_expanded']:5d}  R@50 {ra['expanded'][1]:.2f}→{rb['expanded'][1]:.2f}  P@10(single) {ra['single'][0]:.1f}→{rb['single'][0]:.1f}  P@10(exp) {ra['expanded'][0]:.1f}→{rb['expanded'][0]:.1f} {'same' if same else ''}")
