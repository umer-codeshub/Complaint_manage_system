"""End-to-end orchestrator with conservative fail-closed AI fallbacks."""
import re
from pathlib import Path
from agents.crew import AIUnavailable, ComplaintCrew
from agents.decision import make_decision
from agents.schemas import ComplaintAnalysis, ComplaintInput, DraftOutput
from tools.order_lookup import lookup_order, OrderDataError
from tools.policy_lookup import lookup_policy, PolicyDataError
from tools.ticket_generator import TicketStore

ROOT = Path(__file__).resolve().parent.parent


def fallback_analysis(complaint: str) -> ComplaintAnalysis:
    lowered = complaint.casefold()
    patterns = [('damaged_product', r'broken|damag|crack'), ('incorrect_item', r'wrong|incorrect item'),
                ('missing_order', r'missing|not arrived|never arrived|lost'),
                ('refund_request', r'refund|money back'), ('order_cancellation', r'cancel'),
                ('unresponsive_support', r'unresponsive|support ignored|no response'),
                ('late_delivery', r'late|overdue|delayed|delay')]
    category = next((c for c, p in patterns if re.search(p, lowered)), 'other')
    critical = bool(re.search(r'\b(injury|unsafe|fire|hospital|dangerous)\b', lowered))
    return ComplaintAnalysis(category=category, summary='Customer reports: ' + complaint[:450],
        sentiment='Unverified', severity='Critical' if critical else 'High',
        priority='Critical' if critical else 'High',
        priority_reason='Conservative rule-based assessment; AI triage unavailable.',
        escalation_recommended=True)


def fallback_draft(data, decision) -> DraftOutput:
    # Never echo arbitrary customer text as an outbound directive.
    return DraftOutput(subject='Your complaint is awaiting support review',
        body=(f'Dear {data.customer_name},\n\n'
              'Thank you for contacting our support team. We acknowledge your complaint. '
              'Before taking action, a support representative will need to review the details '
              'and verify the order against the registered email address. '
              f'Our next step: {decision.suggested_action}\n\n'
              'No refund, cancellation, or delivery change has been authorized.\n\n'
              'Best regards,\nCustomer Support Team'))


def process_complaint(data: ComplaintInput, store: TicketStore, groq_api_key: str,
                      groq_model: str = 'openai/gpt-oss-120b',
                      orders_path=None, policies_path=None, ai=None) -> dict:
    order_path = orders_path or ROOT / 'data' / 'sample_orders.csv'
    policy_path = policies_path or ROOT / 'data' / 'company_policies.json'
    warnings = []
    try:
        order_result = lookup_order(data.order_id, str(data.customer_email), order_path)
    except OrderDataError:
        order_result = {'verified': False, 'status': 'contradictory', 'reason': 'Order reference tool error'}
        warnings.append('Order database is unavailable; manual verification required.')
    agent = ai if ai is not None else ComplaintCrew(groq_api_key, groq_model)
    ai_analysis = False
    try:
        analysis = agent.analyze(data)
        ai_analysis = True
    except (AIUnavailable, Exception):
        analysis = fallback_analysis(data.complaint)
        warnings.append('Groq/CrewAI unavailable: conservative rule-based triage used (NOT an AI analysis).')
    try:
        policy_result = lookup_policy(analysis.category.value, policy_path)
    except PolicyDataError:
        policy_result = {'found': False, 'reason': 'Policy tool error'}
        warnings.append('Policy file unavailable; manual review required.')
    decision = make_decision(analysis, data.complaint + ' ' + data.additional_context,
                             order_result, policy_result)
    # If order or policy tools fail, do not let the drafter invent facts.
    ai_draft = False
    if ai_analysis:
        try:
            draft = agent.draft(data, analysis, decision, order_result, policy_result)
            ai_draft = True
        except (AIUnavailable, Exception):
            draft = fallback_draft(data, decision)
            warnings.append('AI drafting unavailable: review the template draft carefully.')
    else:
        draft = fallback_draft(data, decision)
    ticket = store.create({
        'customer_id': order_result.get('order', {}).get('customer_id') if order_result['verified'] else None,
        'customer_name': data.customer_name, 'customer_email': str(data.customer_email),
        'order_id': data.order_id, 'complaint_message': data.complaint,
        'additional_context': data.additional_context,
        'category': analysis.category.value, 'priority': analysis.priority.value,
        'severity': analysis.severity.value, 'sentiment': analysis.sentiment,
        'summary': analysis.summary, 'priority_reason': analysis.priority_reason,
        'verified_order': order_result, 'policy_lookup': policy_result,
        'decision': decision.model_dump(), 'customer_reply_draft': draft.body,
        'email_subject': draft.subject, 'ai_analysis_completed': ai_analysis,
        'ai_draft_completed': ai_draft, 'warnings': warnings})
    return ticket
