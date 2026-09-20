from . import models
from . import wizard


def uninstall_hook(env):
    rule = env.ref("project.project_project_manager_rule", raise_if_not_found=False)
    if rule and "database_hosting" in rule.domain_force:
        rule.write({
            "name": "Project: project manager: see all",
            "domain_force": "[(1, '=', 1)]",
        })
