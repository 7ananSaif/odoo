# Research: Encrypting Secrets at Rest on EKS

**Question this answers:** how does EKS store Kubernetes Secrets on disk, what does
"encrypted at rest" actually mean there, and — given that — what should *this*
project do?

**Short answer.** On EKS the question is mostly already answered for us. Every EKS
cluster has its etcd volumes encrypted at the disk level, and every cluster running
**Kubernetes 1.28 or later** additionally envelope-encrypts *all* Kubernetes API
data (Secrets, ConfigMaps, everything) with AWS KMS **by default**, using an
AWS-owned key, at no extra cost and with no action required. The project's cluster
(`full-infra/eks/cluster.yaml`) is `version: "1.30"`, so it already has this. The only
decision left is whether to (a) accept the default AWS-owned key, (b) bring a
customer-managed KMS key (CMK) for control/auditability, and/or (c) keep secrets
out of etcd entirely by sourcing them from **AWS Secrets Manager**. The
recommendation at the bottom is to accept the default *and* add Secrets Manager as
the source of truth for the handful of high-value, externally-rotated credentials.

Sources (AWS docs, retrieved for this exercise):
- [Default envelope encryption for all Kubernetes API Data](https://docs.aws.amazon.com/eks/latest/userguide/envelope-encryption.html)
- [Encrypt Kubernetes secrets with KMS on existing clusters](https://docs.aws.amazon.com/eks/latest/userguide/enable-kms.html)

---

## 1. What "a Secret" is on disk, without any encryption

A Kubernetes `Secret` is an API object. When you `kubectl apply` one, the API
server **stores it in etcd** (the cluster's key/value datastore). Before
encryption enters the picture, the value in that object is only
**base64-encoded**:

```console
$ kubectl get secret db-secret -o jsonpath='{.data.POSTGRES_PASSWORD}' | base64 -d
local-demo-password-change-me
```

Base64 is **encoding, not encryption**. It is trivially reversible and offers
zero confidentiality. Everything below is about the layers that sit *underneath*
that encoding, between the API server and the disk bytes in etcd.

There is a second truth that is more important than the first: **anyone who can
`get` the Secret, and anything running in a Pod that mounts it, sees the
plaintext.** Encryption at rest protects the *disk*; it does not protect the
*running system*. RBAC and not-mounting-what-you-don't-need do that. (See
[§5](#5-what-encryption-at-rest-does--does-not-protect).)

---

## 2. Layer 1 — etcd disk encryption (every EKS cluster, always)

EKS stores etcd (and EBS volumes generally) encrypted at the disk/volume level
with keys the EKS service manages. This is true **for every EKS cluster,
irrespective of Kubernetes version.** Someone who walks out with a physical disk,
or who snapshots the volume, gets ciphertext.

This is the baseline, and it is the answer to "is the data encrypted at rest" if
someone is grading on the loosest definition. It is *not*, on its own, a
satisfying answer for a security review, because:
- the key is managed by the service, not by you;
- it does not give you a per-object key you can revoke;
- it says nothing about the *other* copies of the secret that exist (in git, in a
  `.env`, in a ConfigMap, in a container env var).

---

## 3. Layer 2 — KMS envelope encryption of the API data (1.28+, default)

This is the layer the exercise is really about, and it changed recently.

> **Default envelope encryption for all Kubernetes API Data.** Amazon EKS
> provides default envelope encryption for all Kubernetes API data in EKS
> clusters running Kubernetes version **1.28 or higher**.
> — [AWS docs](https://docs.aws.amazon.com/eks/latest/userguide/envelope-encryption.html)

### 3.1 What "envelope encryption" means

Envelope encryption is two keys instead of one:

1. a **data encryption key (DEK)** encrypts the actual object (the Secret);
2. a **key encryption key (KEK)** — a root key held in AWS KMS — encrypts the DEK.

The DEK never has to be stored in plaintext, because what is stored is the DEK
*encrypted by the KEK*. If an attacker has etcd but not KMS, the DEKs are
useless.

On EKS the mechanism is **KMS provider v2**:

- at API-server startup it generates a **DEK seed** and asks the KMS plugin to
  encrypt it with the remote KEK;
- the **encrypted DEK seed is cached** in the API server's memory;
- each stored object gets its **own single-use DEK**, derived from the cached
  seed via a key-derivation function, and that DEK is used once;
- KMS is called **once at startup** (and on KEK rotation), not per object — the
  caching is what makes this both performant and cheap.

The plaintext exists only transiently, in the kube-apiserver's memory, on
Nitro-based instances whose memory AWS isolates. It is never plaintext on disk.

### 3.2 What is encrypted (and what is not)

| Data | Covered? |
|---|---|
| Secrets | **Yes** |
| ConfigMaps, and all other Kubernetes API objects in etcd | **Yes** (1.28+ default; the old behaviour encrypted only Secrets) |
| Data on worker **nodes** | No — encrypt the node's EBS volume if you need this |
| **EBS/EBS-backed PVC contents** (e.g. the Postgres data directory) | No — this is volume encryption, a separate concern; EKS uses the **EBS CSI driver** and its own encryption story |
| Secrets that your app copied into a **`.env`, a git repo, or a ConfigMap** | No — encryption at rest cannot protect a copy you made yourself |

That last row is the reason [the ConfigMap/Secret plan](config-secret-plan.md)
matters as much as the KMS setting: the strongest etcd encryption in the world is
irrelevant if the same password is sitting in a committed `.env` file.

### 3.3 Which key — AWS-owned by default, or bring your own (CMK)

- **Default:** an **AWS-owned key**. No action, and **no additional cost** for
  the control plane.
- **Optional:** a **customer-managed key (CMK)** you create in KMS, either at
  cluster creation or added to an existing cluster. A CMK gives you control of
  the key policy, the ability to audit cryptographic use via CloudTrail, and the
  ability to disable/rotate it yourself.

CMK cost: **$1/month** to store the key, plus KMS request charges ($0.03 per
10,000 requests, after a 20,000-request free tier); KMS v2's caching keeps the
request count low. One CMK can be shared across several clusters.

### 3.4 The risks a CMK introduces (read this before choosing one)

Enabling encryption **cannot be undone** ("This action is irreversible"), and a
CMK creates a hard dependency between the cluster and the key:

- **Disable the CMK** → the cluster is immediately placed in a **degraded /
  unhealthy** state once the cached DEK is gone; you have **30 days** to
  re-enable it before AWS escalates (and it may be auto-upgraded in the
  meantime).
- **Delete the CMK** → the cluster is **not recoverable** (`KMS_KEY_NOT_FOUND`)
  or permanently degraded. The API server can no longer encrypt new objects or
  decrypt existing ones.
- You are still billed for the degraded cluster's infrastructure.

So a CMK is a real commitment: it demands the same care as the cluster's own
IAM — least-privilege key policies, CloudWatch alarms on key state, and a
documented "who can disable this" answer. AWS even recommends a CloudWatch alarm
on the key.

### 3.5 The old procedure (≤ 1.27) — what changed and why it matters to us

Before 1.28, enabling encryption was an explicit per-cluster action:

```yaml
# eksctl, clusters <= 1.27 only
secretsEncryption:
  keyARN: arn:aws:kms:region:account:key/key
```

```bash
# aws CLI, clusters <= 1.27 only
aws eks associate-encryption-config \
  --cluster-name my-cluster \
  --encryption-config '[{"resources":["secrets"],"provider":{"keyArn":"arn:aws:kms:..."}}]'
```

and existing Secrets had to be force-rewritten to apply the new key:

```bash
kubectl get secrets --all-namespaces -o json \
  | kubectl annotate --overwrite -f - kms-encryption-timestamp="$(date +%s)"
```

Two changes on 1.28+:

1. It is **on by default** — no `associate-encryption-config` needed. The
   `resources` field of `EncryptionConfig` is now **deprecated** and ignored
   (still accepted for backward compatibility; responses still echo
   `["secrets"]`), because *everything* is encrypted, not just secrets.
2. Existing non-encrypted objects are migrated by the service using the
   `eks:kms-storage-migrator` ClusterRole — you do not have to rewrite them
   yourself.

**This is why the "enable it, then rotate all secrets" runbook you may have seen
in older material does not apply to this project** — the cluster is 1.30.

---

## 4. Layer 3 — keeping the secret out of etcd entirely (Secrets Manager)

Envelope encryption protects the copy *inside etcd*. It does not give you
central rotation, versioning, cross-region replication, or a single audit trail
for "who read the production DB password". For that, the secret's **source of
truth** moves to **AWS Secrets Manager** (or SSM Parameter Store `SecureString`),
and the cluster stops being the place it is authored.

There are two idiomatic bridges, both running with **IRSA** (IAM Roles for
Service Accounts — the EKS OIDC pattern already enabled in
`full-infra/eks/cluster.yaml` via `iam.withOIDC: true`, and described in
`full-infra/eks/README.md`):

### 4.1 External Secrets Operator (ESO) — sync into a k8s `Secret`

ESO watches an `ExternalSecret` object and writes the fetched value into a
normal Kubernetes `Secret`, which pods consume exactly as they do today:

```yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: odoo-secrets
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: aws-secrets-manager
    kind: ClusterSecretStore
  target:
    name: odoo-secrets        # <- the k8s Secret pods already mount
  data:
    - secretKey: POSTGRES_PASSWORD
      remoteRef:
        key: odoo-invoice-agent-production/rds/master-password
        property: password
```

- **Win:** zero application change (the pod keeps mounting a `Secret`), central
  rotation, one audit trail in Secrets Manager/CloudTrail.
- **Caveat:** the materialised k8s `Secret` still exists in etcd — so you still
  want envelope encryption under it. The two layers are complementary, not
  alternatives.

### 4.2 Secrets Store CSI Driver — mount as a volume, no `Secret` object

The CSI driver mounts secrets from Secrets Manager directly into the pod's
filesystem (optionally without ever creating a k8s `Secret`, via
`syncSecret.enabled=false`):

```yaml
# volumeMounts: a file at /mnt/secrets/POSTGRES_PASSWORD
volumes:
  - name: secrets-store
    csi:
      driver: secrets-store.csi.k8s.io
      readOnly: true
      volumeAttributes:
        secretProviderClass: odoo-secrets
```

- **Win:** the credential is never persisted as a Kubernetes object at all.
- **Caveat:** your app must read secrets from **files**, not environment
  variables. That is a code change — and it is genuinely more secure, because
  environment variables leak into `/proc/<pid>/environ`, `kubectl describe pod`,
  crash dumps, and child processes.

### 4.3 Which one for this stack

The Odoo stack is env-var driven (Compose `env_file`/`environment`, and the
image's entrypoint reads `HOST`/`USER`/`PASSWORD`). Moving to the CSI driver
means rewriting how Odoo and the invoice-ai service read configuration. **ESO is
the pragmatic bridge**: it satisfies "secrets are not authored in git or in a
manifest" while keeping the env-var contract the app already has. Revisit the
CSI driver only if the threat model requires "the credential is never a
Kubernetes object".

---

## 5. What encryption at rest does / does not protect

| Threat | Covered by etcd+KMS encryption? |
|---|---|
| Stolen/leaked EBS snapshot or physical disk | **Yes** |
| Someone with direct etcd access but not KMS | **Yes** (they see encrypted DEKs) |
| A user with RBAC `get secrets` in the namespace | **No** — RBAC controls this |
| A compromised pod that mounts the Secret | **No** — it sees plaintext by design |
| The secret copied into a committed `.env` or a ConfigMap | **No** |
| An over-broad IAM policy that can `GetSecretValue` | **No** — that is IAM |

The net: **encryption at rest is one layer of defence in depth, not a substitute
for RBAC, least-privilege IAM, and not handing secrets to pods that don't need
them.**

---

## 6. Decision for this project

| Concern | Decision | Why |
|---|---|---|
| API-data / Secret encryption in etcd | **Rely on the EKS 1.28+ default** (AWS-owned key). Do nothing. | Cluster is 1.30; it is already on, free, and needs no permissions. This is the correct "use what the platform gives you" answer. |
| Customer-managed KMS key (CMK) | **Not now; documented as the upgrade path.** | A CMK buys key-policy control and CloudTrail visibility at $1/month, but creates an irrecoverable dependency (disable/delete = degraded or dead cluster). Not worth it until a compliance requirement, an external audit, or a key-rotation policy demands it. If adopted: create the CMK, set a CloudWatch alarm on its state, and scope `kms:CreateGrant`/`kms:Decrypt` least-privilege. |
| High-value, externally-owned credentials (`ANTHROPIC_API_KEY`, `INVOICE_AI_VOYAGE_API_KEY`, RDS master password) | **Source from AWS Secrets Manager via External Secrets Operator**, with IRSA. | These rotate outside the cluster and must have one audit trail. ESO keeps the app's env-var contract intact. `full-infra/terraform/ssm.tf` + `iam.tf` already provision the parameter/policies; `full-infra/eks/README.md` already names ESO as an IRSA consumer. |
| Secrets authored in the repo | **Never.** `.env` stays a local-only, git-ignored file; `.env.example` carries placeholders; real values live in Secrets Manager. | Encryption at rest cannot protect a copy you committed. This is the highest-leverage change in the whole plan. |
| The `db-secret` used by the local kind exercise (`full-infra/k8s/state/01-secret.yaml`) | **Keep as a documented placeholder.** | It is a throwaway value for a laptop cluster; production never renders it (`secret.existingSecret: true` in the Helm chart — see `full-infra/helm/odoo-stack/README.md`). |

**One-line version:** let EKS do the etcd encryption (it already does, by
default, for free); put the credentials that rotate in **AWS Secrets Manager**
and sync them in with **ESO under IRSA**; and treat "never commit the value" as
the real control, because no amount of disk encryption helps if the password is
in git.

---

## 7. Verifying the posture (commands, for when there is a real cluster)

```bash
# Is secrets/API-data encryption configured on the cluster, and with which key?
aws eks describe-cluster --name odoo-eks --region eu-north-1 \
  --query 'cluster.encryptionConfig'

# Which key does the API server report? (path is --encryption-provider-config only
# on self-managed clusters; on EKS the config is service-managed and visible via
# the encryptionConfig above plus CloudTrail for CMK usage)

# Who can read a given secret — the RBAC control that KMS does NOT provide:
kubectl auth can-i get secrets -n default --as system:serviceaccount:default:some-sa

# Prove the External Secret synced:
kubectl get externalsecret -A
kubectl get secret odoo-secrets -o jsonpath='{.data.POSTGRES_PASSWORD}' | base64 -d | wc -c
```

CloudTrail is the control-plane audit trail; for CMK usage it is the record of
every KMS `Decrypt`/`Encrypt` the API server performed.
