# Deploying to AWS EC2 (automatic, on every push)

This folder turns `git push origin main` into a live deployment on an EC2
instance. There is **no manual step after the first setup**: GitHub Actions SSHes
into the server and runs [`deploy.sh`](deploy.sh), which pulls the new commit,
installs dependencies, ensures the database schema and restarts the services.

```
  developer                GitHub                        EC2 instance
 ┌──────────┐  push   ┌───────────────┐   SSH + deploy   ┌──────────────────────┐
 │ git push │ ──────► │ GitHub Actions│ ───────────────► │ /opt/saas_manger     │
 │  main    │         │ deploy.yml    │   run deploy.sh  │  ├─ git reset --hard │
 └──────────┘         └───────────────┘                  │  ├─ pip install      │
                                                         │  ├─ init_db.py       │
                                                         │  └─ systemctl restart│
                                                         │     3 services        │
                                                         └──────────┬───────────┘
                                                                    │ :8080
                                                        nginx :80 ──┘  (→ :443 with TLS)
```

## What lives here

| File | Purpose |
|---|---|
| `.github/workflows/deploy.yml` | The CD pipeline: on push to `main`, SSH in and run `deploy.sh`. |
| `deploy/deploy.sh` | Server-side deploy: pull, install, migrate schema, restart, health-check. |
| `deploy/setup-server.sh` | One-time bootstrap of a fresh instance (packages, venv, units, nginx). |
| `deploy/systemd/*.service` | systemd units for the web app, the Celery worker and Celery beat. |
| `deploy/nginx/saas-manager.conf` | Reverse proxy in front of uvicorn. |

The service names are `saas-manager-web`, `saas-manager-worker` and
`saas-manager-beat`.

---

## Part A — one-time setup on the EC2 instance

### A.0 Instance + network

* **AMI**: Ubuntu 22.04 or 24.04 LTS (recommended — the scripts also handle Amazon
  Linux 2023 and Amazon Linux 2). Odoo and PostgreSQL are assumed reachable from
  this host.
* **Security group**: allow inbound **22** (SSH), **80** (HTTP) and **443** (HTTPS).
* The instance needs outbound internet (to `apt`/`dnf` and to GitHub).

### A.1 Clone the repository

SSH in as the default user (`ubuntu` on Ubuntu, `ec2-user` on Amazon Linux) and
clone the project to a stable location:

```bash
sudo mkdir -p /opt && cd /opt
git clone https://github.com/7ananSaif/odoo_manager.git saas_manger
sudo chown -R "$USER":"$USER" /opt/saas_manger
cd /opt/saas_manger
```

> **Private repository?** Create a read-only **Deploy Key** (GitHub → repo →
> Settings → Deploy keys → Add) and clone over SSH instead:
> ```bash
> git clone git@github.com:7ananSaif/odoo_manager.git /opt/saas_manger
> ```
> `deploy.sh` only ever needs to **fetch**, so a read-only key is enough.

### A.2 Run the bootstrap

```bash
cd /opt/saas_manger
bash deploy/setup-server.sh
```

This installs `git python3 nginx redis`, builds the venv, installs the three
systemd units and the nginx site, and lets `$USER` restart the services without a
password (needed by CI). Pass `SERVER_NAME=manager.example.com` to set the nginx
`server_name`.

### A.3 Configure `.env`

```bash
cd /opt/saas_manger
nano .env          # created from .env.example by the bootstrap
```

Fill in the **Linux** paths and real secrets — the important ones:

```ini
SECRET_KEY=<openssl rand -hex 32>
SECRETS_KEY=<./venv/bin/python -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())">
MANAGER_DB_URL=postgresql+psycopg2://odoo:YOURPASS@127.0.0.1:5432/saas_manager
ODOO_BASE_URL=https://app.example.com
ODOO_DOMAIN=example.com
ODOO_MASTER_PASSWORD=<odoo admin_passwd>
ODOO_MANAGER_TOKEN=<same value as saas_manager_token in odoo.conf>
ODOO_BIN=/opt/odoo/odoo-bin
ODOO_PYTHON=/opt/odoo/venv/bin/python
PG_DUMP=/usr/bin/pg_dump
PG_RESTORE=/usr/bin/pg_restore
PG_PSQL=/usr/bin/psql
BACKUP_DIR=/opt/saas_manger/backups
CELERY_BROKER_URL=redis://127.0.0.1:6379/0
CELERY_RESULT_BACKEND=redis://127.0.0.1:6379/1
```

> `.env` is git-ignored and is **never** overwritten by a deploy (`git reset`
> only touches tracked files).

### A.4 Create the manager database + owner

```bash
sudo -u postgres createdb saas_manager
cd /opt/saas_manger
./venv/bin/python scripts/init_db.py
./venv/bin/python scripts/create_owner.py --email owner@example.com --name "Owner"
```

`create_owner.py` prints the password once; 2FA is enrolled on the first login.

### A.5 First deploy

```bash
cd /opt/saas_manger
bash deploy/deploy.sh
```

You should end with `[deploy] Health check OK: {...}` and
`curl -s http://127.0.0.1:8080/health` returning JSON. The app is now live on the
instance's public IP (via nginx on port 80).

---

## Part B — connect GitHub Actions

In the GitHub repository, go to **Settings → Secrets and variables → Actions →
New repository secret** and add:

| Secret | Required | Value |
|---|---|---|
| `EC2_HOST` | yes | Public IP or DNS of the instance. |
| `EC2_USER` | yes | `ubuntu` (Ubuntu) or `ec2-user` (Amazon Linux). |
| `EC2_SSH_KEY` | yes | The **private** key (`.pem`) contents for that user. |
| `EC2_PORT` | no | SSH port (default `22`). |
| `EC2_APP_DIR` | no | Install dir (default `/opt/saas_manger`). |

That's it. From now on:

```bash
git add -A
git commit -m "change something"
git push            # -> GitHub Actions -> EC2 deploy.sh -> services restarted
```

Watch it run under the repository's **Actions** tab (workflow **Deploy to EC2**),
or trigger it manually with **Run workflow**.

---

## Updating, rolling back, operating

* **Logs** (journald): `journalctl -u saas-manager-web -f`,
  `journalctl -u saas-manager-worker -f`, `journalctl -u saas-manager-beat -f`.
* **Status**: `systemctl status saas-manager-web saas-manager-worker saas-manager-beat`.
* **Roll back**: the server is a plain git checkout, so deploy any commit:
  ```bash
  cd /opt/saas_manger
  git fetch origin
  git reset --hard <commit-sha>
  bash deploy/deploy.sh SKIP_PULL=1     # deploy the current checkout as-is
  ```
  (Then move `main` back in GitHub if you want CI to keep that state.)
* **Redeploy without pushing**: re-run the workflow from the Actions tab, or run
  `bash deploy/deploy.sh` on the server.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| Actions fails at "Prepare SSH key" | `EC2_USER` / `EC2_HOST` secrets wrong. |
| `Permission denied (publickey)` | `EC2_SSH_KEY` is not the private key for `EC2_USER`. |
| `Host key verification failed` | The workflow uses `accept-new`; if the host key changed, remove the stale `~/.ssh/known_hosts` on the runner (transient) or fix DNS. |
| `sudo: a password is required` during deploy | `deploy/setup-server.sh` did not install the sudoers rule — re-run it as the deploy user. |
| Health check times out | `journalctl -u saas-manager-web -n 100 --no-pager`; usually a bad `.env` (DB URL, missing `SECRETS_KEY`). |
| `init_db.py` fails to connect | `MANAGER_DB_URL` wrong or `saas_manager` DB not created (§A.4). |
| 502 from nginx | uvicorn is not up: `systemctl status saas-manager-web`. |
| Worker/beat not consuming | Redis down (`systemctl status redis-server`) or wrong `CELERY_BROKER_URL`. |
| `git reset --hard` wiped a server hot-fix | Commit it to `main` instead — CI owns the server checkout. |

---

## Appendix

### Alternative: deploy by rsync (no git credentials on the server)

If the repository is private and you would rather not keep a deploy key on the
instance, replace the "Run remote deploy" step's command with an `rsync` of the
checked-out tree. Add a checkout first:

```yaml
      - uses: actions/checkout@v4
      - name: Rsync to EC2
        run: |
          set -euo pipefail
          rsync -az --delete \
            --exclude '.git' --exclude 'venv' --exclude '.env' \
            --exclude 'logs' --exclude 'backups' \
            -e "ssh -i ~/.ssh/ec2_key -p $EC2_PORT -o StrictHostKeyChecking=accept-new" \
            ./ "${EC2_USER}@${EC2_HOST}:/opt/saas_manger/"
```

Both approaches end by running `deploy/deploy.sh` (with `SKIP_PULL=1` for the
rsync variant, since there is nothing to pull).

### HTTPS

Point a DNS record at the instance, then:

```bash
sudo apt-get install -y certbot python3-certbot-nginx
sudo certbot --nginx -d manager.example.com
```

certbot rewrites the nginx block to listen on `:443`. Set `ODOO_BASE_URL` to the
`https://` address so the session cookie is marked `secure`.

### Updating the Odoo core lock

The manager is deployed automatically; the **Odoo core patch** is applied
separately inside the Odoo source tree (it is not a service):

```bash
cd /opt/odoo
git apply --check /opt/saas_manger/patch/saas_manager_lock.patch && \
git apply       /opt/saas_manger/patch/saas_manager_lock.patch
```

Re-run it after each Odoo upgrade. See [`../patch/APPLY_WINDOWS.md`](../patch/APPLY_WINDOWS.md)
for the guarded files and verification steps.
