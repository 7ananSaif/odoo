"""Enumerations shared by the manager models and UI."""
from __future__ import annotations

from enum import StrEnum


class TenantStatus(StrEnum):
    TRIAL = "trial"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class BillingCycle(StrEnum):
    MONTHLY = "monthly"
    YEARLY = "yearly"


class SubscriptionStatus(StrEnum):
    TRIAL = "trial"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    SUSPENDED = "suspended"
    CANCELLED = "cancelled"


class InvoiceStatus(StrEnum):
    DRAFT = "draft"
    SENT = "sent"
    PAID = "paid"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"


class PaymentMethod(StrEnum):
    BANK_TRANSFER = "bank_transfer"
    CASH = "cash"
    CHEQUE = "cheque"
    ONLINE = "online"
    DEPOSIT = "deposit"
    OTHER = "other"


class PaymentKind(StrEnum):
    """How a money movement affects the tenant's balance."""

    PAYMENT = "payment"   # settles an invoice (money in)
    DEPOSIT = "deposit"   # paid in advance, not tied to an invoice (money in)
    REFUND = "refund"     # paid back to the tenant (money out)


class CreditNoteKind(StrEnum):
    """A balance adjustment that is not a payment."""

    CREDIT = "credit"     # reduces what the tenant owes
    DEBIT = "debit"       # increases what the tenant owes


class JobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobKind(StrEnum):
    PROVISION = "provision"
    BACKUP = "backup"
    RESTORE = "restore"
    UPDATE = "update"
    PLAN_PUSH = "plan_push"
    DELETE = "delete"
    DUPLICATE = "duplicate"


class AuditLevel(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
