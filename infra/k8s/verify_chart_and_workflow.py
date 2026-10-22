"""End-to-end verification of the chart, the deploy workflow and the preflight Job."""
import os
import subprocess
import sys
import tempfile

import rendered_config
import yaml
from verify_workflow_shell import check_workflow as check_workflow_shell

CHART = "infra/helm/odoo-stack"
WORKFLOW = ".github/workflows/deploy.yml"
PREFLIGHT = "infra/k8s/odoo-db-preflight-job.yaml"

failures = []


def check(condition, message):
    if not condition:
        failures.append(message)


rendered_manifests = {}

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
    rendered_manifests[env] = rendered.stdout

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
# Reading the rendered values back out.
#
# The values published to $GITHUB_ENV (DB_HOST, DB_PORT, DB_USER, the filestore
# StorageClass) are read out of rendered.yaml, so that what the preflight Job
# checks and what helm deploys are the same endpoint. That read must produce the
# value the manifest holds.
#
# It used to be `grep | sed -E 's/...([^"]*).../\1/'`, which is not portable:
# sed implementations disagree about a back-reference in the *replacement*, and
# the one that ran the deploy check expanded `\1` to the octal escape 0x01. The
# published DB host would have been a single control byte, and the deploy would
# have failed against a host that is not a host. So:
#   * no step may parse rendered.yaml with sed,
#   * both reading steps must use infra/k8s/rendered_config.py,
#   * that reader is exercised here against the manifest helm really produces.
# ---------------------------------------------------------------------------
EXTRACTOR = "infra/k8s/rendered_config.py"
EXPECTED_DB_HOST = "db.example.rds.amazonaws.com"

for step in steps:
    body = step.get("run") or ""
    code_lines = [line for line in body.splitlines()
                  if not line.lstrip().startswith("#")]
    if "rendered.yaml" not in "\n".join(code_lines):
        continue
    check("sed" not in "\n".join(code_lines),
          "step '" + str(step.get("name")) + "' parses rendered.yaml with sed: "
          "a back-reference in a sed replacement is not portable (one sed "
          "expands '\\1' to the octal escape 0x01), so the value published to "
          "$GITHUB_ENV can be a control byte instead of the DB host. Read it "
          "with " + EXTRACTOR + " instead.")

for reader in ["helm template (render check)", "Check cluster prerequisites"]:
    reader_step = next(s for s in steps if s.get("name") == reader)
    check(EXTRACTOR in reader_step["run"],
          reader + ": does not read the rendered values with " + EXTRACTOR +
          ", so the published DB target is parsed by hand")

render_run = render_step["run"]
check(render_run.index("rendered.yaml") < render_run.index(EXTRACTOR),
      "render step reads the DB host before it has rendered anything")

production_render = rendered_manifests.get("production", "")
local_render = rendered_manifests.get("local", "")


def check_rendered_value(label, manifest, kind, dotted_path, expected):
    actual = rendered_config.read_value(manifest, kind, dotted_path)
    check(actual == expected,
          label + ": expected " + repr(expected) + ", read " + repr(actual))
    return actual


read_host = check_rendered_value(
    "production ConfigMap ODOO_DB_HOST", production_render,
    "ConfigMap", "data.ODOO_DB_HOST", EXPECTED_DB_HOST)
check(read_host is None or all(0x20 < ord(char) < 0x7f for char in read_host),
      "the DB host read out of the render contains a control byte (" +
      repr(read_host) + ") - exactly what a sed '\\1' replacement published")

check_rendered_value("production ConfigMap ODOO_DB_PORT", production_render,
                     "ConfigMap", "data.ODOO_DB_PORT", "5432")
check_rendered_value("production ConfigMap ODOO_DB_USER", production_render,
                     "ConfigMap", "data.ODOO_DB_USER", "odoo")
check_rendered_value("production PVC storageClassName", production_render,
                     "PersistentVolumeClaim", "spec.storageClassName", "efs-sc")
check_rendered_value("local render has no filestore StorageClass", local_render,
                     "PersistentVolumeClaim", "spec.storageClassName", None)
check_rendered_value("a key that is not in the render", production_render,
                     "ConfigMap", "data.NOT_A_KEY", None)
check_rendered_value("a field of the wrong document kind", production_render,
                     "Service", "data.ODOO_DB_HOST", None)

# The reader also has to survive the shapes a value can take, since a quoted
# host is only one of them: unquoted, single-quoted, CRLF (a shell on Windows
# that redirects helm output), a value containing a colon (host:port endpoint),
# and a Service whose fields must not be mistaken for ConfigMap data.
READER_CASES = [
    ('  ODOO_DB_HOST: "' + EXPECTED_DB_HOST + '"', EXPECTED_DB_HOST),
    ("  ODOO_DB_HOST: " + EXPECTED_DB_HOST, EXPECTED_DB_HOST),
    ("  ODOO_DB_HOST: '" + EXPECTED_DB_HOST + "'", EXPECTED_DB_HOST),
    ('  ODOO_DB_HOST: "' + EXPECTED_DB_HOST + '"\r', EXPECTED_DB_HOST),
    ('  ODOO_DB_HOST: "pg.internal:6432"', "pg.internal:6432"),
]

for host_line, expected in READER_CASES:
    manifest = (
        "apiVersion: v1\nkind: Service\nmetadata:\n  name: not-a-configmap\n"
        "spec:\n  type: ClusterIP\n---\n"
        "apiVersion: v1\nkind: ConfigMap\nmetadata:\n  name: config\n"
        "data:\n" + host_line + "\n  ODOO_DB_PORT: \"5432\"\n"
    )
    check(rendered_config.read_value(manifest, "ConfigMap", "data.ODOO_DB_HOST")
          == expected,
          "the render reader does not handle " + repr(host_line))

# And the command the workflow actually runs, end to end: exit status, stdout,
# and the empty answer that lets an optional value stay optional.
with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False,
                                 encoding="utf-8") as handle:
    handle.write(production_render)
    rendered_manifest_path = handle.name

try:
    invoked = subprocess.run(
        [sys.executable, EXTRACTOR, rendered_manifest_path,
         "ConfigMap", "data.ODOO_DB_HOST"],
        capture_output=True, text=True, check=False)
    absent = subprocess.run(
        [sys.executable, EXTRACTOR, rendered_manifest_path,
         "PersistentVolumeClaim", "spec.noSuchField"],
        capture_output=True, text=True, check=False)
finally:
    os.unlink(rendered_manifest_path)

check(invoked.returncode == 0 and invoked.stdout.strip() == EXPECTED_DB_HOST,
      "running " + EXTRACTOR + " as the workflow does returns exit " +
      str(invoked.returncode) + " and " + repr(invoked.stdout) +
      " instead of the DB host")
check(absent.returncode == 1 and not absent.stdout.strip(),
      "an absent value must print nothing and exit 1 so `|| true` keeps "
      "optional values optional; got exit " + str(absent.returncode) +
      " and " + repr(absent.stdout))

print("DB host extraction:", repr(read_host))

if failures:
    print("\nFAILURES:")
    for failure in failures:
        print("  -", failure)
    sys.exit(1)

print("\nAll checks passed.")
