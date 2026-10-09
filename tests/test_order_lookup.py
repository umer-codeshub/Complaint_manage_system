from pathlib import Path
from tools.order_lookup import lookup_order, OrderDataError
from services.complaint_service import ROOT

def test_known_order_is_verified():
    r = lookup_order('DEMO-1001','ayesha@example.com',ROOT/'data/sample_orders.csv')
    assert r['verified'] and r['order']['tracking_status'] == 'Delayed at sorting center'
    assert 'FICTIONAL' in r['notice']

def test_invalid_order_id_not_found():
    assert lookup_order('INVALID','ayesha@example.com',ROOT/'data/sample_orders.csv')['status'] == 'not_found'

def test_wrong_customer_identifier_hides_record():
    r = lookup_order('DEMO-1001','stranger@example.com',ROOT/'data/sample_orders.csv')
    assert not r['verified'] and 'order' not in r

def test_contradictory_order_status(tmp_path):
    source = (ROOT/'data/sample_orders.csv').read_text()
    f = tmp_path/'orders.csv'
    f.write_text(source.replace('in_transit,Delayed at sorting center','delivered,Delayed at sorting center'))
    assert lookup_order('DEMO-1001','ayesha@example.com',f)['status'] == 'contradictory'

def test_missing_file_error(tmp_path):
    try:
        lookup_order('DEMO-1001','ayesha@example.com',tmp_path/'missing.csv')
    except OrderDataError:
        pass
    else:
        assert False, 'Expected OrderDataError'
