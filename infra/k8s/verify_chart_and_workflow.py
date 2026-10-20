"""End-to-end verification of the chart, the deploy workflow and the preflight Job."""
import os
import subprocess
import sys

import yaml

CHART = "infra/helm/odoo-stack"
WORKFLOW = ".github/workflows/deploy.yml"
PREFLIGHT = "infra/k8s/odoo-db-preflight-job.yaml"

failures = []


def check(condition, message):
    if not condition:
        failures.append(message)


ENVS = {
    "local": [],
    "staging": ["-f", CHART + "/values.staging.yaml"],
    "production": [
        "-f", CHART + "/values.production.yaml",
        "--set", "odoo.image.repository=repo/odoo",
        "--set", "odoo.image.tag=t1",
        "--set-string", "config.odooDbHost=db.example.rds.amazonaws.com",
    ],
}

for env, extra in ENVS.items():
    lint = subprocess.run(["helm", "lint", CHART] + extra,
                          capture_output=True, text=True, check=False)
    check(lint.returncode == 0, env + ": helm lint failed: " + lint.stdout + lint.stderr)

    rendered = subprocess.run(["helm", "template", "odoo", CHART] + extra,
                              capture_output=True, text=True, check=False)
    check(rendered.returncode == 0, env + ": helm template failed: " + rendered.stderr)
    if rendered.returncode != 0:
        continue

    docs = [d for d in yaml.safe_load_all(rendered.stdout) if d]
    kinds = {d["kind"]: d for d in docs}
    deploy = kinds["Deployment"]
    pod_spec = deploy["spec"]["template"]["spec"]
    container = pod_spec["containers"][0]
    joined_args = " ".join(container["args"])
    pvc = kinds.get("PersistentVolumeClaim")
    replicas = deploy["spec"]["replicas"]
    access = pvc["spec"]["accessModes"] if pvc else None
    storage_class = pvc["spec"].get("storageClassName") if pvc else None

    print(env.ljust(11), "replicas=" + str(replicas), "access=" + str(access),
          "class=" + str(storage_class))

    check("--workers" in joined_args, env + ": no explicit --workers")
    check("--max-cron-threads" in joined_args, env + ": no explicit --max-cron-threads")
    check(container["readinessProbe"].get("exec") is not None,
          env + ": readiness is not the DB-aware exec probe")
    readiness_cmd = "".join(container["readinessProbe"]["exec"]["command"])
    check("db_server_status=true" in readiness_cmd,
          env + ": readiness probe lost the db_server_status query")
    check(container["livenessProbe"].get("httpGet") is not None,
          env + ": liveness must stay the plain httpGet route")
    check(pod_spec.get("securityContext", {}).get("fsGroup") == 101,
          env + ": pod fsGroup missing, filestore would be unwritable")
    if pvc is not None:
        check(bool(storage_class) or env == "local",
              env + ": PVC relies on a cluster default StorageClass")
        if replicas != 1:
            check(access == ["ReadWriteMany"],
                  env + ": " + str(replicas) + " replicas with " + str(access) + " filestore cannot all mount")
        check(pvc["metadata"]["annotations"].get("helm.sh/resource-policy") == "keep",
              env + ": filestore PVC is not kept across uninstall")

workflow_text = open(WORKFLOW, encoding="utf-8").read()
workflow = yaml.safe_load(workflow_text)

check("/tmp/rendered.yaml" not in workflow_text, "workflow still renders to /tmp")

steps = workflow["jobs"]["deploy"]["steps"]
names = [s.get("name") for s in steps]

# --atomic may still be discussed in comments (it is the reason for the design),
# but it must never reach an actual helm invocation.
for step in steps:
    body = step.get("run") or ""
    check("--atomic" not in body,
          "step '" + str(step.get("name")) + "' still passes --atomic to helm")
for required in ["Check cluster prerequisites", "Preflight database check",
                 "helm upgrade --install", "Collect failure diagnostics",
                 "Revert the failed release"]:
    check(required in names, "workflow is missing step: " + required)

upgrade = next(s for s in steps if s.get("name") == "helm upgrade --install")
check("--wait" in upgrade["run"], "helm upgrade does not use --wait")
check("--timeout" in upgrade["run"], "helm upgrade has no explicit timeout")

preflight_step = next(s for s in steps if s.get("name") == "Preflight database check")
check("odoo-db-preflight-job.yaml" in preflight_step["run"],
      "preflight step does not apply the preflight Job manifest")

diag = next(s for s in steps if s.get("name") == "Collect failure diagnostics")
check(diag.get("if") == "failure()", "diagnostics step does not run on failure")

revert = next(s for s in steps if s.get("name") == "Revert the failed release")
check("helm uninstall" in revert["run"], "revert does not handle a failed first install")
check("helm rollback" in revert["run"], "revert does not roll back to a previous revision")

readme = open(CHART + "/README.md", encoding="utf-8").read()
check("odoo.workers" in readme and "must be explicit" in readme,
      "README does not document the explicit worker count")
check("filestore must be shared" in readme, "README does not document the shared filestore")

print("workflow steps:", len(names))
for name in names:
    print("  -", name)

template = open(PREFLIGHT, encoding="utf-8").read()
values = {
    "JOB_NAME": "odoo-db-preflight-123",
    "NAMESPACE": "odoo",
    "IMAGE_REF": "repo/odoo:sha",
    "DB_HOST": "db.example.rds.amazonaws.com",
    "DB_PORT": "5432",
    "DB_USER": "odoo",
    "DB_NAME": "odoo",
    "DB_SECRET_NAME": "odoo-production-secrets",
    "DB_SECRET_KEY": "ODOO_DB_PASSWORD",
}
substituted = template
for key, value in values.items():
    substituted = substituted.replace("${" + key + "}", value)

check("${" not in substituted, "preflight manifest has an unsubstituted placeholder")

job = yaml.safe_load(substituted)
check(job["kind"] == "Job", "preflight manifest is not a Job")
check(job["metadata"]["namespace"] == "odoo", "preflight Job namespace not substituted")

pod = job["spec"]["template"]["spec"]["containers"][0]
env_map = {e["name"]: e.get("value") for e in pod["env"]}
check(env_map.get("HOST") == values["DB_HOST"], "preflight Job did not substitute the DB host")
check(env_map.get("DBNAME") == "odoo", "preflight Job DBNAME missing")
secret_ref = next(e for e in pod["env"] if e["name"] == "PASSWORD")["valueFrom"]["secretKeyRef"]
check(secret_ref["name"] == values["DB_SECRET_NAME"],
      "preflight Job does not read the password from the Secret")

code = pod["args"][0]
check("ir_module_module" in code, "preflight does not verify the Odoo schema")
check("connect_timeout" in code, "preflight has no connect timeout")

print("preflight Job: substituted and parsed OK")

check(os.path.exists("scripts/smoke-test-eks.sh"),
      "scripts/smoke-test-eks.sh referenced by the workflow does not exist")

if failures:
    print("\nFAILURES:")
    for failure in failures:
        print("  -", failure)
    sys.exit(1)

print("\nAll checks passed.")
