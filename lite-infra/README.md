# lite-infra — the whole stack for ~$5/month

One Lightsail instance running Docker Compose: the app plus its own
PostgreSQL. **No EKS, no ALB, no NAT Gateway, no RDS.**

Terraform, same as `full-infra/` — no new tool to learn.

| What | Where |
|---|---|
| Terraform | `lite-infra/*.tf` |
| What runs on the box | `lite-infra/docker-compose.lite.yml` |
| First-boot script | `lite-infra/boot.sh.tftpl` |
| Commands | `deploy/lite-aws.sh` |

---

## 1. What is deliberately missing

| Not deployed | Because | What you get instead |
|---|---|---|
| EKS | ~$73/month for the control plane alone | `docker compose` on the instance |
| ALB | ~$16/month minimum | the instance's static IP on port 80 |
| NAT Gateway | ~$32/month | the instance has a public IP |
| RDS | ~$15/month for the smallest Multi-AZ | `pgvector/pgvector:pg16` container + a Docker volume |
| ElastiCache, RabbitMQ | need RAM this box does not have | not present; see the caveat in §5 |

That is the trade: **one machine, no redundancy, no managed backups.** For a
demo, a staging box, or a side project it is fine. For production it is not.

---

## 2. Cost — what it actually bills

Prices verified against AWS's own documentation in **October 2026**
([Lightsail bundles](https://docs.aws.amazon.com/lightsail/latest/userguide/amazon-lightsail-bundles.html):
*Nano-0.5GB Linux with public IPv4 — $5.00/month, 2 vCPU, 512 MB, 20 GB SSD,
1 TB transfer*).

| Line item | Monthly |
|---|---|
| Lightsail `nano_3_0` bundle | **$5.00** |
| Static IP, while attached to a running instance | $0.00 |
| SNS email notifications (first 1,000) | $0.00 |
| CloudWatch alarm (1 metric alarm, $0.10/alarm) | **$0.10** |
| **Total** | **≈ $5.10/month** |

What pushes it over:

* **Stopping the instance does not stop the bill.** Lightsail bills a stopped
  instance's storage; you must *delete* it to reach $0.
* **Snapshots** are billed per GB-month beyond the plan's allowance.
* **Egress past 1 TB** is billed at standard AWS data-transfer rates.
* A static IP that is **detached** from a running instance is billed hourly.

The `$5` guard rail is `billing.tf`: a CloudWatch alarm on
`AWS/Billing EstimatedCharges` that emails you when the account passes $5. It
reads billing metrics from **us-east-1** (that is where AWS publishes them),
which is why `main.tf` declares a second provider alias.

> Billing metrics must be switched on once per account: **Billing → Billing
> preferences → Receive Billing Alerts**. Terraform cannot toggle it. If the
> alarm shows `INSUFFICIENT_DATA` for a day, that checkbox is why.

---

## 3. Deploy

```bash
cd lite-infra
cp terraform.tfvars.example terraform.tfvars
# edit: billing_alarm_email, ssh_allowed_cidrs (your IP), db_password

terraform init
terraform plan      # read it: one instance, one IP, one alarm
terraform apply
```

Or with the wrapper, which does the same thing plus the follow-up checks:

```bash
bash deploy/lite-aws.sh up        # init + plan + apply
bash deploy/lite-aws.sh ip        # print the static IP and the URL
bash deploy/lite-aws.sh status    # is cloud-init finished? are containers up?
bash deploy/lite-aws.sh logs      # tail /var/log/lite-boot.log over SSH
bash deploy/lite-aws.sh ssh
bash deploy/lite-aws.sh down      # DESTROY (asks for confirmation)
```

**First boot is slow, and that is expected.** cloud-init installs Docker
(~2 min), clones the repo, then either pulls `app_image` or builds the repo's
Dockerfile on a 5%-baseline-CPU instance — **30–60 minutes** for the build. The
app answers `http://<ip>/web/login` when `/var/log/lite-boot.log` ends with
`=== lite boot finished ===`.

To skip the build, publish the image once and set `app_image`:

```bash
docker build -t docker.io/youruser/odoo-invoice-agent:1.0 .
docker push docker.io/youruser/odoo-invoice-agent:1.0
# terraform.tfvars: app_image = "docker.io/youruser/odoo-invoice-agent:1.0"
```

---

## 4. Database, secrets, and why 512 MB works at all

* `DATABASE_URL` is built in `main.tf` from `db_user` / `db_password` /
  `db_name` and passed to the app as an environment variable. The committed
  default password is a **placeholder** — override it:
  `terraform apply -var="db_password=$(openssl rand -base64 24)"`.
* Nothing is written to a committed file; the value lands in
  `terraform.tfvars` (gitignored) or in `terraform.tfstate` (also gitignored).
* PostgreSQL is **never published** on a host port; only the app can reach it,
  over the compose network.

512 MB is below what Odoo + Postgres want (~1 GB combined). Two things make it
survive rather than OOM:

1. `boot.sh.tftpl` creates a **2 GB swapfile** on first boot.
2. The compose file runs **one** Odoo worker, zero cron workers, 8 DB
   connections, and Postgres with 64 MB shared buffers.

The consequence is honest: **throughput is low and the first page load after a
quiet period can take seconds** because it comes back from swap. If that is not
acceptable, the next bundle up is 1 GB; it breaks the $5 target, which is why it
is not the default.

---

## 5. What does not work here

The AI extraction path needs `invoice-ai` + RabbitMQ + Redis (see
`docker-compose.yml` at the repo root). Those are **not** in
`docker-compose.lite.yml`. On this box Odoo runs, the UI works, bills can be
entered by hand — but "upload → extract" will not. That needs the full stack.

---

## 6. Teardown

```bash
bash deploy/lite-aws.sh down      # terraform destroy
```

`terraform destroy` deletes the instance **and its disk**. Take a snapshot
first if the database matters:

```bash
aws lightsail create-instance-snapshot \
  --instance-name odoo-invoice-agent-lite-lite \
  --instance-snapshot-name manual-$(date +%Y%m%d)
```

---

## 7. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `http://<ip>` refuses connection for 30+ min | cloud-init still building the image | `bash deploy/lite-aws.sh logs` and watch for `lite boot finished` |
| Containers restart-looping | OOM before swap was created | `free -h` over SSH; if swap is 0, the swapfile step failed — rerun `/opt/lite-boot.sh` |
| `Error: creating Lightsail Instance: InvalidInputException: blueprint ... does not exist` | blueprint id retired | `aws lightsail get-blueprints --query 'blueprints[].blueprintId'` and set `blueprint_id` |
| Alarm stuck at `INSUFFICIENT_DATA` | billing alerts not enabled in the account | Billing → Billing preferences → Receive Billing Alerts |
| `terraform apply` rejected on `bundle_id` | the validation only allows `nano_*` | intended: this option is capped at the $5 tier |
