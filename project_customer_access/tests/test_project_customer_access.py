# Copyright 2024 Akretion
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests.common import Form, TransactionCase, new_test_user


class TestProjectCustomerAccess(TransactionCase):
    def setUp(self):
        super().setUp()
        self.customer = new_test_user(
            self.env,
            login="test_customer",
            groups="project_customer_access.group_customer",
        )
        self.manager = new_test_user(
            self.env,
            login="test_manager",
            groups="project_customer_access.group_manager",
        )

        self.form_view = "project_customer_access.view_task_form"
        self.project1 = self.env.ref("project.project_project_1")
        self.project2 = self.env.ref("project.project_project_2")
        self.project_ids = self.project1 | self.project2
        self.task = self.env.ref("project.project_1_task_1")
        self.tag = self.env.ref("project.project_tags_00")
        self.stage = self.env.ref("project.project_stage_3")

        self.task_customer = self.env["project.task"].create(
            {
                "name": "Test",
                "project_id": self.project1.id,
                "user_ids": [Command.link(self.customer.id)],
            }
        )

        # Cross connection made by other module
        self.endpoint = self.env["fastapi.endpoint"].create(
            {
                "name": "Cross Connect Server Endpoint",
                "root_path": "/api",
                "app": "cross_connect",
            }
        )
        self.client = self.env["cross.connect.client"].create(
            {
                "name": "Test Client",
                "endpoint_id": self.endpoint.id,
                "api_key": "server-api-key",
            }
        )
        (self.customer | self.manager).write(
            {"cross_connect_client_id": self.client.id}
        )
        self.project_ids.write({"cross_connect_client_id": self.client.id})

    def test_visible_projects(self):
        customer_proj = self.env["project.project"].with_user(self.customer).search([])
        manager_proj = self.env["project.project"].with_user(self.manager).search([])

        self.assertEqual(customer_proj, self.project_ids)
        self.assertEqual(manager_proj, self.project_ids)

    def test_visible_tasks(self):
        task_ids = self.env["project.task"].search(
            [("project_id", "in", self.project_ids.ids)]
        )
        customer_tasks = self.env["project.task"].with_user(self.customer).search([])
        manager_tasks = self.env["project.task"].with_user(self.manager).search([])

        self.assertEqual(customer_tasks, task_ids)
        self.assertEqual(manager_tasks, task_ids)

    def test_edit_own_task_customer(self):
        task_id = self.task_customer.with_user(self.customer)
        with Form(task_id, view=self.form_view) as f:
            f.name = "Test"
            f.description = "Test"
            with self.assertRaisesRegex(AssertionError, "can't write on readonly"):
                f.project_id = self.project2

        self.assertEqual(task_id.name, "Test")
        self.assertIn("Test", str(task_id.description))

    def test_edit_other_task_customer(self):
        task_id = self.task.with_user(self.customer)
        task_form = Form(task_id, view=self.form_view)
        with self.assertRaisesRegex(AssertionError, "can't write on readonly"):
            task_form.name = "Test"

    def test_edit_task_manager(self):
        task_id = self.task.with_user(self.manager)
        with Form(task_id, view=self.form_view) as f:
            f.name = "Test"
            f.description = "Test"
            f.tag_ids.add(self.tag)
            f.stage_id = self.stage
            f.project_id = self.project2

        self.assertEqual(task_id.name, "Test")
        self.assertIn("Test", str(task_id.description))
        self.assertEqual(task_id.tag_ids, self.tag)
        self.assertEqual(task_id.stage_id, self.stage)
        self.assertEqual(task_id.project_id, self.project2)

    def test_no_unlink_manager(self):
        with self.assertRaisesRegex(AccessError, "You are not allowed to delete"):
            self.task_customer.with_user(self.manager).unlink()

    def test_create_task_customer(self):
        f = Form(self.env["project.task"].with_user(self.customer), view=self.form_view)
        f.name = "New"
        f.description = "New"
        f.project_id = self.project1
        task_id = f.save()

        self.assertEqual(task_id.name, "New")
        self.assertIn("New", str(task_id.description))
        self.assertEqual(task_id.project_id, self.project1)

    def test_create_task_customer_no_project(self):
        f = Form(self.env["project.task"].with_user(self.customer), view=self.form_view)
        f.name = "New"
        with self.assertRaisesRegex(AssertionError, "project_id is a required field"):
            task_id = f.save()
