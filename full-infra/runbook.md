# Deploy Runbook — odoo-eks (sole path to production)

This is the **only** supported way to ship the Odoo stack to production. The old
SSH + `docker compose` EC2 path for Odoo has been retired (§4). The one workload
still deployed over SSH is `invoice-ai`, which the Helm chart does not cover —
see §2, "What still deploys outside Helm".

Deployment is a single `helm upgrade --install` against the **odoo-eks** EKS
cluster, authenticated via **GitHub Actions OIDC → IAM role** (no long-lived
AWS keys stored as secrets).

---

## 1. One-time EKS cluster setup

```bash
# Provision control plane + node group + OIDC + EBS CSI addon
eksctl create cluster -f full-infra/eks/cluster.yaml

# Point kubectl at the cluster
aws eks update-kubeconfig --name odoo-eks --region eu-north-1

# --- Map the GitHub OIDC deploy role into the cluster (required, once) ------
# The deploy workflow assumes an IAM role through OIDC and then talks to the
# API server AS that role. AWS credentials are not cluster credentials: until
# the role is mapped, the first kubectl call in the deploy fails with
#
#   error: unable to recognize "STDIN": the server has asked for the client to
#   provide credentials
#
# which names neither the role nor the missing mapping. Run this from an admin
# context, once per cluster (and again if the role is recreated with a new ARN):
ROLE_ARN=$(aws iam get-role --role-name <github-oidc-deploy-role> \
  --query Role.Arn --output text)
aws eks create-access-entry --cluster-name odoo-eks --region eu-north-1 \
  --principal-arn "$ROLE_ARN" --type STANDARD
aws eks associate-access-policy --cluster-name odoo-eks --region eu-north-1 \
  --principal-arn "$ROLE_ARN" \
  --policy-arn arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy \
  --access-scope type=cluster

# A cluster whose aws-auth ConfigMap is still authoritative (created without
# authentication_mode=API_AND_CONFIG_MAP) uses an identity mapping instead:
eksctl create iamidentitymapping --cluster odoo-eks --region eu-north-1 \
  --arn "$ROLE_ARN" --group system:masters --username github-deploy

# Install the AWS Load Balancer Controller (ALB support)
#   see full-infra/eks/aws-load-balancer-controller.md

# Install External Secrets Operator (populates Secret from AWS Secrets Manager)
helm repo add external-secrets https://charts.external-secrets.io
helm repo update
helm install external-secrets external-secrets/external-secrets -n external-secrets --create-namespace
#   create an ExternalSecret for odoo-secrets pointing at
#   arn:aws:secretsmanager:eu-north-1:${ACCOUNT}:secret:odoo-invoice-agent-production/*
```

---

## 2. CI/CD — the deploy workflow

`.github/workflows/deploy.yml` (on push to `production`):

1. **CI** (reused) — lint/test/build.
2. **Configure AWS credentials via OIDC** — `configure-aws-credentials` with
   `role-to-assume: arn:aws:iam::${ACCOUNT}:role/<github-oidc-deploy-role>` and
   `aws-region: eu-north-1`. The OIDC provider trusts the GitHub repo+environment.
3. **Update kubeconfig, then verify cluster access** — `aws eks update-kubeconfig
   --name odoo-eks`, followed immediately by a cluster-scoped read
   (`kubectl get namespace odoo`) *before* the image wait. Assuming the deploy
   role is not the same as being a cluster identity (§1), so this step separates
   the three ways it goes wrong: `401` (role not mapped — prints the caller ARN
   and the exact `create-access-entry` / `iamidentitymapping` command), `403`
   (mapped but not authorized — needs the cluster admin access policy), and a
   missing namespace (fine; the release creates it). Without it the first
   symptom is the same 401 from `kubectl apply` after fifteen minutes of waiting
   for an image.
4. **Chart gate** — `helm lint` and `helm template` the chart with the prod values
   *before* the release is touched, so a broken template fails in seconds instead
   of mid-rollout.
5. **Resolve the image this commit built** — the pipeline deploys
   `<repo>:${{ github.sha }}`, the tag `docker-push.yml` pushed. The repository
   comes from the repo variable `ODOO_IMAGE_REPOSITORY` (ECR) or, if unset, from
   `secrets.DOCKERHUB_USERNAME`/odoo. It then waits (up to 15 min) for the tag to
   appear in the registry, because the image build is a *separate* workflow on the
   same push and can finish after the deploy starts.
6. **`helm upgrade --install`** the `odoo-stack` chart with the prod values file,
   the image injected as flags so the values file never pins a stale tag:
   ```bash
   helm upgrade --install odoo full-infra/helm/odoo-stack \
     -f full-infra/helm/odoo-stack/values.production.yaml \
     --namespace odoo --create-namespace \
     --set odoo.image.repository=<repo> --set odoo.image.tag=<sha> \
     --set-string config.odooDbHost=<rds-endpoint> \
     --wait --timeout 12m
   ```
   `config.odooDbHost` is the host the workflow read back out of its own
   `helm template` render (`secrets.ODOO_DB_HOST` in, rendered ConfigMap out,
   published to `$GITHUB_ENV`), so the RDS endpoint never has to be committed to
   the values file and the preflight Job inspects exactly what is deployed.

   `--atomic` is deliberately **not** used: it uninstalls the release the moment
   the wait budget expires, taking the pods, events and container logs with it -
   the only evidence of why it never became ready. The workflow dumps diagnostics
   first, then rolls back to the previous revision (or uninstalls, if this run
   created the release).
7. **Rollout assert** — resolves the Deployment by label
   (`app.kubernetes.io/instance=odoo, app.kubernetes.io/component=odoo`) and runs
   `kubectl rollout status` on it. `--wait` already blocked until the Deployment
   reported ready, so this is a cheap explicit re-check against the API server.
   It is resolved rather than hardcoded because the
   rendered name is `odoo-odoo-stack-odoo`, not `odoo-odoo` — `odoo-stack.fullname`
   only collapses to the release name when the release name *contains* the chart
   name, which `odoo` does not.
8. **Smoke test** — `./scripts/smoke-test-eks.sh <domain>`: TLS handshake,
   certificate expiry, and the Odoo login page rendering (which itself proves the
   pod can reach RDS). Not `smoke-test.sh` — that one probes the local compose
   topology (invoice-ai, RabbitMQ, Prometheus on localhost) and cannot pass here.
9. **Rollback (auto)** — only when the *smoke step itself* failed:
   `helm rollback odoo <previous_revision> --timeout 5m`, then a rollout assert
   proving the rollback actually landed. The 5-minute bar matches the old EC2
   path; beyond it, §3 "Rollback" takes over manually. A release with a single
   revision reports "nothing to roll back to" instead of silently "rolling back"
   to the revision already live.

### Required configuration

| Kind | Name | Purpose |
|---|---|---|
| Secret | `AWS_EKS_DEPLOY_ROLE_ARN` | IAM role assumed via OIDC (no long-lived keys) |
| Secret | `DOMAIN` | public hostname the smoke test checks |
| Secret | `ODOO_DB_HOST` | RDS endpoint, injected as `config.odooDbHost` (optional if it is filled into the values file) |
| Secret | `DOCKERHUB_USERNAME` / `DOCKERHUB_TOKEN` | registry auth when images come from Docker Hub |
| Variable | `ODOO_IMAGE_REPOSITORY` | image repository to deploy, e.g. `<account>.dkr.ecr.eu-north-1.amazonaws.com/odoo` |

The first step of the job fails with an actionable message if a required one is
missing, and warns about any `<placeholder>` left in `values.production.yaml`.

### What still deploys outside Helm (deliberately)

- **`invoice-ai`** — `invoice-ai-deploy.yml` (triggered by `invoice-ai CI`) still
  ships over SSH + `docker compose` to the EC2 host. It is a *separate service*
  that the `odoo-stack` chart does not render, so retiring its pipeline without a
  chart for it would leave it with no way to production. It owns its own image,
  health gate (`/healthz` + `build_sha` match) and rollback. Folding it into the
  cluster is a separate piece of work.
- **`db-collation-repair.yml`** — manual (`workflow_dispatch`) repair for the
  collation-version mismatch on the *EC2 host's* local Postgres volume. On EKS the
  database is RDS, so it is EC2-only; it stays during the rollback window and is
  removed with the EC2 host.

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
- [ ] The `odoo` ECR image is built & pushed (`<account>.dkr.ecr.eu-north-1.amazonaws.com/odoo:prod-<sha>`).
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
4. **Point the chart at RDS** — `full-infra/helm/odoo-stack/values.production.yaml`:
   - `postgres.enabled: false` (no in-cluster Postgres on prod)
   - `config.odooDbHost: <rds-endpoint>` (from `terraform output rds_hostname`)
   - `config.odooDbPort: "5432"`
   - `secret.existingSecret: true` (ExternalSecrets populates it)
   - `odoo.image.repository: <account>.dkr.ecr.eu-north-1.amazonaws.com/odoo`
   - add `service` annotation for the ALB (see `aws-load-balancer-controller.md`).
5. **Deploy** — run the workflow (the `helm upgrade --install` above).
6. **Smoke test** — `scripts/smoke-test-eks.sh <domain>`: TLS handshake,
   certificate expiry, and the Odoo login page actually rendering. (`invoice-ai`
   is not part of the cluster deployment; its own pipeline health-gates it.)
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

- `.github/workflows/deploy.yml` references no `appleboy/*` action, no `EC2_*`
  or `SSH_*` secret, and runs no `docker compose`.
- Those EC2 credentials still exist for exactly **one** other workflow,
  `invoice-ai-deploy.yml`, which ships the invoice-ai service to the EC2 host
  (scoped in §2). They disappear when invoice-ai is moved into the cluster.
- The Odoo host is no longer deployed to over SSH by any workflow.
- `scripts/deploy_remote.sh`, `scripts/cutover.sh`, `scripts/sync-filestore-to-s3.sh`,
  and `scripts/backup.sh` are kept only as legacy/reference; the EKS + Helm path runs
  deploy, rollback, and the filestore sync (via S3 + EBS) from Kubernetes.
- `full-infra/eks/cluster.yaml` + `full-infra/runbook.md` are the source of truth for shipping
  to production.
