"""Summarize exported catalog UX journal messages without identities or queries."""
import argparse,json,statistics,sys
from pathlib import Path
from collections import Counter

def summarize(lines):
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'server'))
    from web_api.catalog_funnel_contract import validate_metric
    flows={};rejected=0
    for line in lines:
        if '[catalog_funnel] ' not in line:continue
        try:event=validate_metric(json.loads(line.split('[catalog_funnel] ',1)[1]))
        except (ValueError,TypeError,KeyError):rejected+=1;continue
        flows.setdefault(event['flow_id'],{})[event['sequence']]=event
    events=[e for rows in flows.values() for e in rows.values()]
    counts=Counter(e['event'] for e in events)
    opened={key for key,rows in flows.items() if any(e['event']=='opened' for e in rows.values())}
    submitted={key for key,rows in flows.items() if any(e['event']=='submitted' for e in rows.values())}
    abandoned={key for key,rows in flows.items() if any(e['event']=='abandoned' for e in rows.values())}-submitted
    searches=[e for e in events if e['event']=='search_ready']
    ranked=[e for e in events if e['event']=='result_selected' and e['rank']>0]
    durations=[e['elapsed_ms'] for e in events if e['event']=='submitted']
    return {'source':'best_effort_client_measurements','flows_opened':len(opened),'flows_submitted':len(submitted&opened),
        'flows_abandoned':len(abandoned&opened),'flows_unfinished_or_unobserved':len(opened-submitted-abandoned),
        'searches':len(searches),'empty_searches':sum(e['result_count']==0 for e in searches),
        'ranked_selections':len(ranked),'selections_in_top5':sum(e['rank']<=5 for e in ranked),
        'service_changes':counts['service_changed'],'median_submit_ms':statistics.median(durations) if durations else None,
        'rejected_records':rejected,'events':dict(counts)}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('journal',type=Path)
    args=parser.parse_args();print(json.dumps(summarize(args.journal.read_text(encoding='utf-8').splitlines()),indent=2))
