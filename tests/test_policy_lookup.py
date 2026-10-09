from services.complaint_service import ROOT
from tools.policy_lookup import lookup_policy, PolicyDataError

def test_verified_demo_policy():
    r=lookup_policy('late_delivery',ROOT/'data/company_policies.json')
    assert r['found'] and r['policy']['id']=='P-001'

def test_policy_unavailable():
    assert not lookup_policy('unknown_category',ROOT/'data/company_policies.json')['found']

def test_malformed_json(tmp_path):
    p=tmp_path/'bad.json'; p.write_text('{')
    try:
        lookup_policy('late_delivery',p)
    except PolicyDataError:
        pass
    else:
        assert False
