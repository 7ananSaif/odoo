# Kubernetes Core Concepts — Pods, Deployments & Services (local kind cluster)

The first Kubernetes exercise: stand up a real control plane on this laptop with
**kind**, run a plain **Nginx Deployment** behind a **Service**, reach it from
the host with `kubectl port-forward`, and map the existing Docker Compose stack
onto its future Kubernetes objects. No AWS involved.

> The written map of the Compose stack lives in
> [`compose-to-k8s-mapping.md`](compose-to-k8s-mapping.md). This file is the
> runbook: how to build the cluster and prove it works.

---

## What is in this directory

| File | Purpose |
|---|---|
| `kind-cluster.yaml` | kind cluster definition (name `odoo-local`, host port mapping). |
| `nginx.yaml` | Nginx **Deployment** + **Service** — the core exercise. |
| `compose-to-k8s-mapping.md` | Every Compose service → its future Kubernetes object. |
| `config-secret-plan.md` | Every `.env` key → ConfigMap / Secret / AWS Secrets Manager (+ repo wiring & EKS decision). |
| `state/` | ConfigMap + Secret + PVC **+ the Postgres test Pod** that mounts all three — runbook: [`state/README.md`](state/README.md). |
| `eks-secrets-at-rest.md` | Research: how EKS encrypts secrets at rest, and this cluster's decision. |
| `kind-node-image-pull.py` | Recovery tool: fetches the node image with resume (see Troubleshooting). |
| `odoo-db-preflight-job.yaml` | The Job `.github/workflows/deploy.yml` runs before `helm upgrade`: proves the RDS endpoint, the Secret and the Odoo schema are reachable. |
| `rendered_config.py` | Reads one value (ConfigMap entry, PVC field) out of a `helm template` render — how the deploy publishes the DB host it actually rendered. |
| `verify_chart_and_workflow.py` | End-to-end check: `helm lint`/`helm template` per environment, the workflow's steps, the preflight Job, and the render reader. Run it after touching the chart or the deploy workflow. |
| `verify_workflow_shell.py` | Static guard: every shell variable a deploy step reads is declared or published to `$GITHUB_ENV` (the `DB_HOST: unbound variable` class of failure). |

---

## 0. Prerequisites

| Tool | Where it comes from | Check |
|---|---|---|
| Docker Desktop (Linux engine) | Docker Desktop, **running** | `docker version` |
| `kubectl` | ships with Docker Desktop | `kubectl version --client` |
| `kind` | see below | `kind version` |

`kubectl` is already on PATH via Docker Desktop
(`C:\Program Files\Docker\Docker\resources\bin\kubectl.exe`). `kind` is not
shipped with anything, so install it once:

```powershell
# Option A - winget
winget install --id Kubernetes.kind --silent --accept-package-agreements --accept-source-agreements

# Option B - direct download
$dir = "$env:USERPROFILE\bin"
New-Item -ItemType Directory -Force -Path $dir | Out-Null
curl.exe -L -f --retry 5 --retry-all-errors `
    -o "$dir\kind.exe" `
    https://kind.sigs.k8s.io/dl/v0.33.0/kind-windows-amd64

$up = [Environment]::GetEnvironmentVariable("Path", "User")
if ($up -notlike "*$dir*") { [Environment]::SetEnvironmentVariable("Path", "$up;$dir", "User") }
$env:Path = "$dir;$env:Path"

kind version      # -> kind v0.33.0 windows/amd64
```

Make sure **Docker Desktop is running** first — a stopped daemon gives
`Cannot connect to the Docker daemon`.

---

## 1. Bring up the cluster

```powershell
kind create cluster --config infra/k8s/kind-cluster.yaml --image kindest/node:v1.37.0
```

What this does, in order:

1. Ensures the node image `kindest/node:v1.37.0` is present (≈1 GB, one time
   only — Docker caches it, so later clusters are instant).
2. Starts a Docker container that runs `kubelet`, `containerd`, and the whole
   control plane (API server, scheduler, controller-manager, etcd) inside it.
3. Generates a kubeconfig and merges it into `~/.kube/config`, setting the
   current context to `kind-odoo-local`.

**Why `--image` is passed explicitly.** Without it, kind looks for the node
image under its digest-pinned reference
(`kindest/node:v1.37.0@sha256:a1ed56cf…`). Docker Desktop's **containerd image
store** re-digests an image when it is loaded, so that lookup misses a locally
present copy and kind falls back to a registry pull. Naming the image removes
the digest from the lookup and kind uses the local copy. On a Docker setup with
the classic (non-containerd) image store, the flag is harmless either way.

Confirm the control plane is alive:

```powershell
kubectl get nodes
# NAME                       STATUS   ROLES           AGE   VERSION
# odoo-local-control-plane   Ready    control-plane   30s   v1.37.0
```

`STATUS=Ready` is the goal. `kind get clusters` should list `odoo-local`.

---

## 2. Run Nginx

```powershell
kubectl apply -f infra/k8s/nginx.yaml
```

Watch the Pods come up:

```powershell
kubectl get pods -l app=nginx -w
# NAME                                READY   STATUS    RESTARTS   AGE
# nginx-deployment-<hash>-abcde       1/1     Running   0          4s
# nginx-deployment-<hash>-fghij       1/1     Running   0          4s
```

`Ctrl-C` stops the watch. `READY 1/1` and `STATUS Running` is the success state.
The first start may sit in `ContainerCreating` for a few seconds while the node
pulls `nginx:alpine` from Docker Hub.

> **Note — `kind load docker-image` does not work here.** On Docker Desktop with
> the containerd image store, `kind load docker-image nginx:alpine` fails with
> `ctr: content digest … not found`, because the tarball `docker save` produces
> references a manifest digest that is not in the payload. Simply let the node
> pull the image — the deployment does that on its own.

See the object chain the Deployment created for you:

```powershell
kubectl get deployment,replicaset,pods -l app=nginx
kubectl describe deployment nginx-deployment
```

**Prove the self-healing** — delete a Pod and watch a new one appear with a new
name and a new IP:

```powershell
$pod = kubectl get pods -l app=nginx -o jsonpath="{.items[0].metadata.name}"
kubectl delete pod $pod
kubectl get pods -l app=nginx -o wide
```

The ReplicaSet notices the replica count dropped and immediately creates a
replacement. That is the entire value of a Deployment: you describe the desired
state, a controller makes it true and keeps it true.

---

## 3. Reach the Service from the host

The Service is `ClusterIP`, so it is only reachable from inside the cluster.
`kubectl port-forward` opens a tunnel from your machine to it — the Kubernetes
equivalent of the Week-0 "can I curl the EC2 box" check.

```powershell
# leave this running in its own terminal
kubectl port-forward svc/nginx-service 8080:80

# in another terminal
curl.exe -i http://127.0.0.1:8080
# HTTP/1.1 200 OK
# Server: nginx/<version>
# <title>Welcome to nginx!</title>
```

If the local port is already taken (on this machine something else owns `8080`),
pick any other free port — the mapping is `localhost:<any-port> -> service:80`:

```powershell
kubectl port-forward svc/nginx-service 18080:80
curl.exe -i http://127.0.0.1:18080
```

The `svc/nginx-service` part is what makes this a *Service* test and not a Pod
test: you never named a Pod. Behind the tunnel, kube-proxy load-balances across
whatever Pods the Service currently selects. Delete a Pod while the tunnel is
open and the next request still succeeds — that is the stable identity doing its
job.

### Optional: reach it without port-forward

`kind-cluster.yaml` maps host `8081` → node port `30080`. Add a `NodePort` (or
change the existing Service) and you can skip the tunnel:

```yaml
spec:
  type: NodePort
  ports:
    - name: http
      port: 80
      targetPort: http
      nodePort: 30080
```

```powershell
kubectl apply -f infra/k8s/nginx.yaml
curl.exe -i http://127.0.0.1:8081
```

---

## 4. Clean up

```powershell
kind delete cluster --name odoo-local
```

This deletes the node container and everything inside it (including any
PersistentVolumeClaims). The `kindest/node` image stays in Docker's cache, so
re-creating the cluster is fast.

---

## 5. Next exercise — the three kinds of state (ConfigMap, Secret, PVC)

`nginx.yaml` above is stateless: destroy its Pods and nothing is lost. The next
exercise adds the three objects that carry state, and proves each one:

- **ConfigMap** and **Secret** — configuration, non-sensitive and sensitive,
  consumed as env vars *and* as a mounted file
  (`state/00-configmap.yaml`, `state/01-secret.yaml`,
  `state/02-env-probe-pod.yaml`).
- **PersistentVolumeClaim** — durable disk, proven to outlive the Pod that
  mounts it (`state/03-pvc.yaml`, `state/04-postgres-pod.yaml`).

```powershell
kubectl apply -f infra/k8s/state/
kubectl get pod,configmap,secret,pvc -l app.kubernetes.io/component=state-demo
```

Full runbook — including the delete-and-recreate persistence proof with its
recorded output — is [`state/README.md`](state/README.md).

> Encryption at rest is a different axis from *which object holds what*. The EKS
> decision (default KMS envelope encryption; AWS Secrets Manager via External
> Secrets) is [`eks-secrets-at-rest.md`](eks-secrets-at-rest.md).

---

## The object model, in one paragraph

A **Pod** is the smallest deployable unit — one or more containers that share a
network namespace and storage. You almost never create one directly. A
**Deployment** declares "N replicas of this Pod template" and owns a
**ReplicaSet**, which owns the Pods; the Deployment adds rolling updates and
rollbacks on top. Because Pods are continuously replaced (new name, new IP),
you never address them directly — a **Service** gives a stable virtual IP and
DNS name that selects Pods by label and load-balances across them. Delete a Pod,
the Deployment replaces it, and the Service points at the replacement without
any client noticing.

---

## Verified result (recorded from this environment)

```
$ kubectl get nodes
NAME                       STATUS   ROLES           AGE   VERSION
odoo-local-control-plane   Ready    control-plane   3m    v1.37.0

$ kubectl get deployment,replicaset,service,endpoints -l app=nginx
deployment.apps/nginx-deployment   2/2     2     2
replicaset.apps/nginx-deployment-… 2       2     2
service/nginx-service   ClusterIP   10.96.100.1   <none>   80/TCP
endpoints/nginx-service           10.244.0.5:80,10.244.0.6:80

$ kubectl port-forward svc/nginx-service 18080:80   # then:
$ curl.exe -i http://127.0.0.1:18080
HTTP/1.1 200 OK
Server: nginx/<version>
<title>Welcome to nginx!</title>

# deleting one Pod -> ReplicaSet created a replacement with a new IP
pod "nginx-deployment-…-6bszb" deleted
nginx-deployment-…-km2rz   1/1   Running   10.244.0.7
nginx-deployment-…-wpfbm   1/1   Running   10.244.0.6
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `Cannot connect to the Docker daemon` | Docker Desktop not running | start Docker Desktop, wait for "Engine running" |
| `kind create cluster` tries to pull and hangs on `Ensuring node image` | containerd image store re-digesting the local copy | pass `--image kindest/node:v1.37.0` |
| `kind load docker-image` → `ctr: content digest … not found` | containerd image store vs. `docker save` output | don't load; let the node pull the image from the registry |
| Pod stuck `ImagePullBackOff` | node cannot reach the registry | check the node has network; `kubectl describe pod <name>` → Events |
| Pod stuck `Pending` | no room on the node / image still pulling | `kubectl describe pod <name>` and read Events |
| `port-forward` errors: `address already in use` | another process owns that local port | map a different one: `kubectl port-forward svc/nginx-service 18080:80` |
| `kubectl` talks to the wrong cluster | stale context | `kubectl config use-context kind-odoo-local` |
| Need to re-create the node image after a `docker system prune` | large layer pulls fail mid-transfer on a slow link | `python infra/k8s/kind-node-image-pull.py` then `docker load` (see that file's docstring) |

Useful commands while learning:

```powershell
kubectl get all                      # everything in the default namespace
kubectl get endpoints nginx-service  # the Pod IPs the Service is routing to
kubectl logs -l app=nginx
kubectl exec -it deploy/nginx-deployment -- sh     # shell into a Pod
kubectl get events --sort-by=.lastTimestamp
