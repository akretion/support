# Copyright 2026 Akretion (http://www.akretion.com).
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    "name": "Support Server Release",
    "summary": "Receive the releases of a customer project, link the tickets and "
    "move them to the stage of the deployed environment",
    "version": "18.0.1.0.0",
    "license": "AGPL-3",
    "author": "Akretion",
    "website": "https://github.com/akretion/support",
    "depends": [
        "cross_connect_server",
        "project",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/support_server_release_views.xml",
        "views/project_task_views.xml",
        "views/res_config_settings_views.xml",
    ],
    "installable": True,
}
