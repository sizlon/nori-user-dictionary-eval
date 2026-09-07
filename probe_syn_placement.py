"""동의어 필터를 어디에 두느냐 프로브(2026-09-07). 결과: 색인 분석기(mixed) 뒤 → ES 400 거부, lenient=true → 조용히 규칙 폐기, 검색 분석기(none) 뒤 → 정상."""
import json, requests
from common import ES, analyzer_settings
from make_indices import tuned2s_body
rules = json.load(open('user_rules2.json', encoding='utf8')); syn = ['rfp, 제안요청서', '누리집, 홈페이지, 웹사이트']
def analyze(ix, an, s): return [(t['token'], t['position'], t.get('positionLength', 1)) for t in requests.post(f'{ES}/{ix}/_analyze', json={'analyzer': an, 'text': s}).json()['tokens']]
b = analyzer_settings('mixed', user_rules=rules, synonyms=syn)
r = requests.put(ES + '/probe_a', json=b); print('A 색인(mixed)+syn:', r.status_code, r.json()['error']['caused_by']['caused_by']['reason'][:80] if r.status_code == 400 else '')
b['settings']['analysis']['filter']['syn']['lenient'] = True
r = requests.put(ES + '/probe_a2', json=b); print('A2 lenient:', r.status_code, analyze('probe_a2', 'ko', '제안요청서 작성'))
b = tuned2s_body(rules); an = b['settings']['analysis']; an['filter']['syn'] = {'type': 'synonym_graph', 'synonyms': syn}; an['analyzer']['ko_search']['filter'].append('syn')
r = requests.put(ES + '/probe_b', json=b); print('B 검색(none)+syn:', r.status_code, analyze('probe_b', 'ko_search', '제안요청서 작성'))
for n in ['probe_a', 'probe_a2', 'probe_b']: requests.delete(f'{ES}/{n}')
