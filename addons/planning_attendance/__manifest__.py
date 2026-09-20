# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    "name": "Planning and Attendances",
    "version": "1.0",
    "category": "Hidden",
    "sequence": 50,
    "summary": "Compare plannings and attendances",
    "depends": ["planning", "hr_attendance"],
    "description": """
Compare plannings and attendances
=================================
Allow users to compare planned hours vs. the hours effectively done in attendance.
""",
    "data": [
        "security/planning_attendance_security.xml",
        "security/ir.model.access.csv",
        "report/planning_attendance_analysis_report_views.xml",
        "views/planning_attendance_menus.xml",
    ],
    "auto_install": True,
    "author": "Odoo S.A.",
    "license": "OEEL-1",
}
