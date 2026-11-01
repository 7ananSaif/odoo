"""Verify the Odoo core patch artefacts (source-level, no Odoo runtime needed).

These tests inspect the produced `.patch` file and the helper module
`odoo/tools/saas_lock.py` in the Odoo tree next to this project. They are
skipped automatically when the Odoo tree is not present.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

PROJECT_DIR = Path(__file__).resolve().parent.parent
ODOO_ROOT = PROJECT_DIR.parent / "odoo"
PATCH_FILE = PROJECT_DIR / "patch" / "saas_manager_lock.patch"
HELPER = ODOO_ROOT / "odoo" / "tools" / "saas_lock.py"

pytestmark = pytest.mark.skipif(not ODOO_ROOT.is_dir(), reason="Odoo tree not present")

# Every file the patch must touch (paths relative to the Odoo root).
EXPECTED_FILES = [
    "odoo/tools/saas_lock.py",
    "odoo/tools/config.py",
    "odoo/addons/base/models/ir_module.py",
    "odoo/modules/loading.py",
    "odoo/addons/base/models/ir_ui_menu.py",
    "odoo/http.py",
    "odoo/service/db.py",
    "addons/web/controllers/database.py",
    "odoo/addons/base/models/res_users.py",
    "odoo/addons/base/models/res_company.py",
    "addons/stock/models/stock_warehouse.py",
    "odoo/addons/base/models/ir_attachment.py",
    "odoo/addons/base/models/ir_config_parameter.py",
]


def test_patch_file_exists():
    assert PATCH_FILE.is_file(), f"patch not found at {PATCH_FILE}"


def test_patch_contains_every_expected_file():
    text = PATCH_FILE.read_text(encoding="utf-8", errors="replace")
    missing = [f for f in EXPECTED_FILES if f"b/{f}" not in text]
    assert not missing, f"patch is missing diffs for: {missing}"


def test_patch_is_marked_with_saas_patch():
    text = PATCH_FILE.read_text(encoding="utf-8", errors="replace")
    assert "# SAAS-PATCH" in text
    assert text.count("# SAAS-PATCH") >= 10


def test_helper_module_exists_and_is_marked():
    assert HELPER.is_file()
    source = HELPER.read_text(encoding="utf-8")
    assert "# SAAS-PATCH" in source


def test_helper_exports_expected_api():
    """saas_lock.py must define the public functions the patch relies on."""
    tree = ast.parse(HELPER.read_text(encoding="utf-8"))
    functions = {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    for name in (
        "saas_enabled",
        "is_internal",
        "internal_context",
        "mark_internal",
        "check_module_operation",
        "check_db_operation",
        "check_saas_limit",
        "check_saas_param_write",
        "hide_dev_mode",
        "hide_saas_params",
    ):
        assert name in functions, f"saas_lock.{name} is missing"


def test_helper_defines_version_and_prefix_constants():
    source = HELPER.read_text(encoding="utf-8")
    assert "SAAS_PATCH_VERSION" in source
    assert "SAAS_PARAM_PREFIX" in source


def test_guarded_methods_reference_the_helper():
    """Each core file must import/call the helper (source-level grep)."""
    targets = {
        "odoo/addons/base/models/ir_module.py": ["saas_lock.check_module_operation"],
        "odoo/addons/base/models/ir_ui_menu.py": ["saas_lock"],
        "odoo/http.py": ["saas_lock.check_db_operation", "saas_lock.hide_dev_mode"],
        "odoo/service/db.py": ["saas_lock.check_db_operation"],
        "odoo/addons/base/models/res_users.py": ["saas_lock.check_users_extra"],
    }
    for rel, needles in targets.items():
        path = ODOO_ROOT / rel
        if not path.is_file():
            pytest.skip(f"{rel} not present")
        source = path.read_text(encoding="utf-8", errors="replace")
        for needle in needles:
            assert needle in source, f"{needle} not found in {rel}"


def test_saas_lock_names_apply_to_the_manager_defaults():
    """The manager must target the same switch names the core patch reads."""
    helper = HELPER.read_text(encoding="utf-8")
    for name in ("saas_lock", "saas_manager_token"):
        assert name in helper, f"{name} must be referenced by saas_lock.py"
