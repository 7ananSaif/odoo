# SAAS-PATCH — Odoo 19 core lock

This patch locks application and database management inside every client
database. Only the standalone **SaaS Manager** (or the server owner on the
command line) can install/uninstall/upgrade apps, create/drop/backup/restore
databases, and change the master password.

Everything the patch adds is marked with `# SAAS-PATCH`, so after an Odoo
upgrade you can find every hunk with:

```
findstr /s /n "# SAAS-PATCH" odoo\*.py addons\*.py
```

## 1. Files touched

| # | File | What it does |
|---|------|--------------|
| 1 | `odoo/tools/saas_lock.py` **(new)** | Central helper: token check, internal flag, DB/module guards, plan limits, tenant status. |
| 2 | `odoo/tools/config.py` | Adds `saas_lock` and `saas_manager_token` (config-file only). |
| 3 | `odoo/addons/base/models/ir_module.py` | Guards install/uninstall/upgrade/`update_list`/reset/uninstall-wizard. |
| 4 | `odoo/modules/loading.py` | Marks the trusted internal load path so startup/CLI and manager installs are never blocked. |
| 5 | `odoo/addons/base/models/ir_ui_menu.py` | Hides the Apps and Settings > Technical menus when locked. |
| 6 | `odoo/http.py` | Blocks `db` RPC, disables developer mode for clients, read-only mode when suspended/expired. |
| 7 | `odoo/service/db.py` | Guards the `db` service dispatch (create/drop/backup/restore/...). |
| 8 | `addons/web/controllers/database.py` | Guards every `/web/database/*` route. |
| 9 | `odoo/addons/base/models/res_users.py` | Enforces the `max_users` plan limit on user create/activation. |
| 10 | `odoo/addons/base/models/res_company.py` | Enforces the `max_companies` plan limit. |
| 11 | `addons/stock/models/stock_warehouse.py` | Enforces the `max_warehouses` plan limit. |
| 12 | `odoo/addons/base/models/ir_attachment.py` | Enforces the optional `max_storage_mb` limit. |
| 13 | `odoo/addons/base/models/ir_config_parameter.py` | `saas.*` parameters: hidden from clients, only the manager can write them. |

## 2. How the lock decides "allowed"

A restricted operation is allowed when **any** of these is true:

1. `saas_lock` is `False` in `odoo.conf` (lock disabled).
2. The call is **internal** (the manager already passed the token matrix and the
   core load path is running — `loading.py` / `button_immediate_*`).
3. The caller presented the **manager token**, via any of:
   * HTTP header `X-Saas-Manager-Token: <token>`
   * RPC context key `saas_manager_token`
   * POST field `saas_manager_token`
4. It is a **CLI** run (`-i` / `-u` / `--reinit`) **with no live HTTP request**
   (i.e. the server owner running `odoo-bin -d db -u module --stop-after-init`).

## 3. Apply the patch (Windows)

Prerequisites: `git` on PATH, and the Odoo 19 tree at `D:\odoo\odoo`.

### 3.1 Dry run first (recommended)

```
cd /d D:\odoo\odoo
git apply --check --verbose D:\odoo\saas_manger\patch\saas_manager_lock.patch
```

* No output (and exit code 0) means the patch applies cleanly.
* If it complains, you are not on a matching 19.0 revision — see §6.

### 3.2 Apply

```
cd /d D:\odoo\odoo
git apply -v D:\odoo\saas_manger\patch\saas_manager_lock.patch
```

If the tree is **not** a git working copy on the target machine, use plain
`patch` instead (install "GnuWin32 patch"):

```
cd /d D:\odoo\odoo
patch -p1 --dry-run < D:\odoo\saas_manger\patch\saas_manager_lock.patch
patch -p1           < D:\odoo\saas_manger\patch\saas_manager_lock.patch
```

### 3.3 Edit odoo.conf

Open the config file that Odoo actually loads (usually
`D:\odoo\odoo\odoo.conf`) and add the keys from
`patch\odoo.conf.snippet` to its `[options]` section:

```
[options]
; ... your existing keys ...
saas_lock = True
saas_manager_token = <A_LONG_RANDOM_SECRET>
dbfilter = ^%d$
list_db = False
```

Generate the secret with:

```
python -c "import secrets;print(secrets.token_urlsafe(48))"
```

Copy the same value into the SaaS Manager `.env` as `ODOO_MANAGER_TOKEN`.

### 3.4 Restart Odoo

```
Restart-Service odoo        # if registered as a service (see the manager docs)
```

Check the log for a clean start: no `SAAS-PATCH` errors, and the client admin
UI no longer shows the Apps menu.

## 4. Verify the lock (manual)

1. Log into a client database as its **administrator** (not the manager).
2. The **Apps** app is gone from the app switcher.
3. Settings no longer shows **Technical**; the debug/developer toggle is off.
4. Open `/web/database/manager` in the browser → access denied.
5. From an RPC client, call `button_immediate_install` → `AccessError`.

## 5. Verify the lock (automated tests)

The patch ships with tests in the SaaS Manager repo:

```
cd D:\odoo\saas_manger
venv\Scripts\activate
pytest tests\test_core_lock.py -v
```

and, against a running Odoo, the end-to-end checks:

```
pytest tests\test_e2e_lock.py -v
```

See `docs/TESTING.md` for the full checklist (client admin cannot create user
`max_users + 1`, cannot add a warehouse, cannot edit `saas.*`, cannot open the
database manager, and the manager **can** do all of these).

## 6. Re-applying after an Odoo upgrade

When you upgrade Odoo:

1. `git stash` / `git checkout .` to drop the old hunks, upgrade, then re-apply
   (`git apply --3way`) — resolve any conflicts reported by the `# SAAS-PATCH`
   markers.
2. Or, search the new source for the anchors used by each hunk:

   ```
   findstr /s /n "def button_immediate_install" odoo\addons\base\models\ir_module.py
   ```

   and re-add the one-line `saas_lock.check_module_operation(...)` calls at the
   top of the same methods. The helper file `odoo/tools/saas_lock.py` never
   changes, so re-applying is mechanical.

> Note: most of the guarded methods (`button_install`, `update_list`,
> `_button_immediate_function`, `load_modules`, ...) keep their signatures, so
> conflicts are rare and localized.
