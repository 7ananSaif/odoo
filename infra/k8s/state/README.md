# The Three Kinds of State — ConfigMap, Secret & PersistentVolumeClaim

A single, runnable exercise that separates Kubernetes' three kinds of state and
then mounts all three into one **Postgres test Pod**:

| Kind | Object | What it holds | Its lifecycle |
|---|---|---|---|
| Non-sensitive config | **ConfigMap** | hostnames, ports, users, flags, whole config files | edited and rolled independently of any Pod |
| Sensitive values | **Secret** | passwords, tokens, keys | as a ConfigMap, but access-controlled and encryptable at rest |
| Durable disk state | **PersistentVolumeClaim** | the bytes a process writes (a data directory, an upload folder) | outlives every Pod that mounts it |

The point of putting them side by side is that they are *not* the same problem
wearing three hats. Config is re-read, secrets are protected, and disk state is
**persisted** — three different contracts, three different objects.

> The written migration plan for the real Odoo stack is
> [`../config-secret-plan.md`](../config-secret-plan.md); the EKS
> encryption-at-rest decision is
> [`../eks-secrets-at-rest.md`](../eks-secrets-at-rest.md). This file is the
> runbook: how to stand the demo up and prove it works.

---

## What is in this directory

| File | Object(s) | Purpose |
|---|---|---|
| `00-configmap.yaml` | ConfigMap `app-config` | Non-sensitive values **and** a `postgresql.conf` file. |
| `01-secret.yaml` | Secret `db-secret` | The DB password(s). Placeholder only — never a real value. |
| `02-env-probe-pod.yaml` | Pod `env-probe` | Tiny busybox Pod that **asserts** the ConfigMap + Secret resolve as env vars. |
| `03-pvc.yaml` | PersistentVolumeClaim `pg-pvc` | The durable disk, created independently of any Pod. |
| `04-postgres-pod.yaml` | Pod `pg-test` | The deliverable: mounts all three kinds at once. |

---

## 0. Prerequisites

The cluster from the previous exercise ([`../README.md`](../README.md)):

```powershell
kind get clusters                       # -> odoo-local
kubectl config use-context kind-odoo-local
kubectl get storageclass                # -> standard (default) ... rancher.io/local-path
```

`standard` is the default StorageClass, and its provisioner is what turns a PVC
into a real volume on demand. If there were no default class here, `03-pvc.yaml`
would sit `Pending` — that is the precondition to check first.

---

## 1. Apply everything

```powershell
kubectl apply -f infra/k8s/state/
```

```text
configmap/app-config created
secret/db-secret created
pod/env-probe created
persistentvolumeclaim/pg-pvc created
pod/pg-test created
```

---

## 2. Prove the ConfigMap and Secret resolve as env vars (task 2)

`env-probe` runs a script that prints the resolved values and **exits non-zero**
if any expected variable is empty, so a failure shows up as `STATUS=Error` rather
than a wall of echo.

```powershell
kubectl logs env-probe
```

```text
--- ConfigMap (app-config) values, resolved as env vars ---
APP_MODE=production
POSTGRES_DB=odoo
POSTGRES_USER=odoo
ODOO_DB_HOST=postgres
ODOO_DB_PORT=5432
ODOO_DB_USER=odoo
--- Secret (db-secret) value, resolved as an env var ---
POSTGRES_PASSWORD is set: 29 bytes
POSTGRES_PASSWORD sha256: 3e3a8cdabc4fe94c2ac1a53401c95b1fbda825b1d408faffc6ee3ddb5ca62d31
OK: every ConfigMap and Secret key resolved into the container
```

The `env-probe` Pod is `Completed` (it ran to the end and exited 0). To be sure
the Secret value inside the container is **byte-for-byte** what the API holds,
compare the digest it printed against the value decoded from the cluster:

```powershell
# decode the stored value and hash it the same way the pod did
$raw = kubectl get secret db-secret -o jsonpath='{.data.POSTGRES_PASSWORD}'
$val = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($raw))
([BitConverter]::ToString([Security.Cryptography.SHA256]::Create().ComputeHash([Text.Encoding]::UTF8.GetBytes($val))) -replace '-','').ToLower()
# -> 3e3a8cdabc4fe94c2ac1a53401c95b1fbda825b1d408faffc6ee3ddb5ca62d31   (matches)
```

Two config-mount styles are shown across the two Pods, and the difference is the
point:

- `env-probe` reads **one key at a time** with `configMapKeyRef` / `secretKeyRef`.
- `pg-test` additionally mounts `postgresql.conf` as a **file** (see §4).

> `envFrom` (mount *every* key as an env var) is the convenient shorthand — but
> it is unusable for `app-config` as written, because that ConfigMap also holds
> the key `postgresql.conf`, and a dot is not legal in an env-var name. The
> kubelet silently skips such keys. That is exactly why the demo uses explicit
> key references.

---

## 3. See the storage decoupling (task 3)

The PVC binds on first use (the default class is `WaitForFirstConsumer`), so once
`pg-test` is scheduled:

```powershell
kubectl get pvc pg-pvc
```

```text
NAME     STATUS   VOLUME                                     CAPACITY   ACCESS MODES   STORAGECLASS
pg-pvc   Bound    pvc-98cc7224-1b79-466b-a170-012b29dd1225   1Gi        RWO            standard
```

Note the two objects that now exist and their separate lifecycles: the **Pod**
`pg-test` and the **PV/PVC**. Deleting the Pod does not touch the claim.

---

## 4. Prove the ConfigMap file mount and the Secret are live (task 4)

Enter the database Pod and confirm Postgres is *actually running on* the
ConfigMap-supplied config, authenticating with the Secret password, writing to
the PVC:

```powershell
kubectl exec pg-test -- cat /etc/postgresql/postgresql.conf      # the ConfigMap file
kubectl exec pg-test -- psql -U odoo -d odoo -tAc "show config_file"
# -> /etc/postgresql/postgresql.conf
kubectl exec pg-test -- psql -U odoo -d odoo -tAc "show data_directory"
# -> /var/lib/postgresql/data/pgdata          (a subdirectory, i.e. inside the PVC)
kubectl exec pg-test -- psql -U odoo -d odoo -tAc "show shared_buffers"
# -> 128MB                                    (a value that came from the ConfigMap)
```

`show config_file` returning the mounted path is the proof the file mount is not
merely present but **in effect**: `shared_buffers = 128MB` is a tuning value that
exists nowhere but the ConfigMap.

The Secret is proven by connecting over TCP — the local Unix socket uses `trust`,
so only the TCP path exercises the password:

```powershell
kubectl exec pg-test -- sh -c 'PGPASSWORD="$POSTGRES_PASSWORD" psql -h 127.0.0.1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "select current_user, current_database();"'
# -> odoo|odoo
```

> **Windows quoting note.** Nesting a `sh -c '…'` script inside a PowerShell
> single-quoted string that itself contains quotes and `;` is fragile — the
> argument gets re-split and the shell sees fragments. When a probe is more than
> a one-liner, put it in a file and pipe it in, which is deterministic:
> ```powershell
> Get-Content -Raw my-probe.sh | kubectl exec -i pg-test -- sh
> ```
> (The repo's scratch `_k8s_probe.sh` / `_k8s_check_after.sh` were used exactly
> this way while building this exercise.)

---

## 5. Prove the data survives deleting the Pod (task 3, the money shot)

Write a row, delete the Pod, recreate it from the *same* manifest, and read the
row back:

```powershell
# 1) write a row
kubectl exec pg-test -- psql -U odoo -d odoo -c "create table if not exists persistence_check(id serial primary key, note text, written_at timestamptz default now());"
kubectl exec pg-test -- psql -U odoo -d odoo -c "insert into persistence_check(note) values ('row written before the pod was deleted');"
kubectl exec pg-test -- psql -U odoo -d odoo -tAc "select pg_postmaster_start_time();"   # note this

# 2) destroy the Pod (the claim is untouched)
kubectl delete pod pg-test

# 3) recreate it from the same file
kubectl apply -f infra/k8s/state/04-postgres-pod.yaml
kubectl get pod pg-test -w          # wait for 1/1 Running, Ctrl-C
```

Recorded result from this environment:

```text
NAME      READY   STATUS    RESTARTS   AGE
pg-test   1/1     Running   0          78s          # a brand-new Pod

=== the row written BEFORE the delete, still present ===
 id |                  note                  |          written_at
----+----------------------------------------+-------------------------------
  1 | row written before the pod was deleted | 2026-10-16 11:15:18.504445+00

=== server start time (must be AFTER the delete: a brand-new process) ===
2026-10-16 11:15:40.010405+00

=== the PVC-backed data directory is still mounted ===
/dev/sdd       1007G   69G  888G   8% /var/lib/postgresql/data
```

Read those three facts together, because together they are the proof:

1. the **row is still there** — the data outlived the Pod;
2. the **server start time (11:15:40) is later than the row's timestamp
   (11:15:18)** — so this is a genuinely new Postgres process, not the old one
   still running; it read the existing data off the same volume;
3. the **data directory is a mounted filesystem** — the PVC.

That is what "the PVC decouples storage from the Pod's lifecycle" means in
practice: **the Pod is disposable; the claim is not.**

The same claim even keeps its identity across recreation. `kubectl get pvc pg-pvc
-o jsonpath='{.spec.volumeName}'` returns the same `pvc-98cc7224-…` PV name
before and after — the recreated Pod is backed by the *same* volume.

---

## 6. Clean up

```powershell
# remove the demo (the PV is released by the Delete reclaim policy)
kubectl delete -f infra/k8s/state/

# nuke the whole cluster, PVCs and all
kind delete cluster --name odoo-local
```

`kubectl delete -f infra/k8s/state/` removes the Pod, the PVC and the config
objects. With the `Delete` reclaim policy on the `standard` class, deleting the
PVC also deletes the underlying local-path volume — so this is destructive to the
demo data, and the correct way to stop.

---

## 7. The one-paragraph summary

A **ConfigMap** holds non-sensitive configuration and can be projected either as
environment variables or as files; a **Secret** is the same shape with a
protection contract — access-controlled and, on a real cluster,
envelope-encrypted at rest; a **PersistentVolumeClaim** is a *request* for disk
that binds to a **PersistentVolume**, and it is the object that survives the Pod.
This demo builds all three, mounts them into one Postgres Pod (env vars from the
ConfigMap and Secret, `postgresql.conf` as a ConfigMap file, the data directory
as a PVC), verifies the mounts are live, and proves the data outlives
`kubectl delete pod`.

---

## 8. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `container "postgres" ... "root" execution of the PostgreSQL server is not permitted` | a `command:` in the Pod spec **replaced the image ENTRYPOINT**, so `docker-entrypoint.sh` never dropped privileges to the `postgres` user | set only `args:` (keep the entrypoint). See the comment block in `04-postgres-pod.yaml`. |
| `pg-test` stuck `ContainerCreating` for minutes | the node is pulling `postgres:16` for the first time | wait; check `kubectl describe pod pg-test` → Events shows `Pulling image` |
| PVC stuck `Pending` with no consumer | `WaitForFirstConsumer` binding | expected until a Pod mounts it; apply `04-postgres-pod.yaml` |
| PVC stuck `Pending` **even with a consumer** | `storageClassName: ""` (literal empty) opts *out* of dynamic provisioning | omit the field entirely, or set it to the class name (`standard`) |
| `initdb: ... permission denied` | the local-path volume is root-owned and the process is uid 999 | set `securityContext.fsGroup: 999` (already in the manifest) |
| Config value empty in the container | key typo, or a `envFrom` that silently skipped a non-identifier key | prefer explicit `configMapKeyRef`/`secretKeyRef`; check `kubectl describe pod` |
| `psql` over TCP fails with password auth | the Secret was rotated but the Pod was not restarted (env vars are read at start) | `kubectl delete pod` → recreated, or mount as a file and let the app re-read |
