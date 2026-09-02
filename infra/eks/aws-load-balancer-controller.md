# AWS Load Balancer Controller — install on odoo-eks

The AWS Load Balancer Controller lets Kubernetes `Service`/`Ingress` objects
provision real AWS **Application Load Balancers** (ALBs) / Network Load
Balancers (NLBs) instead of node-port/cloud-provider load balancers. It does
this by reconciling the cluster's service/ingress resources into AWS resources.

It must run with an **IAM role for service accounts (IRSA)** — never long-lived
static keys. The controller assumes a role bound to the `aws-load-balancer-controller`
service account via the cluster OIDC provider.

## Prerequisites
- The EKS cluster is up (`eksctl create cluster -f infra/eks/cluster.yaml`) with OIDC enabled (`iam.withOIDC: true`).
- `kubectl` is pointed at the cluster:
  `aws eks update-kubeconfig --name odoo-eks --region eu-west-1`
- `helm` installed.

## 1. Create the IAM policy for the controller

The controller needs the standard `AWSLoadBalancerControllerIAMPolicy`. Download
the permissive-but-scoped policy and attach it to a dedicated IAM role created
for the controller service account.

```bash
curl -o /tmp/aws-lb-controller-iam-policy.json \
  https://raw.githubusercontent.com/kubernetes-sigs/aws-load-balancer-controller/v2.8.1/docs/install/iam_policy.json

aws iam create-policy \
  --policy-name AWSLoadBalancerControllerIAMPolicy \
  --policy-document file:///tmp/aws-lb-controller-iam-policy.json
```

## 2. Create the IRSA role + service account (eksctl)

```bash
eksctl create iamserviceaccount \
  --cluster odoo-eks \
  --namespace kube-system \
  --name aws-load-balancer-controller \
  --attach-policy-arn arn:aws:iam::$(aws sts get-caller-identity --query Account --output text):policy/AWSLoadBalancerControllerIAMPolicy \
  --override-existing-serviceaccounts \
  --approve
```

This creates the `aws-load-balancer-controller` service account in `kube-system`
plus the IAM role with OIDC trust. The controller pod is annotated to use it.

## 3. Install via Helm

Add the EKS chart repo and install (Helm v3):

```bash
helm repo add eks https://aws.github.io/eks-charts
helm repo update

helm install aws-load-balancer-controller eks/aws-load-balancer-controller \
  -n kube-system \
  --set clusterName=odoo-eks \
  --set serviceAccount.create=false \
  --set serviceAccount.name=aws-load-balancer-controller \
  --set region=eu-west-1 \
  --set vpcId=vpc-XXXXXXXXXXXXXXXX   # <- from terraform output vpc_id
```

## 4. Verify

```bash
kubectl -n kube-system rollout status deployment/aws-load-balancer-controller
kubectl -n kube-system get deploy aws-load-balancer-controller
kubectl logs -n kube-system deploy/aws-load-balancer-controller --tail=20
```

A healthy controller logs the reconcile loop for the cluster; no auth errors.

## 5. Using ALBs

Once installed, annotate the Odoo `Service` (or an `Ingress`) with
`service.beta.kubernetes.io/aws-load-balancer-type: external` — the controller
then provisions an ALB with its own security group, target group, and health
checks pointing at the Odoo pods.

Example annotation block to add to `templates/odoo-service.yaml` (or an Ingress):

```yaml
annotations:
  service.beta.kubernetes.io/aws-load-balancer-type: external
  service.beta.kubernetes.io/aws-load-balancer-scheme: internet-facing
  service.beta.kubernetes.io/aws-load-balancer-nlb-target-type: ip
```

> Because the chart's `odoo-service.yaml` uses `.Values.service.type: ClusterIP`,
> production should either (a) annotate it for the ALB, or (b) add an `Ingress`
> resource that routes to the ClusterIP service. Both are supported by the
> controller installed above.
