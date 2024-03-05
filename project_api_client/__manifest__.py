# Copyright 2018 Akretion (http://www.akretion.com).
# @author Sébastien BEAU <sebastien.beau@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    "name": "Project API client",
    "summary": "Module add a new entry to follow your project in the integrator ERP",
    "version": "16.0.1.0.0",
    "category": "Project Management",
    "author": "Akretion",
    "website": "https://github.com/akretion/support",
    "license": "AGPL-3",
    "depends": ["mail", "base_sparse_field"],
    "data": [
        "security/group.xml",
        "security/ir.model.access.csv",
        "views/project_view.xml",
        "views/res_users_view.xml",
        "views/account_view.xml",
        "data/partner_data.xml",
    ],
    "demo": ["demo/account_support_demo.xml"],
    "installable": True,
    "application": True,
}
