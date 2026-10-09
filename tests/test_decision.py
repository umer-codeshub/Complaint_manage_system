from datetime import date
from agents.decision import make_decision
from agents.schemas import ComplaintAnalysis
from tools.order_lookup import lookup_order
from tools.policy_lookup import lookup_policy
from services.complaint_service import ROOT

def analysis(category='late_delivery', priority='Medium'):
    return ComplaintAnalysis(category=category,summary='Customer states an order problem.',sentiment='Frustrated',
        severity=priority,priority=priority,priority_reason='Customer needs a status update.',escalation_recommended=False)

def order(n, email):
    return lookup_order(n,email,ROOT/'data/sample_orders.csv')

def policy(category):
    return lookup_policy(category,ROOT/'data/company_policies.json')

def test_delayed_order_and_twice_ignored_escalates():
    d=make_decision(analysis(), 'Ten days late and contacted support twice.',
                    order('DEMO-1001','ayesha@example.com'),policy('late_delivery'))
    assert d.escalated and 'unanswered' in d.reason

def test_critical_harm_requires_escalation():
    d=make_decision(analysis(priority='Critical'),'Item caused an injury',
        order('DEMO-1005','hira@example.com'), policy('late_delivery'))
    assert d.escalated and 'harm' in d.reason

def test_missing_policy_escalates():
    assert make_decision(analysis(),'Status update request',order('DEMO-1001','ayesha@example.com'),{'found':False}).escalated

def test_no_order_prevents_resolution():
    d=make_decision(analysis(),'Where is it?',{'verified':False,'status':'not_found','reason':'No matching order'},policy('late_delivery'))
    assert d.outcome == 'Request additional information'

def test_refund_outside_allowed_period():
    d=make_decision(analysis('refund_request'),'I want a refund',
        order('DEMO-1003','sana@example.com'),policy('refund_request'), date(2026,10,9))
    assert d.escalated and '14 days' in d.reason

def test_damaged_product_needs_evidence():
    d=make_decision(analysis('damaged_product'),'Broken item',
        order('DEMO-1002','ali@example.com'),policy('damaged_product'))
    assert d.escalated and d.outcome == 'Request additional information'

def test_safe_recommendation_available():
    d=make_decision(analysis('delivery_delay'),'Tracking delay',
        order('DEMO-1009','maria@example.com'),policy('delivery_delay'))
    assert not d.escalated and 'recommendation' in d.outcome

def test_high_value_escalated():
    d=make_decision(analysis(),'Question about the order',
        order('DEMO-1006','hassan@example.com'),policy('late_delivery'))
    assert d.escalated
