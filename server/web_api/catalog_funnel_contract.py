"""Dependency-free allowlist for requester UX journal events."""
from uuid import UUID

EVENTS={'opened','search_ready','result_selected','service_selected','service_changed','catalog_selected','fallback_selected','submitted','abandoned'}
KEYS={'flow_id','sequence','event','elapsed_ms','rank','result_count'}

def validate_metric(data):
    if not isinstance(data,dict) or set(data)!=KEYS: raise ValueError('contract')
    if not isinstance(data['flow_id'],str) or str(UUID(data['flow_id']))!=data['flow_id']: raise ValueError('flow')
    if data['event'] not in EVENTS: raise ValueError('event')
    for key,lower,upper in [('sequence',1,10000),('elapsed_ms',0,86400000),('rank',0,50),('result_count',0,50)]:
        if type(data[key]) is not int or not lower<=data[key]<=upper: raise ValueError('range')
    return data
