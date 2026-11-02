"""Static guard: every shell variable a deploy step reads must be defined.

Why this exists
---------------
Every deploy step runs under `set -euo pipefail`. Under `-u` (nounset) a
variable nobody declared does not expand to the empty string - bash aborts the
step with

    line 13: DB_HOST: unbound variable

which is the whole error. That is exactly how the deploy failed: the
"Check cluster prerequisites" step echoed `$DB_HOST` while only the config
guard, the render step and the helm upgrade step were given it.

A step can be fed from four places, and this module collects all of them:
  * the workflow-level `env:` block,
  * the step's own `env:` block,
  * names an earlier step published to `$GITHUB_ENV`,
  * names the script assigns itself (`VAR=`, `for VAR in`, `read VAR`).

Anything read outside that set - in a step that enables nounset - is a
failure with the step name, instead of an unbound-variable line at runtime.
"""
import re
import sys

import yaml

# Provided by the runner, never declared in the workflow.
GITHUB_DEFAULT_ENV = frozenset({
    "GITHUB_ENV", "GITHUB_OUTPUT", "GITHUB_PATH", "GITHUB_SHA",
    "GITHUB_REF", "GITHUB_REF_NAME", "GITHUB_WORKSPACE", "GITHUB_REPOSITORY",
    "GITHUB_RUN_ID", "GITHUB_ACTOR", "GITHUB_TOKEN", "GITHUB_BASE_REF",
    "RUNNER_OS", "RUNNER_TEMP", "CI", "HOME", "PATH",
})

# `${{ ... }}` is resolved by GitHub before bash ever sees the script.
GH_EXPRESSION = re.compile(r"\$\{\{.*?\}\}", re.S)

ASSIGNMENT = re.compile(
    r"(?:^|[\s;(])(?:export\s+|local\s+|readonly\s+)?"
    r"([A-Za-z_][A-Za-z0-9_]*)\+?=",
    re.M,
)
FOR_LOOP = re.compile(r"\bfor\s+([A-Za-z_][A-Za-z0-9_]*)\s+in\b")
ASSIGN_BUILTIN = re.compile(r"\b(?:read|mapfile|readarray)\s+(?:-\S+\s+)*"
                            r"([A-Za-z_][A-Za-z0-9_]*)")
PUBLISHED = re.compile(r'echo\s+"?([A-Za-z_][A-Za-z0-9_]*)=')

REFERENCE = re.compile(r"\$\{([^}]*)\}|\$([A-Za-z_][A-Za-z0-9_]*)")

NOUNSET = re.compile(r"set\s+-\w*u|set\s+-o\s+nounset")


def _assigned_names(script):
    names = set(ASSIGNMENT.findall(script))
    names.update(FOR_LOOP.findall(script))
    names.update(ASSIGN_BUILTIN.findall(script))
    return names


def _referenced_names(script):
    """Every variable the script reads, with `${...}` operators stripped."""
    cleaned = GH_EXPRESSION.sub("", script)
    names = set()
    for braced, plain in REFERENCE.findall(cleaned):
        if plain:
            names.add(plain)
            continue
        # ${!ref}, ${#arr[@]}, ${VAR:-default}, ${VAR%pattern}, ...
        body = braced.lstrip("!#")
        match = re.match(r"[A-Za-z_][A-Za-z0-9_]*", body)
        if match:
            names.add(match.group(0))
    return names


def _published_names(script):
    """Names this step exports to later steps through $GITHUB_ENV."""
    if "GITHUB_ENV" not in script:
        return set()
    return set(PUBLISHED.findall(script))


def check_workflow(path=".github/workflows/deploy.yml"):
    """Return a list of human-readable failures; empty means the file is sane."""
    with open(path, encoding="utf-8") as handle:
        workflow = yaml.safe_load(handle)

    workflow_env = set((workflow.get("env") or {}).keys())
    failures = []

    for job_name, job in (workflow.get("jobs") or {}).items():
        if not isinstance(job, dict) or "steps" not in job:
            continue  # reusable-workflow call, not a step list

        available = set(workflow_env) | GITHUB_DEFAULT_ENV
        for step in job["steps"]:
            label = str(step.get("name") or step.get("uses") or "<unnamed>")
            step_env = set((step.get("env") or {}).keys())
            script = step.get("run") or ""

            defined = available | step_env | _assigned_names(script)
            if script and NOUNSET.search(script):
                for name in sorted(_referenced_names(script)):
                    if name not in defined:
                        failures.append(
                            job_name + " / '" + label + "': $" + name +
                            " is read but never defined - under `set -u` this "
                            "aborts with 'unbound variable'. Declare it in the "
                            "step env:, the workflow env:, or publish it to "
                            "$GITHUB_ENV in an earlier step.")

            # Later steps inherit what this one published.
            available |= _published_names(script)
    return failures


def main():
    failures = check_workflow()
    if failures:
        print("Workflow shell-variable check FAILED:")
        for failure in failures:
            print("  - " + failure)
        return 1
    print("Workflow shell-variable check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
