"""인덱스 4벌을 만든다: base(discard) · mixed · tuned2(사전, 색인=검색) · tuned2s(사전, 색인 mixed·검색 none).
사용: python3 make_indices.py [--prefix m_] [--rules user_rules2.json] [--only base,mixed,...]
같은 이름의 인덱스는 지우고 다시 만든다(결정적이라 결과는 같다). 보존본을 건드리기 싫으면 --prefix.
"""
import argparse, json, time
from common import ES, analyzer_settings, create, bulk, requests

def tuned2s_body(rules):
    body = analyzer_settings('mixed', user_rules=rules)
    an = body['settings']['analysis']
    an['tokenizer']['ko_tok_search'] = {'type': 'nori_tokenizer', 'decompound_mode': 'none', 'user_dictionary_rules': rules}
    an['analyzer']['ko_search'] = {'type': 'custom', 'tokenizer': 'ko_tok_search', 'filter': ['nori_readingform', 'lowercase', 'nori_part_of_speech']}
    body['mappings']['properties']['title']['search_analyzer'] = 'ko_search'
    return body

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--prefix', default=''); ap.add_argument('--rules', default='user_rules2.json'); ap.add_argument('--only', default='base,mixed,tuned2,tuned2s')
    a = ap.parse_args()
    rules = json.load(open(a.rules, encoding='utf8')) if any(x.startswith('tuned') for x in a.only.split(',')) else None
    bodies = {'base': lambda: analyzer_settings('discard'), 'mixed': lambda: analyzer_settings('mixed'),
              'tuned2': lambda: analyzer_settings('mixed', user_rules=rules), 'tuned2s': lambda: tuned2s_body(rules)}
    for name in a.only.split(','):
        full = a.prefix + name
        create(full, bodies[name]()); t = time.time(); n = bulk(full)
        print(f'{full}: {n} docs in {time.time()-t:.1f}s')
    print(requests.get(ES + '/_cat/indices?v&h=index,docs.count,store.size&s=index').text)
