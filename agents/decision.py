"""Conservative business rules: AI output cannot grant business privileges."""
import re
from datetime import date
from agents.schemas import Decision, ComplaintAnalysis

HARM_RE = re.compile(r'\b(injur(?:y|ed)|fire|burn(?:ed|s)?|unsafe|dangerous|hospital|electrocut(?:ed|ion))\b', re.I)
REPEATED_RE = re.compile(r'\b(twice|two times|three times|multiple times|again and again|no response|ignored)\b', re.I)
REFUND_RE = re.compile(r'\b(refund|money back|return)\b', re.I)

def make_decision(analysis: ComplaintAnalysis, complaint: str, order_result: dict,
                  policy_result: dict, today: date | None = None) -> Decision:
    today = today or date.today()
    if not order_result.get('verified'):
        status = order_result.get('status', '')
        if status in ('contradictory', 'incomplete'):
            return Decision(outcome='Escalate to human support', reason='Order record cannot be trusted',
                suggested_action='Human agent must inspect records before further action.',
                escalated=True, escalation_reason=order_result.get('reason', 'Verification failure'))
        return Decision(outcome='Request additional information', reason='Order ownership is not verified',
            suggested_action='Ask customer to verify order ID and registered email. Do not disclose order details.',
            escalated=True, escalation_reason=order_result.get('reason', 'Verification missing'))
    if not policy_result.get('found'):
        return Decision(outcome='Escalate to human support', reason='Applicable policy is unavailable',
            suggested_action='Human agent must consult approved company policy.',
            escalated=True, escalation_reason='No verified policy')
    order = order_result['order']
    if (HARM_RE.search(complaint) or analysis.priority == 'Critical'
            or analysis.severity == 'Critical'):
        return Decision(outcome='Escalate to human support', reason='Potential serious harm or critical priority',
            suggested_action='Urgent human review; do not promise any remedy.',
            escalated=True, escalation_reason='Critical safety/customer concern')
    if float(order['order_amount']) >= 1000:
        return Decision(outcome='Escalate to human support', reason='High-value dispute threshold',
            suggested_action='Human reviewer checks order and documents a decision.',
            escalated=True, escalation_reason='Order amount ≥ 1000 demo currency units')
    if REPEATED_RE.search(complaint):
        return Decision(outcome='Escalate to human support', reason='Possible repeated unanswered support requests',
            suggested_action='Escalate to a senior support agent for review.',
            escalated=True, escalation_reason='Repeated/unanswered support contacts')
    if REFUND_RE.search(complaint) or analysis.category.value == 'refund_request':
        if not order.get('actual_delivery_date'):
            return Decision(outcome='Request additional information', reason='Refund clock cannot be verified without delivery date',
                suggested_action='Human support must verify delivery and eligibility; refund not approved.',
                escalated=True, escalation_reason='Delivery evidence missing')
        elapsed = (today - date.fromisoformat(order['actual_delivery_date'])).days
        if elapsed > 14:
            return Decision(outcome='Escalate to human support', reason='Demo refund period of 14 days has passed',
                suggested_action='Human agent review; do not offer an exception or refund approval.',
                escalated=True, escalation_reason='Refund request beyond verified policy period')
    if analysis.category.value in {'order_cancellation', 'damaged_product', 'incorrect_item', 'missing_order'}:
        return Decision(outcome='Request additional information', reason='Needs verification by support staff',
            suggested_action='Collect relevant evidence and route to support; no irreversible changes.',
            escalated=True, escalation_reason='Further evidence / human authorization required')
    if analysis.escalation_recommended or analysis.priority == 'High':
        return Decision(outcome='Escalate to human support', reason='AI triage indicates escalation',
            suggested_action='Assign a human support agent.', escalated=True,
            escalation_reason='High priority or AI triage recommendation')
    return Decision(outcome='Resolve with recommendation', reason='Verified demo order and applicable demo policy available',
        suggested_action='Communicate relevant policy and offer human review if unresolved; no order changes.',
        escalated=False)
