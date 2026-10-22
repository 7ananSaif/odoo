"""End-to-end verification of the chart, the deploy workflow and the preflight Job."""
import os
import shutil
import subprocess
import sys
import tempfile

import yaml

from verify_workflow_shell import check_workflow as check_workflow_shell

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
    check(container["startupProbe"].get("tcpSocket") is not None,
          env + ": startup must be tcpSocket; /web/health 500s while the database has no schema")
    check(container["livenessProbe"].get("tcpSocket") is not None,
          env + ": liveness must be tcpSocket, or an empty database crash-loops every pod")
    check(container["livenessProbe"].get("httpGet") is None,
          env + ": liveness must not use /web/health, which depends on the database")
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

# ---------------------------------------------------------------------------
# DB host plumbing.
#
# The deploy died with "line 13: DB_HOST: unbound variable": the
# "Check cluster prerequisites" step printed $DB_HOST under `set -u`, but it
# had never been given the value. The fix is that the render step publishes the
# host it actually rendered (read back out of rendered.yaml) to $GITHUB_ENV,
# and nothing else declares DB_HOST - one value, one source.
# ---------------------------------------------------------------------------
render_step = next(s for s in steps if s.get("name") == "helm template (render check)")
check("DB_HOST=" in render_step["run"] and "GITHUB_ENV" in render_step["run"],
      "render step does not publish the rendered DB host to $GITHUB_ENV")

# The publish line must sit *inside* the render script, after the manifest was
# written - publishing a value the step never rendered would be worse than not
# publishing one at all.
check(render_step["run"].index("rendered.yaml") <
      render_step["run"].index('echo "DB_HOST='),
      "render step publishes DB_HOST before it renders, so the value cannot "
      "come from rendered.yaml")

for step in steps:
    declared = set((step.get("env") or {}).keys())
    check("DB_HOST" not in declared,
          "step '" + str(step.get("name")) + "' declares its own DB_HOST; it "
          "would shadow the value published to $GITHUB_ENV, so the deploy "
          "could validate one database while pointing Odoo at another")

for consumer in ["Check cluster prerequisites", "helm upgrade --install"]:
    consumer_step = next(s for s in steps if s.get("name") == consumer)
    check("DB_HOST" in consumer_step["run"],
          consumer + ": does not gate on DB_HOST - an empty host silently "
          "falls back to the in-cluster Postgres Service production never runs")

# ---------------------------------------------------------------------------
# Static shell guard: no step may read a variable from nowhere.
#
# Run against the real workflow, and the guard itself is exercised against a
# deliberately broken one, so a regex that quietly stops matching cannot make
# the check vacuous.
# ---------------------------------------------------------------------------
for shell_failure in check_workflow_shell(WORKFLOW):
    failures.append("undeclared shell variable - " + shell_failure)

BROKEN_WORKFLOW = """
on: push
env:
  DEFINED: x
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: publishes
        run: |
          set -euo pipefail
          echo "PUBLISHED=1" >> "$GITHUB_ENV"
      - name: reads what exists
        run: |
          set -euo pipefail
          echo "$DEFINED $PUBLISHED"
      - name: reads what does not
        run: |
          set -euo pipefail
          echo "$NEVER_SET"
"""

with tempfile.NamedTemporaryFile("w", suffix=".yml", delete=False,
                                 encoding="utf-8") as handle:
    handle.write(BROKEN_WORKFLOW)
    broken_workflow_path = handle.name

try:
    detected = check_workflow_shell(broken_workflow_path)
finally:
    os.unlink(broken_workflow_path)

check(len(detected) == 1 and "NEVER_SET" in detected[0],
      "the shell-variable guard does not catch undeclared variables (got " +
      repr(detected) + ") - it would not have caught the DB_HOST failure")

# ---------------------------------------------------------------------------
# The render step extracts the published host with an actual grep|sed:
#   grep -m1 '^  ODOO_DB_HOST:' rendered.yaml | sed -E 's/^[^:]*: *"?([^"]*)"?$/\1/'
# Prove that exact pipeline against the manifest helm really produces, so a
# chart indentation change cannot silently publish an empty or quoted host.
# Runs only where sed exists (the ubuntu CI runner); skipped elsewhere.
# ---------------------------------------------------------------------------
if shutil.which("sed"):
    sample = subprocess.run(["helm", "template", "odoo", CHART] +
                            ENVS["production"],
                            capture_output=True, text=True, check=False).stdout
    host_line = next((line for line in sample.splitlines()
                      if line.startswith("  ODOO_DB_HOST:")), "")
    check(bool(host_line),
          "production render has no '  ODOO_DB_HOST:' ConfigMap entry")
    if host_line:
        extracted = subprocess.run(
            ["sed", "-E", 's/^[^:]*: *"?([^"]*)"?$/\1/'],
            input=host_line, capture_output=True, text=True,
            check=False).stdout.strip()
        check(extracted == "db.example.rds.amazonaws.com",
              "the render step's grep|sed extracts " + repr(extracted) +
              " from " + repr(host_line) + " instead of the DB host, so the "
              "value published to $GITHUB_ENV would be wrong")
        print("DB host extraction:", repr(extracted))
else:
    print("DB host extraction: sed not available here, check skipped")

if failures:
    print("\nFAILURES:")
    for failure in failures:
        print("  -", failure)
    sys.exit(1)

print("\nAll checks passed.")
