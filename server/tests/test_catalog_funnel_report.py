import json
from scripts.catalog_funnel_report import summarize

def test_report_deduplicates_sequences_and_does_not_call_incomplete_flows_abandoned():
    flow='a82270f9-1287-4df5-81aa-996ed532942b'
    def row(seq,event,**extra):return '[catalog_funnel] '+json.dumps(dict(flow_id=flow,sequence=seq,event=event,elapsed_ms=1000,rank=0,result_count=0,**extra))
    lines=[row(1,'opened'),row(2,'search_ready'),row(2,'search_ready'),row(3,'submitted')]
    result=summarize(lines)
    assert result['flows_opened']==result['flows_submitted']==result['empty_searches']==1
    assert result['searches']==1 and result['flows_abandoned']==0
    assert summarize([lines[0]])['flows_unfinished_or_unobserved']==1
    assert result['median_submit_ms']==1000
import pytest

pytestmark = pytest.mark.no_db
