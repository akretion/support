# Copyright 2024 Akretion
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Project Customer Access",
    "summary": """Project menu and views for customers accessing your own ERP""",
    "version": "16.0.1.0.0",
    "license": "AGPL-3",
    "author": "Akretion",
    "website": "http://akretion.com",
    "depends": [
        "date_range",
        # https://github.com/akretion/ak-odoo-incubator
        "project_sprint",
        # https://github.com/OCA/server-backend
        "base_group_backend",
        # https://github.com/OCA/server-auth
        "cross_connect_server",
    ],
    "data": [
        "data/res_groups.xml",
        "security/ir.model.access.csv",
        "security/project_customer_access_security.xml",
        "views/project_task_views.xml",
    ],
    "demo": ["data/project_customer_access_demo.xml"],
}
