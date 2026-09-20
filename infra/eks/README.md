# EKS Architecture — Odoo Invoice Agent

This document studies how EKS is structured for this project, mapping the AWS
managed control plane, the worker node group, and the IAM model to the pieces
of the stack that run on it (Odoo pods, PVCs, and the AWS Load Balancer
Controller).

## Control plane (AWS-managed)

The Kubernetes API server, etcd, scheduler, and controller-manager run inside
the AWS-managed control plane. AWS fully operates it: HA across AZs, upgrades,
and patching. You do not SSH into it, and it is billed separately from the
worker nodes. It is reachable from your workstation via `kubectl` once you
`aws eks update-kubeconfig --name odoo-eks --region eu-west-1`.

- **etcd** is encrypted at rest with KMS (EKS default) — the baseline for the
  "secrets at rest" concern raised in the ConfigMap/Secret module.
- The control plane is **not** in your VPC subnets; it lives in an AWS-owned
  network and is exposed via a public or private endpoint. We keep the default
  (public with auth) and rely on IAM + the OIDC issuer for identity.

## Node group (worker nodes)

Worker nodes are EC2 instances in a `managedNodeGroups` entry
(`infra/eks/cluster.yaml`): `m5.large`, 1–4 desired 2, in the **private app
subnets** (`10.20.10.0/24`, `10.20.11.0/24`). Private networking means no public
IP; egress to RDS (5432), ElastiCache (6379), S3, and Secrets Manager goes via
the existing NAT gateway.

- Kubelet + the worker run the pods. They are the only part you scale/patch.
- Each node gets an IAM role for the EKS worker (AmazonEKSWorkerNodePolicy +
  AmazonEKS_CNI_Policy + AmazonEC2ContainerRegistryReadOnly) so it can pull
  images and register with the cluster.
- `aws-ebs-csi-driver` addon (with `withAddonPolicies.ebs: true`) lets the
  cluster provision **EBS volumes for PVCs** — the `pgdata` and `filestore`
  PersistentVolumeClaims from the Helm chart.

## IAM roles for service accounts (IRSA)

Instead of baking static AWS keys into a pod, EKS exposes the cluster's OIDC
issuer (`iam.withOIDC: true` in `cluster.yaml`). An IAM role is created with a
**trust policy** that allows the OIDC provider to assume it only for a specific
service account (e.g. `aws-load-balancer-controller` in `kube-system`). The
service account is annotated with the role ARN, and the pod's projected
service-account token is exchanged for AWS credentials via STS — no static keys
in the manifest or repository.

Two concrete IRSA consumers here:
1. **AWS Load Balancer Controller** — assumes a role holding
   `AWSLoadBalancerControllerIAMPolicy` so it can create/modify ALBs, target
   groups, and security groups (see `aws-load-balancer-controller.md`).
2. **External Secrets Operator** — assumes a role holding
   `secretsmanager:GetSecretValue` on the RDS/Redis secrets so cluster `Secret`
   objects are populated from AWS Secrets Manager without committing secrets.

> The previous EC2-based deployment used a machine IAM role with S3 + Secrets
> Manager read. On EKS that same capability moves to **IRSA** scoped per service
> account — smaller blast radius and no instance profile on a long-lived EC2.

## Where each part of the stack runs

| Component | Where |
|-----------|-------|
| Odoo (Deployment) | EKS worker nodes |
| Postgres | **Amazon RDS** (not in-cluster — see `values.production.yaml`, `postgres.enabled: false` once RDS is the source) |
| Redis | **Amazon ElastiCache** (not in-cluster) |
| Filestore | EBS via PVC (`filestore`) + S3 mirror |
| Ingress | **AWS ALB** provisioned by the AWS Load Balancer Controller |
| Secrets | AWS Secrets Manager → External Secrets Operator → k8s `Secret` |
| DNS | Route 53 (existing `cloud-ai-erp.duckdns.org`) |

## Why manage the data plane with eksctl

`eksctl` declaratively defines the cluster, node group, OIDC, and addons in
`infra/eks/cluster.yaml`. That gives us: versioned cluster config in git, a
repeatable `eksctl create cluster -f`, and IRSA wired at cluster creation —
the same "infrastructure as code" instinct already applied to the Terraform for
VPC/RDS/ElastiCache/S3.
