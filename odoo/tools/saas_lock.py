# Part of Odoo. See LICENSE file for full copyright and licensing details.
#
# SAAS-PATCH ###################################################################
# Centralized "SaaS lock" helper.
#
# This module is the SINGLE enforcement point for every SaaS restriction added
# to the Odoo core. All other patched files import the functions defined here,
# so the whole patch can be found by searching for the marker `# SAAS-PATCH`.
#
# What it does:
#   * Reads two config switches added to odoo.conf:
#         saas_lock = True            # master switch (default: False)
#         saas_manager_token = <secret>   # token the SaaS Manager must send
#   * Blocks module installation/uninstallation/upgrade operations unless they
#     are performed by the SaaS Manager (token), by an internal manager-authorized
#     call (thread flag), or by the server owner through the CLI (-i / -u).
#   * Blocks database management (create/drop/backup/restore/duplicate/rename/
#     change master password) unless performed by the SaaS Manager (token).
#   * Enforces per-tenant plan limits (users / warehouses / companies / storage)
#     inside the client database, based on `saas.*` ir.config_parameter keys that
#     only the manager can write.
#   * Centralizes the `saas.*` parameter keys and their protection.
#
# This file is intentionally dependency-light: it must be importable very early
# (during module loading) without creating circular imports.
# SAAS-PATCH ###################################################################
from __future__ import annotations

import hmac
import logging
import threading
from contextlib import contextmanager

from odoo.tools import config

_logger = logging.getLogger(__name__)

#: Version of the core patch, useful for support / diagnostics.
SAAS_PATCH_VERSION = '1.0.0'

#: Prefix of every parameter managed by the SaaS Manager.
SAAS_PARAM_PREFIX = 'saas.'

#: ir.config_parameter keys owned by the SaaS Manager. Client admins may neither
#: read nor write these keys.
SAAS_PARAM_KEYS = (
    'saas.status',          # trial / active / suspended / expired / cancelled
    'saas.expiry_date',     # ISO date (YYYY-MM-DD) or empty
    'saas.trial_days',      # integer
    'saas.max_users',
    'saas.max_warehouses',
    'saas.max_companies',
    'saas.max_storage_mb',
    'saas.max_db_size_mb',
    'saas.block_writes',        # '1' to force read-only when suspended/expired
    'saas.count_portal_users',  # '1' to also count portal/public users
    'saas.tenant_id',       # SaaS Manager tenant identifier
    'saas.plan',            # informational plan name
    'saas.last_push',       # ISO datetime of the last manager push
)

#: HTTP header carrying the manager token.
SAAS_TOKEN_HEADER = 'X-Saas-Manager-Token'

#: Context key the manager may use instead of / in addition to the header.
SAAS_TOKEN_CONTEXT_KEY = 'saas_manager_token'

#: Statuses that make a database read-only (or blocked).
SAAS_BLOCKING_STATUSES = ('suspended', 'expired', 'cancelled')

#: Statuses considered "not blocked" for limit checks (business as usual).
SAAS_ACTIVE_STATUSES = ('trial', 'active')

# Thread-local flag: set while an internal (already authorized) module/database
# operation is running, so the low-level model methods do not re-check the token.
_local = threading.local()


# ---------------------------------------------------------------------------
# Config accessors
# ---------------------------------------------------------------------------
def saas_enabled() -> bool:
    """Return True when the SaaS lock is enabled in odoo.conf."""
    try:
        return bool(config.get('saas_lock'))
    except Exception:  # noqa: BLE001 - config not parsed yet (very early import)
        return False


def configured_token() -> str:
    """Return the manager token configured in odoo.conf (may be empty)."""
    try:
        return str(config.get('saas_manager_token') or '')
    except Exception:  # noqa: BLE001
        return ''


def is_cli_run() -> bool:
    """Return True when the server was started with -i / -u / --reinit.

    This is how the server owner performs one-shot installs/upgrades. It is only
    honoured when there is no live HTTP request (see :func:`manager_token_ok` and
    the guards), so a long-running server started with -u does not silently
    unlock the UI.
    """
    try:
        return bool(config['init'] or config['update'] or config['reinit'])
    except Exception:  # noqa: BLE001
        return False


# ---------------------------------------------------------------------------
# Internal (authorized) thread flag
# ---------------------------------------------------------------------------
def is_internal() -> bool:
    """Return True while an internal/authorized operation is running."""
    return bool(getattr(_local, 'internal', False))


def mark_internal(flag: bool = True) -> bool:
    """Set the internal flag, returning its previous value."""
    previous = bool(getattr(_local, 'internal', False))
    _local.internal = bool(flag)
    return previous


@contextmanager
def internal_context():
    """Context manager that sets the internal flag for the duration of a block."""
    previous = mark_internal(True)
    try:
        yield
    finally:
        _local.internal = previous


# ---------------------------------------------------------------------------
# Request / token helpers
# ---------------------------------------------------------------------------
def _current_request():
    """Return the current odoo.http.request, or None outside a request."""
    try:
        from odoo.http import request  # noqa: PLC0415 - avoid circular import
    except Exception:  # noqa: BLE001
        return None
    # `request` is a LocalProxy: touching it outside a request raises.
    try:
        if request and getattr(request, 'httprequest', None) is not None:
            return request
    except Exception:  # noqa: BLE001
        return None
    return None


def has_http_request() -> bool:
    """Return True when the current thread is serving an HTTP request."""
    return _current_request() is not None


def _candidate_tokens(token=None, env=None):
    """Collect every token presented by the caller."""
    candidates = []
    if token:
        candidates.append(token)
    if env is not None:
        try:
            context = env.context or {}
        except Exception:  # noqa: BLE001
            context = {}
        value = context.get(SAAS_TOKEN_CONTEXT_KEY)
        if value:
            candidates.append(value)
    request = _current_request()
    if request is not None:
        httprequest = request.httprequest
        try:
            header_value = httprequest.headers.get(SAAS_TOKEN_HEADER)
        except Exception:  # noqa: BLE001
            header_value = None
        if header_value:
            candidates.append(header_value)
        for store in (getattr(httprequest, 'args', None), getattr(httprequest, 'form', None)):
            if not store:
                continue
            try:
                value = store.get(SAAS_TOKEN_CONTEXT_KEY)
            except Exception:  # noqa: BLE001
                value = None
            if value:
                candidates.append(value)
    return candidates


def _token_matches(candidate, expected) -> bool:
    try:
        return hmac.compare_digest(str(candidate).encode(), str(expected).encode())
    except Exception:  # noqa: BLE001
        return False


def manager_token_ok(token=None, env=None) -> bool:
    """Return True when the caller presented the configured manager token."""
    expected = configured_token()
    if not expected:
        return False
    return any(_token_matches(candidate, expected) for candidate in _candidate_tokens(token, env))


def is_manager_call(token=None, env=None) -> bool:
    """True for any call the manager is allowed to make (token or internal)."""
    return is_internal() or manager_token_ok(token, env)


def hide_dev_mode() -> bool:
    """Return True when developer mode must be disabled for the caller.

    When the SaaS lock is on, client users must not be able to enable developer
    mode (which would reveal the Technical menu, debug menus, ...). Manager
    calls keep their rights.
    """
    if not saas_enabled():
        return False
    return not is_manager_call()


# ---------------------------------------------------------------------------
# Guards
# ---------------------------------------------------------------------------
def _deny(message):
    from odoo.exceptions import AccessError  # noqa: PLC0415
    _logger.warning('SAAS-PATCH: access denied: %s', message)
    raise AccessError(message)


def check_module_operation(env=None, token=None, operation='module operation'):
    """Guard every ir.module.module state-changing operation.

    Allowed when:
      * the SaaS lock is disabled, OR
      * the call is internal (already authorized by the manager), OR
      * the caller presented the manager token, OR
      * the process is a CLI run (-i / -u) with no live HTTP request.
    """
    if not saas_enabled():
        return
    if is_internal():
        return
    if manager_token_ok(token, env):
        return
    if is_cli_run() and not has_http_request():
        return
    _deny(
        "Application management is disabled on this database. "
        "Please contact your service provider to install, upgrade or "
        "uninstall applications (%s)." % operation
    )


def check_db_operation(method=None, token=None, env=None):
    """Guard database management (create/drop/backup/restore/...)."""
    if not saas_enabled():
        return
    if is_internal():
        return
    if manager_token_ok(token, env):
        return
    if is_cli_run() and not has_http_request():
        return
    _deny(
        "Database management is disabled. Only the SaaS Manager may manage "
        "databases (%s)." % (method or 'database operation')
    )


def check_saas_param_write(env=None, keys=None, token=None):
    """Guard writes to `saas.*` ir.config_parameter keys."""
    if not saas_enabled():
        return
    if is_internal():
        return
    if manager_token_ok(token, env):
        return
    for key in keys or ():
        if key and str(key).startswith(SAAS_PARAM_PREFIX):
            _deny(
                "SaaS parameters are managed by your provider and cannot be "
                "modified (%s)." % key
            )


def hide_saas_params(env=None, token=None) -> bool:
    """Return True when `saas.*` parameters must be hidden from the caller."""
    if not saas_enabled():
        return False
    return not is_manager_call(token, env)


# ---------------------------------------------------------------------------
# Tenant status / expiry
# ---------------------------------------------------------------------------
def get_saas_param(env, key, default=None):
    """Read a `saas.*` parameter (full key expected, e.g. 'saas.status')."""
    if not saas_enabled() or env is None:
        return default
    try:
        # Use the raw accessor to bypass the ir.config_parameter visibility guard.
        value = env['ir.config_parameter'].sudo()._get_param(key)
        return value if value not in (None, False) else default
    except Exception:  # noqa: BLE001 - registry/table may not exist yet
        return default


def get_status(env) -> str:
    """Return the current tenant status (defaults to 'active')."""
    return str(get_saas_param(env, 'saas.status', 'active') or 'active').lower()


def is_blocked(env) -> bool:
    """Return True when the database is suspended/expired and must be read-only."""
    if not saas_enabled():
        return False
    return get_status(env) in SAAS_BLOCKING_STATUSES


def block_writes_enabled(env) -> bool:
    """Whether blocking emails the instance into write-protection mode."""
    value = get_saas_param(env, 'saas.block_writes', '1')
    return str(value) not in ('0', 'False', 'false', '')


def get_expiry_date(env):
    """Return the expiry date string (YYYY-MM-DD) or None."""
    value = get_saas_param(env, 'saas.expiry_date', None)
    return value or None


# ---------------------------------------------------------------------------
# Plan limits
# ---------------------------------------------------------------------------
def _int_param(env, key):
    value = get_saas_param(env, key)
    if value in (None, '', False):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        _logger.warning('SAAS-PATCH: invalid integer for %s: %r', key, value)
        return None


def count_portal_users_enabled(env) -> bool:
    """Whether portal/public users are also counted against `saas.max_users`.

    Configurable per tenant through the `saas.count_portal_users` parameter
    (default: off — only internal users are counted).
    """
    value = get_saas_param(env, 'saas.count_portal_users', '0')
    return str(value).strip().lower() in ('1', 'true', 'yes', 'on')


def count_internal_users(env) -> int:
    """Count the users that consume the `saas.max_users` quota.

    By default this is active internal users only — portal and public users are
    free. Set `saas.count_portal_users` to also count portal/public users.
    """
    domain = [('active', '=', True)]
    if not count_portal_users_enabled(env):
        domain.append(('share', '=', False))
    return env['res.users'].with_context(active_test=True).search_count(domain)


def count_warehouses(env) -> int:
    if 'stock.warehouse' not in env:
        return 0
    return env['stock.warehouse'].with_context(active_test=True).search_count([
        ('active', '=', True),
    ])


def count_companies(env) -> int:
    return env['res.company'].with_context(active_test=True).search_count([
        ('active', '=', True),
    ])


def storage_mb(env) -> float:
    """Return the current filestore size in megabytes (best effort)."""
    if 'ir.attachment' not in env:
        return 0.0
    env.cr.execute("SELECT COALESCE(SUM(file_size), 0) FROM ir_attachment")
    total = env.cr.fetchone()[0] or 0
    return float(total) / (1024.0 * 1024.0)


#: Human label used in the limit error message, per limit kind.
LIMIT_LABELS = {
    'user': 'User',
    'warehouse': 'Warehouse',
    'company': 'Company',
    'storage': 'Storage',
}


def _raise_limit(kind):
    """Raise the standard plan-limit UserError (message shown to the client)."""
    from odoo.exceptions import UserError  # noqa: PLC0415
    label = LIMIT_LABELS.get(kind, kind.capitalize())
    raise UserError(
        "%s limit reached for your plan. Contact your provider." % label
    )


def check_saas_limit(env, limit_key, extra=0):
    """Enforce a plan limit inside the client database.

    :param env: current environment
    :param limit_key: one of 'max_users', 'max_warehouses', 'max_companies',
                      'max_storage_mb'
    :param extra: how many additional units the pending operation would add
    :return: True when the operation is allowed
    :raises UserError: when the limit would be exceeded
    """
    if not saas_enabled() or env is None:
        return True
    # Managers and internal (already authorized) operations bypass the limits.
    if is_manager_call(env=env):
        return True
    # Never enforce while the registry is initializing (install time).
    try:
        if not env.registry.ready or env.registry._init:
            return True
    except Exception:  # noqa: BLE001
        return True

    if limit_key == 'max_users':
        limit = _int_param(env, 'saas.max_users')
        if limit is None:
            return True
        current = count_internal_users(env)
        if current + extra > limit:
            _raise_limit("user")
    elif limit_key == 'max_warehouses':
        limit = _int_param(env, 'saas.max_warehouses')
        if limit is None:
            return True
        current = count_warehouses(env)
        if current + extra > limit:
            _raise_limit("warehouse")
    elif limit_key == 'max_companies':
        limit = _int_param(env, 'saas.max_companies')
        if limit is None:
            return True
        current = count_companies(env)
        if current + extra > limit:
            _raise_limit("company")
    elif limit_key == 'max_storage_mb':
        limit = _int_param(env, 'saas.max_storage_mb')
        if limit is None:
            return True
        if storage_mb(env) > limit:
            _raise_limit("storage")
    return True


def check_users_extra(env, vals_list, current_records=None):
    """Helper for res.users create/write: check whether the operation activates
    internal users beyond the plan limit.

    :param vals_list: list of value dicts (create) or a single vals dict (write)
    :param current_records: recordset being written (for write), else None
    """
    if not saas_enabled() or env is None:
        return True
    if is_manager_call(env=env):
        return True
    if not isinstance(vals_list, list):
        vals_list = [vals_list]

    if current_records is None:
        # create(): a new user counts when active and internal. We cannot know
        # `share` for sure before creation, so count any explicitly active user
        # that is not explicitly a portal/share user.
        extra = 0
        for vals in vals_list:
            if vals.get('active', True) is False:
                continue
            if vals.get('share'):
                continue
            extra += 1
        if extra:
            check_saas_limit(env, 'max_users', extra=extra)
        return True

    # write(): count only records transitioning to active internal.
    extra = 0
    for record in current_records:
        was_internal = record.active and not record.share
        becomes_internal = vals_list[0].get('active', record.active) and not vals_list[0].get('share', record.share)
        if becomes_internal and not was_internal:
            extra += 1
    if extra:
        check_saas_limit(env, 'max_users', extra=extra)
    return True
