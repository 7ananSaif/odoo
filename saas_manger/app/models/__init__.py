"""Import every model so SQLAlchemy registers them on ``Base.metadata``."""
from __future__ import annotations

from app.models.base import PkMixin, TimestampMixin
from app.models.billing import CreditNote, Invoice, InvoiceLine, Payment, Subscription
from app.models.enums import (
    AuditLevel,
    BillingCycle,
    InvoiceStatus,
    JobKind,
    JobStatus,
    PaymentMethod,
    SubscriptionStatus,
    TenantStatus,
)
from app.models.ops import AuditLog, Backup, JobLog, OdooVersion, UpdateJob, UpdateRun
from app.models.plan import Plan, PlanModule
from app.models.settings import Setting
from app.models.tenant import Tenant
from app.models.user import User

__all__ = [
    "AuditLevel",
    "AuditLog",
    "Backup",
    "BillingCycle",
    "CreditNote",
    "Invoice",
    "InvoiceLine",
    "InvoiceStatus",
    "JobKind",
    "JobLog",
    "JobStatus",
    "OdooVersion",
    "Payment",
    "PaymentMethod",
    "PkMixin",
    "Plan",
    "PlanModule",
    "Setting",
    "Subscription",
    "SubscriptionStatus",
    "Tenant",
    "TenantStatus",
    "TimestampMixin",
    "UpdateJob",
    "UpdateRun",
    "User",
]
