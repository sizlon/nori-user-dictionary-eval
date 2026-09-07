# nori-user-dictionary-eval

*[한국어 README](README.ko.md)*

A reproducible measurement of how Elasticsearch's Korean analyzer (**Nori**) fails on domain text with default settings, and how much a **user dictionary extracted from the corpus itself** recovers — on 183,240 Korean public-tender notice titles.

Headline (50 queries, P@10 / R@50 / MRR, loose relevance):

| Configuration | P@10 | R@50 | MRR |
|---|---|---|---|
| Nori defaults | 0.906 | 0.852 | 0.977 |
| Corpus-derived dictionary + index `mixed` / search `none` | **0.986** | **0.979** | **1.000** |

Changing `decompound_mode` alone changed nothing. The dictionary did the work; a separate search analyzer added the last step. Full write-up: [English](https://sizlon.io/en/notes/korean-tokenizer/) · [Korean](https://sizlon.io/notes/korean-tokenizer/).

This is a measurement snapshot (September 2026), published as used. It is not maintained — the repository is archived. Code comments are in Korean; this README covers everything needed to run it.

## What it shows

**Finding 1 — the same word segments differently by context.** Of 2,273 words occurring 30+ times in the corpus, 382 (16.8%) segment in two or more ways depending on their neighbours; 8.5% of those words' occurrences sit in a minority segmentation and silently miss queries analysed the majority way. Example: 소액수의 → 소액+수 (1,988) · 액수 (352) · 소액+수의 (120).

**Finding 2 — characters disappear.** Pieces tagged as prefix/suffix/particle are dropped: 맨홀 (manhole) → 홀 (hole), 재공고 (re-announcement) → 공고, 단가계약 → 다+이+계약, 전자견적 → 자견.

**The counter-example.** A wrong-but-consistent segmentation still retrieves (단가계약 scores 1.0 on defaults). Retrieval dies only when segmentation varies by context, or when what survives collides with a common token.

**The fix.** Extract the dictionary from corpus statistics (2,147 entries, no human input), hand-segment the lossy ones (19 entries), index with `decompound_mode: mixed`, search with `none`.

## Contents

| File | What |
|---|---|
| `corpus.jsonl.gz` | 183,240 notice titles (`id, title, div, agency, date, method`), de-duplicated by notice number from KONEPS bid-opening data, Feb–Aug 2026 |
| `Dockerfile` | Elasticsearch 9.5.2 + `analysis-nori` |
| `common.py` | index settings (analyzers, dictionary), bulk indexing, `_analyze`, `match` query |
| `make_indices.py` | builds `base` · `mixed` · `tuned2` · `tuned2s` |
| `diagnose.py` | Findings 1 and 2; dictionary-candidate extraction |
| `build_rules.py` | candidates → Nori `user_dictionary_rules` (+ 19 manual entries in `MANUAL`) |
| `eval2.py` | 50 queries × 2 relevance rules × P@10 · R@50 · MRR |
| `queries.json` | the 50 queries, grouped `lossy` / `inconsistent` / `control` |
| `user_rules.json` · `user_rules2.json` · `user_rules3.json` | dictionary: automatic only · + manual (used) · + auto-segmented lossy entries (no gain) |
| `dict_candidates.json` · `seg_inconsistency.json` · `word_freq.json` | diagnostics output |
| `results.json` | metrics for 4 configurations × 50 queries × 2 rules |
| `index-settings/*.json` | the exact analysis settings and mappings of each index, as dumped from the cluster |
| `synonyms.json` · `queries_syn.json` · `make_syn_index.py` · `probe_syn_placement.py` · `eval_syn.py` · `user_rules4.json` · `results_syn.json` | synonym experiment (2026-09-07), see the section below; `make_indices.py --only tuned4` builds its control index |

## Run it (about 10 minutes)

Requirements: Docker, Python 3 with `requests`.

```bash
docker build -t es-nori:9.5.2 .
docker run -d --name es-nori -p 127.0.0.1:9201:9200 \
  -e discovery.type=single-node -e xpack.security.enabled=false -e xpack.ml.enabled=false \
  -e ES_JAVA_OPTS="-Xms2g -Xmx2g" es-nori:9.5.2
curl -s localhost:9201/_cluster/health        # wait for "green"

python3 make_indices.py --only base            # 183,240 docs, ~6 s
python3 diagnose.py --index base               # ~3 min → dict_candidates.json, seg_inconsistency.json, word_freq.json
python3 build_rules.py                         # → user_rules2.json (2,155 rules: 2,147 automatic + 19 manual)
python3 make_indices.py --only mixed,tuned2,tuned2s
python3 eval2.py base mixed tuned2 tuned2s --out results_repro.json
```

Expected output of `diagnose.py`:

```
titles 183240 | words >=30: 2273 | inconsistently segmented: 382 (16.8%)
occurrences in minority segmentation: 7322/86021 = 8.5%
dictionary candidates (split or lossy, freq>=30): 2147
```

Expected `ALL` rows of `eval2.py`:

```
strict     base      ALL           0.830  0.799  0.920
strict     mixed     ALL           0.834  0.788  0.920
strict     tuned2    ALL           0.904  0.873  0.947
strict     tuned2s   ALL           0.908  0.884  0.947
loose      base      ALL           0.906  0.852  0.977
loose      mixed     ALL           0.906  0.838  0.977
loose      tuned2    ALL           0.982  0.958  1.000
loose      tuned2s   ALL           0.986  0.979  1.000
```

`results_repro.json` should equal `results.json` query by query (timing fields aside). To see a single word:

```bash
curl -s localhost:9201/base/_analyze   -H 'content-type: application/json' -d '{"analyzer":"ko","text":"맨홀 정비"}'      # → 홀, 정비
curl -s localhost:9201/tuned2/_analyze -H 'content-type: application/json' -d '{"analyzer":"ko","text":"단가계약"}'      # → 단가계약, 단가, 계약
curl -s localhost:9201/tuned2s/_analyze -H 'content-type: application/json' -d '{"analyzer":"ko_search","text":"상수도관 교체"}'  # → 상수도관, 교체
```

## Method

- **Ground truth is automatic**, not human-judged: *strict* — the title with spaces removed contains the query with spaces removed as a substring; *loose* — every word of the query appears in the title. Both configurations are judged by the same rule, so the differences are trustworthy and the absolute numbers should be read down.
- **The dictionary was extracted without looking at the queries.** Every title is analysed with the default analyzer; each token is attributed to its surface word by offset; words occurring 30+ times that split into 2+ tokens or lose characters become candidates. Words that split cleanly get a rule `word part1 part2` (so `mixed` mode emits both the whole and the parts); words that lose characters become a single token. 19 lossy entries (맨홀, 재선충병, 단가계약 단가 계약, …) were given segmentations by hand — the "80% automatic, 20% by hand" ratio measured here.
- **The golden set is centred on words the diagnostics flagged**, so the 15 control queries (things the default already handled) are the honest floor: they moved from 0.947 to 1.000.
- Queries are `match` with the default `OR` operator — what most teams ship first.

## Limits

- Titles only (median 27 characters). Longer documents dilute the effect.
- Automatic relevance misses paraphrases and counts accidental substring hits.
- No synonyms (RFP ↔ 제안요청서 and the like) — that is the next experiment.
- A random 100-query set would move less than this golden set; the control group shows the lower bound.

## Synonyms (added 2026-09-07)

Twenty spelling/acronym pairs (`synonyms.json`) on a `synonym_graph` filter in the **search** analyzer only, on top of the same dictionary (`make_syn_index.py`). A document counts as relevant if it contains any spelling (`eval_syn.py`, "expanded"). On the 24 queries that contain such a pair:

| Setup | P@10 | R@50 | MRR |
|---|---|---|---|
| dictionary 2,163, no synonyms (`tuned4`) | 0.750 | 0.586 | 0.878 |
| dictionary 2,155 + 25 synonyms (`syn`) | 0.767 | 0.926 | 0.923 |
| dictionary 2,163 + 26 synonyms (`syn3`) | **0.921** | **0.955** | **1.000** |

Ten control queries: identical top 50 in every setup. Behind the index analyzer (decompound mixed) Elasticsearch rejects the rules; `lenient` drops them silently (`probe_syn_placement.py`). A synonym spelling that splits into several tokens becomes a phrase query and pushes the original-spelling documents out, so those spellings go into the user dictionary first — that is the +8 in `user_rules4.json`. Pairs that are merely close in meaning gained nothing at R@50. Reproduce: `python3 make_indices.py --only tuned4 && python3 make_syn_index.py --name syn && python3 make_syn_index.py --name syn3 --rules user_rules4.json && python3 eval_syn.py tuned4 syn syn3`.

## Data and license

Code: MIT (see `LICENSE`). The corpus is derived from public bid-opening records of KONEPS (나라장터), obtained through the Korean government open-data API (`apis.data.go.kr`, PubDataOpnStdService); it contains notice titles and agency names only, no bidder information. Redistributed here for reproducibility under the open-data terms of the source.

Made by [Sizlon](https://sizlon.io/en/) — Korean search, RAG retrieval and data extraction, from someone who ran it in production.
