"""토크나이저 실험 공통 코드 (sizlon.io/notes/korean-tokenizer/, 2026-09).

ES = Elasticsearch 9.5.2 + analysis-nori 단일 노드 (Dockerfile.es-nori):
  docker build -t es-nori:9.5.2 -f Dockerfile.es-nori .
  docker run -d -p 127.0.0.1:9201:9200 -e discovery.type=single-node -e xpack.security.enabled=false es-nori:9.5.2

CORPUS = corpus.jsonl.gz (gzip), 한 줄에 {"id","title","div","agency","date","method"}.
나라장터 개찰 공개 데이터(조달청 낙찰정보 API 의 일별 jsonl.gz)에서 공고번호로 중복 제거:

    seen = {}
    for rec in rows_from_all_files():            # 응찰 행 1,746만 건
        k = rec["bidNtceNo"]
        if k in seen: continue
        seen[k] = {"id": k, "title": rec["bidNtceNm"], "div": rec["bsnsDivNm"],
                   "agency": rec["ntceInsttNm"], "date": rec["opengDate"], "method": rec["cntrctCnclsMthdNm"]}
    # → 183,240건 (용역 111,756 · 공사 71,484)

인덱스 4벌: base(discard) · mixed · tuned2(사전, 색인=검색) · tuned2s(사전, 색인 mixed·검색 none).
tuned2s 는 analyzer_settings() 결과에 검색 분석기를 덧붙인다 — make_indices.py 의 tuned2s_body().
"""
import json, requests
ES='http://localhost:9201'
import os
CORPUS=os.environ.get('CORPUS', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'corpus.jsonl.gz'))
def docs():
    import gzip
    opener = gzip.open if CORPUS.endswith('.gz') else open
    with opener(CORPUS, 'rt', encoding='utf8') as f:
        for line in f: yield json.loads(line)
def analyzer_settings(decompound='discard', user_rules=None, synonyms=None):
    tok={'type':'nori_tokenizer','decompound_mode':decompound}
    if user_rules: tok['user_dictionary_rules']=user_rules
    # nori_part_of_speech 는 기본 stoptags(조사·어미·기호 등)를 그대로 쓴다 — Lucene 10 에서 태그 열거형이 바뀌어 명시 목록이 거부됨
    filters=['nori_readingform','lowercase','nori_part_of_speech']
    fdefs={}
    if synonyms:
        fdefs['syn']={'type':'synonym_graph','synonyms':synonyms}
        filters.append('syn')
    return {'settings':{'index':{'number_of_shards':1,'number_of_replicas':0},'analysis':{'tokenizer':{'ko_tok':tok},'filter':fdefs,'analyzer':{'ko':{'type':'custom','tokenizer':'ko_tok','filter':filters}}}},
            'mappings':{'properties':{'title':{'type':'text','analyzer':'ko'},'div':{'type':'keyword'},'agency':{'type':'keyword'},'date':{'type':'keyword'}}}}
def create(name, body):
    requests.delete(f'{ES}/{name}')
    r=requests.put(f'{ES}/{name}',json=body); r.raise_for_status(); return r.json()
def bulk(name, batch=5000):
    buf=[]; n=0
    def flush():
        nonlocal buf,n
        if not buf: return
        r=requests.post(f'{ES}/_bulk',data=('\n'.join(buf)+'\n').encode('utf8'),headers={'Content-Type':'application/x-ndjson'}); r.raise_for_status()
        if r.json().get('errors'): raise SystemExit('bulk errors: '+str([i for i in r.json()['items'] if 'error' in i['index']][:2]))
        n+=len(buf)//2; buf=[]
    for d in docs():
        buf.append(json.dumps({'index':{'_index':name,'_id':d['id']}})); buf.append(json.dumps({k:d[k] for k in ('title','div','agency','date')},ensure_ascii=False))
        if len(buf)>=batch*2: flush()
    flush(); requests.post(f'{ES}/{name}/_refresh'); return n
def analyze(name, texts):
    r=requests.post(f'{ES}/{name}/_analyze',json={'analyzer':'ko','text':texts}); r.raise_for_status(); return r.json()['tokens']
def search(name, q, size=50, operator='or'):
    r=requests.post(f'{ES}/{name}/_search',json={'size':size,'_source':['title'],'query':{'match':{'title':{'query':q,'operator':operator}}}}); r.raise_for_status()
    return [(h['_id'],h['_source']['title'],h['_score']) for h in r.json()['hits']['hits']]
