# -*- coding: utf-8 -*-
# Copyright 2019 Akretion (http://www.akretion.com).
# @author Sébastien BEAU <sebastien.beau@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
# pylint: disable=C8107

import base64
from os import path

from odoo.tests.common import SavepointCase


class TestTask(SavepointCase):
    @classmethod
    def _get_image(cls, name):
        image_path = path.dirname(path.abspath(__file__))
        f = open(path.join(image_path, "static", name), "rb")
        return base64.b64encode(f.read()).decode()

    @classmethod
    def setUpClass(cls):
        super(TestTask, cls).setUpClass()
        cls.image = cls._get_image("partner-customer-image.png")
        cls.env.user.image_1920 = cls.image
        cls.demo_user = cls.env.ref("base.user_demo")
        cls.demo_user.image_1920 = cls.image
        cls.env.ref("project_api_client.support_api_key").confirm_connection()
        cls.task = cls.env["external.task"].search(domain=[["name", "=", "Migration"]])
        cls.read_only_task = cls.env["external.task"].search(
            domain=[["name", "=", "Integrate Modules"]]
            )

    def assertTaskFieldEqual(self, task, field, value):
        # Note task.<field> do not work as we didn't have implemented
        # the cache logic so it will raise an error
        # but we do not need this as their is not python logic for this object
        self.assertEqual(task.read([field])[0][field], value)

    def test_read_group(self):
        res = self.env["external.task"].read_group(
            groupby=["stage_name"],
            fields=["stage_name", "name"],
            domain=[],
            offset=0,
            lazy=True,
            limit=False,
            orderby=False,
        )
        self.assertEqual(len(res), 3, "we expect 3 columns")
        stages = [x["stage_name"] for x in res]
        self.assertEqual(stages, ["To Do", "In Progress", "Done"])

    def test_search(self):
        res = self.env["external.task"].search(domain=[["stage_name", "=", "Done"]])
        self.assertEqual(len(res), 1, "we expect 1 task")
        self.assertIsInstance(res[0], type(self.env["external.task"]))

    def test_search__count(self):
        res = self.env["external.task"].search(
            domain=[["stage_name", "=", "Done"]], count=True
        )
        self.assertEqual(res, 1)

    def test_read(self):
        tasks = self.env["external.task"].search(
            domain=[["stage_name", "=", "In Progress"]],
            order="name",
        )
        res = tasks.read(fields=["stage_name", "name"])
        self.assertEqual(len(res), 5)
        names = [x["name"] for x in res]
        self.assertEqual(
            names,
            [
                "Propose a new design for invoice report",
                "Integrate Modules",
                "Develop module for Warehouse",
                "Develop module for Sale Management",
                "Need to add a new columns in report A",
            ],
        )

    def test_create(self):
        task = self.env["external.task"].create(
            {"name": "Test", "description": "Creation test"}
        )
        self.assertEqual(len(task), 1)
        self.assertIsInstance(task, type(self.env["external.task"]))
        self.assertTaskFieldEqual(task, "name", "Test")

    def test_write(self):
        res = self.task.write({"description": "Duplicated issue #112"})
        self.assertEqual(res, True)
        self.assertTaskFieldEqual(
            self.task, "description", "<p>Duplicated issue #112</p>"
        )

    def test_write__assignee(self):
        res = self.task.write({"assignee_customer_id": self.demo_user.partner_id.id})
        self.assertEqual(res, True)
        self.assertTaskFieldEqual(
            self.task,
            "assignee_customer_id",
            [self.demo_user.partner_id.id, self.demo_user.partner_id.name],
        )

    def test_message_read(self):
        support_team = self.env.ref("project_api_client.support_team")
        # Ensure that there is not partner in the team
        support_team.child_ids.unlink()
        res = self.env["mail.message"].browse(
            self.read_only_task.message_ids.ids
            ).message_format()
        self.assertEqual(len(res), 2)
        self.assertEqual(len(support_team.child_ids), 1)

    def test_message_post(self):
        res = self.task.message_post(body="my comment")
        self.assertIn("external/", res)

    def test_add_and_download_attachement(self):
        self.task.write(
            {
                "attachment_ids": [
                    (
                        0,
                        0,
                        {
                            "datas_fname": "error.png",
                            "name": "error.png",
                            "datas": self.image,
                            "res_model": "project.task",
                        },
                    )
                ]
            }
        )
        _id = self.task.read(["attachment_ids"])[0]["attachment_ids"][-1]
        attachment = self.env["external.attachment"].browse(_id).read(["datas"])[0]
        self.assertEqual(attachment["datas"], self.image)
