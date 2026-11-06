"""Evaluate fixed nonpersonal search examples against an authorized public snapshot."""
import argparse
import json
import statistics
import sys
from pathlib import Path
from time import perf_counter

QUERIES = ("принтер", "застряла бумага", "принтр не печатает", "ghbynth", "не работает",
           "Directum", "не могу войти", "электронный бюджет", "еис", "нет интернета", "не работает космопульт")

def benchmark(catalog):
    root=Path(__file__).resolve().parents[1]
    sys.path.insert(0,str(root/'server'))
    from tickets.service_catalog_search import search_public_catalog
    rows=[]
    for query in QUERIES:
        started=perf_counter()
        result=search_public_catalog(catalog,query)['results']
        rows.append({'query':query,'elapsed_ms':round((perf_counter()-started)*1000,2),
                     'results':len(result),'services':len({r['offering_full_code'] for r in result}),
                     'top5':[{'title':r['title'],'offering':r['offering_full_code'],'kind':r['result_kind']} for r in result[:5]]})
    return {'examples':rows,'median_ms':statistics.median(row['elapsed_ms'] for row in rows)}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('snapshot',type=Path)
    args=parser.parse_args()
    payload=json.loads(args.snapshot.read_text(encoding='utf-8'))
    print(json.dumps(benchmark(payload.get('catalog',payload)),ensure_ascii=True,indent=2))
