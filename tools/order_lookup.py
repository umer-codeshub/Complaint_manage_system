"""Deterministic lookups in an explicitly fictional CSV database."""
import csv
from datetime import date
from pathlib import Path

REQUIRED = {'order_id','customer_id','customer_name','customer_email','order_date',
            'expected_delivery_date','actual_delivery_date','order_status',
            'tracking_status','product_name','order_amount','refund_status'}

class OrderDataError(Exception):
    pass

def lookup_order(order_id: str, customer_email: str, path: str | Path) -> dict:
    """Returns only owned/verified records; rejects ambiguous or inconsistent data."""
    if not order_id or not customer_email:
        return {'verified': False, 'reason': 'Missing order ID or email', 'status': 'missing_identifier'}
    try:
        with open(path, newline='', encoding='utf-8-sig') as handle:
            reader = csv.DictReader(handle)
            if not REQUIRED.issubset(reader.fieldnames or []):
                raise OrderDataError('Required CSV columns are missing')
            rows = [r for r in reader if r['order_id'].strip().casefold() == order_id.strip().casefold()]
    except (OSError, UnicodeError, csv.Error) as exc:
        raise OrderDataError('Order database unavailable') from exc
    if not rows:
        return {'verified': False, 'reason': 'No matching demonstration order', 'status': 'not_found'}
    if len(rows) != 1:
        return {'verified': False, 'reason': 'Duplicate order ID in demonstration database', 'status': 'contradictory'}
    order = {k: str(v).strip() for k,v in rows[0].items() if k in REQUIRED}
    if not all(order.get(k) for k in REQUIRED - {'actual_delivery_date'}):
        return {'verified': False, 'reason': 'Incomplete demonstration order', 'status': 'incomplete'}
    if order['customer_email'].casefold() != customer_email.strip().casefold():
        # Do not disclose another person's record on failed identifier verification.
        return {'verified': False, 'reason': 'Order identifier and customer email do not match', 'status': 'mismatch'}
    try:
        for field in ('order_date','expected_delivery_date'):
            date.fromisoformat(order[field])
        if order['actual_delivery_date']:
            date.fromisoformat(order['actual_delivery_date'])
        if float(order['order_amount']) < 0:
            raise ValueError('Negative amount')
    except ValueError:
        return {'verified': False, 'reason': 'Invalid dates or amount in order record', 'status': 'contradictory'}
    if ((order['order_status'].lower() == 'delivered') != bool(order['actual_delivery_date'])):
        return {'verified': False, 'reason': 'Contradictory delivery status', 'status': 'contradictory'}
    return {'verified': True, 'status': 'verified', 'order': order,
            'notice': 'FICTIONAL DEMONSTRATION ORDER — not a live store integration'}
