"""동의어 인덱스: tuned2s 와 같은 색인(사전 2,155 + mixed) 에 검색 분석기 ko_search(decompound none) 뒤로 synonym_graph 를 붙인다.
색인 데이터는 tuned2s 와 동일 — 다른 것은 검색 분석기 하나. 사용: python3 make_syn_index.py [--name syn] [--rules user_rules2.json] [--synonyms synonyms.json] [--types exact,near] [--two-field]
  syn  = user_rules2 + 동의어 25(검색 분석기)   syn3 = --rules user_rules4.json --name syn3 → 동의어 26   syn2 = --two-field --name syn2
왜 검색 쪽인가: 색인 분석기(mixed) 뒤에 붙이면 규칙 어절이 겹치는 위치의 여러 토큰으로 분석되어 ES 가 거부한다(probe_syn_placement.py).
"""
import argparse, json, time
from common import ES, create, bulk, requests
from make_indices import tuned2s_body

def syn_rules(path, types, rules_file='user_rules2.json'):
    """requires 가 붙은 군(무정전전원장치↔ups)은 그 사전 파일로 만들 때만 넣는다 — 사전 없이는 ES 가 규칙을 거부한다."""
    g = json.load(open(path, encoding='utf8'))['groups']
    return [', '.join(x['terms']) for x in g if x['type'] in types and x.get('requires', rules_file) == rules_file]

def syn_body(rules, synonyms):
    body = tuned2s_body(rules); an = body['settings']['analysis']
    an['filter']['syn'] = {'type': 'synonym_graph', 'synonyms': synonyms}
    an['analyzer']['ko_search']['filter'].append('syn')
    return body

def syn2_body(rules, synonyms):
    """두 필드: title 은 tuned2s 그대로(동의어 없음), title.syn 은 검색 분석기에만 동의어. 질의에서 둘을 should 로 묶고 원표기 필드에 가중치."""
    body = tuned2s_body(rules); an = body['settings']['analysis']
    an['filter']['syn'] = {'type': 'synonym_graph', 'synonyms': synonyms}
    an['analyzer']['ko_search_syn'] = dict(an['analyzer']['ko_search'], filter=an['analyzer']['ko_search']['filter'] + ['syn'])
    body['mappings']['properties']['title']['fields'] = {'syn': {'type': 'text', 'analyzer': 'ko', 'search_analyzer': 'ko_search_syn'}}
    return body

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--name', default='syn'); ap.add_argument('--rules', default='user_rules2.json'); ap.add_argument('--synonyms', default='synonyms.json'); ap.add_argument('--types', default='exact,near'); ap.add_argument('--two-field', action='store_true', help='syn2: title(무동의어)+title.syn')
    a = ap.parse_args()
    rules = json.load(open(a.rules, encoding='utf8')); syns = syn_rules(a.synonyms, a.types.split(','), a.rules)
    print(f'{len(syns)} synonym rules'); create(a.name, (syn2_body if a.two_field else syn_body)(rules, syns)); t = time.time(); n = bulk(a.name)
    print(f'{a.name}: {n} docs in {time.time()-t:.1f}s')
