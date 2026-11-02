# Production secrets — External Secrets Operator

`values.production.yaml` renders **no** Secret: it sets
`secret.existingSecret: true` / `secret.name: odoo-production-secrets` and
expects that Secret to already exist. Nothing in the chart or the deploy
workflow creates it, by design — the database password does not live in git, in
a values file, or in a GitHub secret.

The chain is:

```
AWS Secrets Manager  odoo/production
        │  (IRSA: role on the operator's service account)
        ▼
External Secrets Operator  ──syncs──▶  Secret odoo-production-secrets  (ns odoo)
                                              │
                                              ▼
                                    odoo pod env PASSWORD
```

Until this is in place the deploy stops at **Check cluster prerequisites** with
`Secret odoo-production-secrets does not exist in namespace odoo`. That step is
deliberately strict: without the Secret every pod sits in
`CreateContainerConfigError` until the helm wait budget expires, which looks
like a hung rollout rather than a missing prerequisite.

## One-time setup

Run once per cluster, from an admin context. `$ACCOUNT` is the AWS account
number, `$REGION` the cluster region.

```bash
CLUSTER=odoo-eks
REGION=eu-north-1
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
```

### 1. IAM policy — read only the one secret

```bash
aws iam create-policy \
  --policy-name odoo-eso-secrets-read \
  --policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Action": ["secretsmanager:GetSecretValue", "secretsmanager:DescribeSecret"],
      "Resource": "arn:aws:secretsmanager:'"$REGION"':'"$ACCOUNT"':secret:odoo/production*"
    }]
  }'
```

Scoped to one secret on purpose: the operator has no business reading anything
else in the account.

### 2. Install the operator with its role (IRSA)

`eksctl` creates the service account, the IAM role, and the trust policy that
lets only `system:serviceaccount:external-secrets:external-secrets` in this
cluster assume it:

```bash
helm repo add external-secrets https://charts.external-secrets.io
helm repo update

eksctl create iamserviceaccount \
  --cluster "$CLUSTER" --region "$REGION" \
  --namespace external-secrets --name external-secrets \
  --attach-policy-arn "arn:aws:iam::$ACCOUNT:policy/odoo-eso-secrets-read" \
  --override-existing-serviceaccounts --approve

helm upgrade --install external-secrets external-secrets/external-secrets \
  --namespace external-secrets --create-namespace
```

(If the service account was created by the chart instead of `eksctl`, annotate
it with `eks.amazonaws.com/role-arn` and make sure its trust policy matches the
namespace/name in `cluster-secret-store.yaml`.)

### 3. Author the secret value in Secrets Manager

One JSON document, keys matching the chart:

```bash
aws secretsmanager create-secret \
  --name odoo/production \
  --region "$REGION" \
  --secret-string '{
    "ODOO_DB_PASSWORD": "<password of the odoo role on RDS>",
    "POSTGRES_PASSWORD": "<same value>"
  }'
```

Already storing the RDS password elsewhere (e.g. `rds/master-password`)? Point
`remoteRef.key`/`property` in `external-secret.yaml` at it instead of copying
the value around — one source of truth is the point.

### 4. Apply the store and the ExternalSecret

```bash
kubectl apply -f infra/eks/external-secrets/
```

### 5. Prove it synced

```bash
kubectl -n odoo get externalsecret odoo-production-secrets
# NAME                      STORE                STATUS         READY
# odoo-production-secrets   aws-secretsmanager   SecretSynced   True

kubectl -n odoo get secret odoo-production-secrets

# The keys the chart reads:
kubectl -n odoo get secret odoo-production-secrets \
  -o jsonpath='{range $k,$v := .data}{$k}{"\n"}{end}'
# ODOO_DB_PASSWORD
# POSTGRES_PASSWORD
```

`STATUS` other than `SecretSynced` names the failure in its conditions — a
wrong region, a role without the policy, or a secret name that does not exist in
Secrets Manager. The deploy's prerequisite step prints those conditions when the
Secret is missing, so the same information is in the workflow log.

## Why not put the password in a GitHub secret?

Because it would then exist in two systems with different rotation stories. The
chart's contract is "an operator owns this Secret"; the IRSA-scoped role means
the cluster can read exactly one secret in the account, and rotation is a single
`put-secret-value` with no redeploy.
