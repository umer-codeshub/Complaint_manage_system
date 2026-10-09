import pytest
from agents.schemas import ComplaintAnalysis, DraftOutput, ComplaintInput
from tools.ticket_generator import TicketStore

@pytest.fixture
def store(tmp_path):
    return TicketStore(tmp_path / 'tickets')

@pytest.fixture
def sample():
    return ComplaintInput(customer_name='Ayesha Khan', customer_email='ayesha@example.com',
                          order_id='DEMO-1001', complaint='My delivery is ten days late and support ignored me twice.')

class FakeAI:
    def __init__(self, category='late_delivery', priority='High'):
        self.category=category
        self.priority=priority
        self.draft_called=False
    def analyze(self, complaint):
        return ComplaintAnalysis(category=self.category, summary='Customer reports order-related problems.',
            sentiment='Frustrated', severity=self.priority, priority=self.priority,
            priority_reason='Customer describes an unresolved order problem.', escalation_recommended=False)
    def draft(self, complaint, analysis, decision, order_result, policy_result):
        self.draft_called=True
        return DraftOutput(subject='Update about your complaint',
                           body='Dear Customer,\nWe understand your concern. Support will review the case.\nBest regards, Support')

@pytest.fixture
def fake_ai():
    return FakeAI()

class FakeCredentials:
    valid = True
    expired = False
    refresh_token = None

@pytest.fixture
def credentials():
    return FakeCredentials()
