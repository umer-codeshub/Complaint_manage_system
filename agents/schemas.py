"""Validated contracts shared by the deterministic workflow and AI agents."""
from enum import Enum
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

class Category(str, Enum):
    LATE_DELIVERY = 'late_delivery'
    MISSING_ORDER = 'missing_order'
    DAMAGED_PRODUCT = 'damaged_product'
    REFUND_REQUEST = 'refund_request'
    INCORRECT_ITEM = 'incorrect_item'
    UNRESPONSIVE_SUPPORT = 'unresponsive_support'
    ORDER_CANCELLATION = 'order_cancellation'
    DELIVERY_DELAY = 'delivery_delay'
    OTHER = 'other'

class Priority(str, Enum):
    LOW = 'Low'
    MEDIUM = 'Medium'
    HIGH = 'High'
    CRITICAL = 'Critical'

class ComplaintInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    customer_name: str = Field(min_length=2, max_length=120)
    customer_email: EmailStr
    order_id: str = Field(min_length=3, max_length=60)
    complaint: str = Field(min_length=12, max_length=5000)
    additional_context: str = Field(default='', max_length=2000)

    @field_validator('customer_name', 'order_id')
    @classmethod
    def no_controls(cls, value: str) -> str:
        if any(ord(c) < 32 for c in value):
            raise ValueError('Control characters are not allowed')
        return value

class ComplaintAnalysis(BaseModel):
    category: Category
    summary: str = Field(min_length=8, max_length=600)
    sentiment: str = Field(min_length=3, max_length=60)
    severity: Priority
    priority: Priority
    priority_reason: str = Field(min_length=8, max_length=400)
    escalation_recommended: bool

class DraftOutput(BaseModel):
    subject: str = Field(min_length=8, max_length=150)
    body: str = Field(min_length=30, max_length=5000)

class Decision(BaseModel):
    outcome: str
    reason: str
    suggested_action: str
    escalated: bool
    escalation_reason: str = ''
