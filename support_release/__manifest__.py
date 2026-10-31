# Copyright 2026 Akretion (http://www.akretion.com).
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    "name": "Support Release",
    "summary": "Record the releases of a project and push them to the support server",
    "version": "18.0.1.0.0",
    "license": "AGPL-3",
    "author": "Akretion",
    "website": "https://github.com/akretion/support",
    "depends": [
        "support",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/ir_cron.xml",
        "views/support_release_views.xml",
    ],
    "installable": True,
}
