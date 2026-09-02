# Deploy Runbook — odoo-eks (sole path to production)

This is the **only** supported way to ship to production. The old
SSH + `docker compose` EC2 path has been retired (see "Retired path" below).

Deployment is a single `helm upgrade --install` against the **odoo-eks** EKS
cluster, authenticated via **GitHub Actions OIDC → IAM role** (no long-lived
AWS keys stored as secrets).

---

## 1. One-time EKS cluster setup

```bash
# Provision control plane + node group + OIDC + EBS CSI addon
eksctl create cluster -f infra/eks/cluster.yaml

# Point kubectl at the cluster
aws eks update-kubeconfig --name odoo-eks --region eu-west-1

# Install the AWS Load Balancer Controller (ALB support)
#   see infra/eks/aws-load-balancer-controller.md

# Install External Secrets Operator (populates Secret from AWS Secrets Manager)
helm repo add external-secrets https://charts.external-secrets.io
helm repo update
helm install external-secrets external-secrets/external-secrets -n external-secrets --create-namespace
#   create an ExternalSecret for odoo-secrets pointing at
#   arn:aws:secretsmanager:eu-west-1:${ACCOUNT}:secret:odoo-invoice-agent-production/*
```

---

## 2. CI/CD — the deploy workflow

`.github/workflows/deploy.yml` (on push to `production`):

1. **CI** (reused) — lint/test/build.
2. **Configure AWS credentials via OIDC** — `configure-aws-credentials` with
   `role-to-assume: arn:aws:iam::${ACCOUNT}:role/<github-oidc-deploy-role>` and
   `aws-region: eu-west-1`. The OIDC provider trusts the GitHub repo+environment.
3. **Update kubeconfig** — `aws eks update-kubeconfig --name odoo-eks`.
4. **`helm upgrade --install`** the `odoo-stack` chart with the prod values file:
   ```bash
   helm upgrade --install odoo infra/helm/odoo-stack \
     -f infra/helm/odoo-stack/values.production.yaml \
     --namespace odoo --create-namespace --atomic
   ```
5. **Smoke test** — `./scripts/smoke-test.sh <domain>` (HTTPS login + invoice-ai `/healthz`).
6. **Rollback (auto)** — if the smoke test fails, run `helm rollback odoo <previous_revision>`.

---

## 3. Data migration & cutover checklist

The existing app runs against **RDS** (Postgres) and stores attachments in the
**S3 filestore**. The EKS deployment must point at the *same* RDS database and
*carry over* the filestore. Order matters — do it in this exact sequence during
the maintenance window.

### Pre-cutover (once)

- [ ] RDS is reachable from the EKS node group (security group / NACL allow
      `5432` from the app subnets `10.20.10.0/24`, `10.20.11.0/24`).
- [ ] ElastiCache Redis reachable from EKS on `6379` (same subnets).
- [ ] The `odoo` ECR image is built & pushed (`<account>.dkr.ecr.eu-west-1.amazonaws.com/odoo:prod-<sha>`).
- [ ] AWS Secrets Manager holds the RDS password + Odoo admin password
      (already present: `.../rds/master-password`, `.../db_odoo_user`).
- [ ] An `ExternalSecret` is created in-cluster to sync those into the
      `odoo-secrets` Secret.

### Cutover (in order)

1. **Freeze writes** — put the old EC2 Odoo into maintenance/read-only, or
   schedule the cutover off-hours. Note the exact `PREVIOUS_SHA`/tag.
2. **Final DB snapshot** (already migrated to RDS, so this is optional) — if the
   EC2 Postgres is still the source of truth:
   `./scripts/db-migrate.sh` (dumps local Docker Postgres → restores into RDS,
   creates `odoo_user`, runs `ANALYZE`). Verify row counts:
   `account_move`, `account_move_line`, `ir_attachment`, `res_users`.
3. **Sync filestore to S3** — `./scripts/sync-filestore-to-s3.sh`
   (uploads `/var/lib/odoo` attachments to the `attachments` S3 bucket) so the
   EKS `filestore` PVC can be seeded, or mount the same S3 bucket via the
   `s3_storage` addon config.
4. **Point the chart at RDS** — `infra/helm/odoo-stack/values.production.yaml`:
   - `postgres.enabled: false` (no in-cluster Postgres on prod)
   - `config.odooDbHost: <rds-endpoint>` (from `terraform output rds_hostname`)
   - `config.odooDbPort: "5432"`
   - `secret.existingSecret: true` (ExternalSecrets populates it)
   - `odoo.image.repository: <account>.dkr.ecr.eu-west-1.amazonaws.com/odoo`
   - add `service` annotation for the ALB (see `aws-load-balancer-controller.md`).
5. **Deploy** — run the workflow (the `helm upgrade --install` above).
6. **Smoke test** — `scripts/smoke-test.sh <domain>`; confirm Odoo login works,
   invoice-ai `/healthz` is `ok`, and `/web/health` returns 200.
7. **Cut DNS** — flip the Route 53 record (`cloud-ai-erp.duckdns.org`) to the
   new ALB DNS name. Keep the old ALB/EC2 record for the rollback window.
8. **Verify data integrity** — spot-check invoices/attachments visible in Odoo,
   and that `ir_attachment` filestore rows resolve to S3/EBS objects.
9. **Decommission (after 24–48h)** — stop the old EC2 instance, disable the
   `odoo-backup.timer` on EC2, and archive the EC2 deploy role.

### Rollback (sub-5-min target)

- [ ] `helm rollback odoo <previous_revision>` in `odoo` namespace.
- [ ] Restore the Route 53 record to the old ALB/EC2 if DNS was cut.
- [ ] Smoke test the old path.

If the EKS Odoo cannot start at all, the fastest rollback is the DNS flip back
to the old EC2 ALB, which is still running during the rollout window.

---

## 4. Retired path (EC2 / SSH + docker compose)

The previous `.github/workflows/deploy.yml` SSH-invoked a detached shell script
(`scripts/deploy_remote.sh`) that ran `docker compose up -d --build`, upgraded
modules, and health-checked the EC2 app. That path is **removed**:

- No more `appleboy/ssh-action`, `EC2_HOST`, `EC2_USERNAME`, `SSH_PRIVATE_KEY`.
- No more `docker compose` deploys to a single EC2 host.
- `scripts/deploy_remote.sh`, `scripts/cutover.sh`, `scripts/sync-filestore-to-s3.sh`,
  and `scripts/backup.sh` are kept only as legacy/reference; the EKS + Helm path runs
  deploy, rollback, and the filestore sync (via S3 + EBS) from Kubernetes.
- `.github/workflows/deploy.yml` no longer references `appleboy/ssh-action` or any
  `EC2_*` / `SSH_*` secrets.
- `infra/eks/cluster.yaml` + `infra/runbook.md` are the source of truth for shipping
  to production.
