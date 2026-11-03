# Copyright 2026 Akretion (http://www.akretion.com).
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.extendable_fastapi.tests.common import FastAPITransactionCase

from ..routers import release_router


class ReleaseCaseMixin:
    @classmethod
    def _setup_release_data(cls):
        cls.Release = cls.env["support.server.release"]
        cls.partner = cls.env["res.partner"].create({"name": "Customer"})
        cls.other_partner = cls.env["res.partner"].create({"name": "Other customer"})
        cls.endpoint = cls.env["fastapi.endpoint"].create(
            {"name": "Support endpoint", "root_path": "/api", "app": "cross_connect"}
        )
        cls.client = cls.env["cross.connect.client"].create(
            {
                "name": "Test client",
                "endpoint_id": cls.endpoint.id,
                "api_key": "release-api-key",
            }
        )
        cls.other_client = cls.env["cross.connect.client"].create(
            {
                "name": "Other client",
                "endpoint_id": cls.endpoint.id,
                "api_key": "other-api-key",
            }
        )
        cls.project = cls.env["project.project"].create(
            {
                "name": "Ticket project",
                "partner_id": cls.partner.id,
                "cross_connect_client_id": cls.client.id,
            }
        )
        cls.other_project = cls.env["project.project"].create(
            {
                "name": "Other project",
                "partner_id": cls.other_partner.id,
                "cross_connect_client_id": cls.other_client.id,
            }
        )
        cls.anonymous_project = cls.env["project.project"].create(
            {"name": "Anonymous project", "cross_connect_client_id": cls.client.id}
        )
        cls.internal_project = cls.env["project.project"].create(
            {"name": "Internal maintenance", "partner_id": cls.partner.id}
        )
        projects = (
            cls.project
            | cls.other_project
            | cls.anonymous_project
            | cls.internal_project
        ).ids
        cls.stage_new = cls.env["project.task.type"].create(
            {"name": "New", "sequence": 1, "project_ids": [(6, 0, projects)]}
        )
        cls.stage_preprod = cls.env["project.task.type"].create(
            {"name": "To release", "sequence": 10, "project_ids": [(6, 0, projects)]}
        )
        cls.stage_prod = cls.env["project.task.type"].create(
            {"name": "Closed", "sequence": 20, "project_ids": [(6, 0, projects)]}
        )
        cls.env["ir.config_parameter"].sudo().set_param(
            "support_server_release.stage_preprod_id", cls.stage_preprod.id
        )
        cls.env["ir.config_parameter"].sudo().set_param(
            "support_server_release.stage_prod_id", cls.stage_prod.id
        )

    def _task(self, stage=None, project=None):
        stage = stage or self.stage_preprod
        project = project or self.project
        return self.env["project.task"].create(
            {"name": "Ticket", "project_id": project.id, "stage_id": stage.id}
        )

    def _payload(self, environment, version, tickets):
        return {"environment": environment, "version": version, "tickets": tickets}

    def _notification_user(self, email):
        """A user notified when a release of the partner reaches production."""
        user = (
            self.env["res.users"]
            .with_context(no_reset_password=True)
            .create(
                {
                    "name": "Customer user",
                    "login": email,
                    "email": email,
                    "groups_id": [(6, 0, [self.env.ref("base.group_portal").id])],
                }
            )
        )
        self.partner.support_release_notification_user_ids = [(4, user.id)]
        return user


class TestSupportServerRelease(ReleaseCaseMixin, TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_release_data()

    def test_preprod_creates_release(self):
        task = self._task()
        release = self.Release._process(
            self.client, self._payload("preprod", "next", [task.id])
        )
        self.assertEqual(release.version, "next")
        self.assertEqual(release.cross_connect_client_id, self.client)
        self.assertEqual(release.partner_id, self.partner)
        self.assertEqual(release.task_ids, task)
        self.assertTrue(release.preprod_deployed_at)
        self.assertFalse(release.prod_deployed_at)
        self.assertFalse(release.message)
        self.assertEqual(task.stage_id, self.stage_preprod)
        self.assertEqual(task.release_ids, release)

    def test_unknown_ticket_is_reported(self):
        release = self.Release._process(
            self.client, self._payload("preprod", "next", [99999999])
        )
        self.assertTrue(release)
        self.assertFalse(release.task_ids)
        self.assertIn("99999999", release.message)

    def test_numbered_version_removes_next(self):
        first = self._task()
        second = self._task()
        self.Release._process(self.client, self._payload("preprod", "next", [first.id]))
        release = self.Release._process(
            self.client, self._payload("preprod", "14.0.1.0", [first.id, second.id])
        )
        self.assertFalse(self.Release.search([("version", "=", "next")]))
        self.assertEqual(release.version, "14.0.1.0")
        self.assertEqual(release.task_ids, first | second)
        self.assertEqual(self.Release.search_count([]), 1)

    def test_prod_applies_prod_stage(self):
        task = self._task()
        release = self.Release._process(
            self.client, self._payload("prod", "14.0.1.0", [task.id])
        )
        self.assertTrue(release.prod_deployed_at)
        self.assertFalse(release.preprod_deployed_at)
        self.assertEqual(task.stage_id, self.stage_prod)

    def test_payload_after_prod_is_ignored(self):
        task = self._task()
        self.Release._process(self.client, self._payload("prod", "14.0.1.0", [task.id]))
        release = self.Release._process(
            self.client, self._payload("preprod", "14.0.1.0", [task.id])
        )
        self.assertFalse(release.preprod_deployed_at)
        self.assertEqual(task.stage_id, self.stage_prod)

    def test_stage_is_applied_without_condition(self):
        task = self._task(stage=self.stage_prod)
        self.Release._process(self.client, self._payload("preprod", "next", [task.id]))
        self.assertEqual(task.stage_id, self.stage_preprod)

    def test_no_stage_configured(self):
        self.env["ir.config_parameter"].sudo().set_param(
            "support_server_release.stage_preprod_id", False
        )
        task = self._task()
        release = self.Release._process(
            self.client, self._payload("preprod", "next", [task.id])
        )
        self.assertTrue(release)
        self.assertEqual(task.stage_id, self.stage_preprod)
        self.assertIn("No stage configured", release.message)

    def test_ticket_of_another_partner_is_not_linked(self):
        task = self._task()
        foreign = self._task(stage=self.stage_new, project=self.other_project)
        release = self.Release._process(
            self.client, self._payload("preprod", "next", [task.id, foreign.id])
        )
        self.assertEqual(release.task_ids, task)
        self.assertEqual(release.partner_id, self.partner)
        self.assertEqual(foreign.stage_id, self.stage_new)
        self.assertIn(str(foreign.id), release.message)

    def test_ticket_of_internal_project_is_linked(self):
        internal = self._task(stage=self.stage_new, project=self.internal_project)
        release = self.Release._process(
            self.client, self._payload("preprod", "next", [internal.id])
        )
        self.assertEqual(release.task_ids, internal)
        self.assertEqual(release.partner_id, self.partner)
        self.assertFalse(release.message)

    def test_ticket_of_project_without_partner_is_not_linked(self):
        task = self._task(project=self.anonymous_project)
        release = self.Release._process(
            self.client, self._payload("preprod", "next", [task.id])
        )
        self.assertFalse(release.task_ids)
        self.assertEqual(release.partner_id, self.partner)
        self.assertIn(str(task.id), release.message)
        self.assertEqual(task.stage_id, self.stage_preprod)

    def test_several_partners_raise(self):
        self.env["project.project"].create(
            {
                "name": "Second project of the client",
                "partner_id": self.other_partner.id,
                "cross_connect_client_id": self.client.id,
            }
        )
        task = self._task()
        with self.assertRaises(ValidationError):
            self.Release._process(
                self.client, self._payload("preprod", "next", [task.id])
            )
        self.assertFalse(self.Release.search([]))

    def test_payload_replaces_tickets(self):
        first = self._task()
        second = self._task()
        self.Release._process(
            self.client, self._payload("preprod", "14.0.1.0", [first.id, second.id])
        )
        release = self.Release._process(
            self.client, self._payload("preprod", "14.0.1.0", [first.id])
        )
        self.assertEqual(release.task_ids, first)
        self.assertFalse(second.release_ids)

    def test_second_payload_is_idempotent(self):
        task = self._task()
        payload = self._payload("preprod", "next", [task.id])
        release = self.Release._process(self.client, dict(payload))
        deployed_at = release.preprod_deployed_at
        release = self.Release._process(self.client, dict(payload))
        self.assertEqual(self.Release.search_count([]), 1)
        self.assertEqual(release.task_ids, task)
        self.assertEqual(release.partner_id, self.partner)
        self.assertGreaterEqual(release.preprod_deployed_at, deployed_at)

    def test_prod_notifies_the_notification_users(self):
        task = self._task()
        task.description = "<p>The content of the ticket</p>"
        self._notification_user("customer@example.com")
        self.env["mail.mail"].search([]).unlink()
        release = self.Release._process(
            self.client, self._payload("prod", "14.0.1.0", [task.id])
        )
        mail = self.env["mail.mail"].search(
            [("model", "=", "support.server.release"), ("res_id", "=", release.id)]
        )
        self.assertEqual(len(mail), 1)
        self.assertEqual(mail.email_to, "customer@example.com")
        self.assertIn("14.0.1.0", mail.subject)
        self.assertIn(self.project.name, mail.body_html)
        self.assertIn(f"[{task.id}] {task.name}", mail.body_html)
        self.assertIn("The content of the ticket", mail.body_html)
        self.assertIn("<details>", mail.body_html)
        self.assertNotIn("mail/unfollow", mail.body_html)
        self.assertIn(
            f"/odoo/action-project.action_view_task/{task.id}", mail.body_html
        )

    def test_prod_mail_groups_the_tickets_by_project(self):
        second_project = self.env["project.project"].create(
            {
                "name": "Second project",
                "partner_id": self.partner.id,
                "cross_connect_client_id": self.client.id,
                "type_ids": [(6, 0, (self.stage_preprod | self.stage_prod).ids)],
            }
        )
        task = self._task()
        second_task = self._task(project=second_project)
        internal_task = self._task(project=self.internal_project)
        self._notification_user("customer@example.com")
        self.env["mail.mail"].search([]).unlink()
        release = self.Release._process(
            self.client,
            self._payload(
                "prod", "14.0.1.0", [task.id, second_task.id, internal_task.id]
            ),
        )
        mail = self.env["mail.mail"].search(
            [("model", "=", "support.server.release"), ("res_id", "=", release.id)]
        )
        body = mail.body_html
        # the internal ticket is linked to the release but kept out of the mail
        self.assertIn(internal_task, release.task_ids)
        self.assertNotIn(self.internal_project.name, body)
        self.assertNotIn(f"[{internal_task.id}]", body)
        # each ticket is listed under the block of its own project
        self.assertIn(f"[{task.id}] {task.name}", body)
        self.assertIn(f"[{second_task.id}] {second_task.name}", body)
        self.assertLess(body.index(self.project.name), body.index(f"[{task.id}]"))
        self.assertLess(body.index(f"[{task.id}]"), body.index(second_project.name))
        self.assertLess(
            body.index(second_project.name), body.index(f"[{second_task.id}]")
        )

    def test_prod_mail_is_sent_in_the_language_of_the_customer(self):
        self.env["res.lang"]._activate_lang("fr_FR")
        self.env.ref("base.module_support_server_release")._update_translations(
            ["fr_FR"]
        )
        self.env.invalidate_all()
        template = self.env.ref("support_server_release.mail_template_release_in_prod")
        self.assertIn("en production", template.with_context(lang="fr_FR").subject)
        task = self._task()
        self._notification_user("customer@example.com")
        self.partner.lang = "fr_FR"
        self.env["mail.mail"].search([]).unlink()
        release = self.Release._process(
            self.client, self._payload("prod", "14.0.1.0", [task.id])
        )
        mail = self.env["mail.mail"].search(
            [("model", "=", "support.server.release"), ("res_id", "=", release.id)]
        )
        self.assertIn("version 14.0.1.0 en production", mail.subject)
        self.assertIn("Bonjour", mail.body_html)
        self.assertIn("Cordialement", mail.body_html)

    def test_prod_mail_is_sent_once(self):
        task = self._task()
        self._notification_user("customer@example.com")
        self.env["mail.mail"].search([]).unlink()
        payload = self._payload("prod", "14.0.1.0", [task.id])
        self.Release._process(self.client, dict(payload))
        self.Release._process(self.client, dict(payload))
        self.assertEqual(len(self.env["mail.mail"].search([])), 1)

    def test_preprod_sends_no_mail(self):
        task = self._task()
        self._notification_user("customer@example.com")
        self.env["mail.mail"].search([]).unlink()
        self.Release._process(self.client, self._payload("preprod", "next", [task.id]))
        self.assertFalse(self.env["mail.mail"].search([]))

    def test_prod_without_customer_ticket_sends_no_mail(self):
        internal_task = self._task(project=self.internal_project)
        self._notification_user("customer@example.com")
        self.env["mail.mail"].search([]).unlink()
        release = self.Release._process(
            self.client, self._payload("prod", "14.0.1.0", [internal_task.id])
        )
        # the internal ticket is linked, but there is nothing to announce
        self.assertIn(internal_task, release.task_ids)
        self.assertFalse(self.env["mail.mail"].search([]))
        self.assertIn("No ticket of a customer project", release.message)

    def test_prod_without_notification_user_sends_no_mail(self):
        task = self._task()
        self.env["mail.mail"].search([]).unlink()
        release = self.Release._process(
            self.client, self._payload("prod", "14.0.1.0", [task.id])
        )
        self.assertTrue(release.prod_deployed_at)
        self.assertFalse(self.env["mail.mail"].search([]))
        self.assertIn("No user with an email", release.message)


@tagged("post_install", "-at_install")
class TestSupportServerReleaseRouter(ReleaseCaseMixin, FastAPITransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_release_data()
        cls.endpoint_user = cls.env["res.users"].create(
            {
                "name": "FastAPI Endpoint User",
                "login": "support_release_endpoint_user",
                "groups_id": [
                    (
                        6,
                        0,
                        [cls.env.ref("fastapi.group_fastapi_endpoint_runner").id],
                    )
                ],
            }
        )
        cls.endpoint._handle_registry_sync(cls.endpoint.ids)
        cls.default_fastapi_running_user = cls.endpoint_user
        cls.default_fastapi_router = release_router
        cls.default_fastapi_app = cls.endpoint._get_app()
        cls.default_fastapi_dependency_overrides = (
            cls.default_fastapi_app.dependency_overrides
        )

    def test_post_release(self):
        task = self._task()
        with self._create_test_client() as test_client:
            response = test_client.post(
                "/cross_connect/release",
                headers={"api-key": "release-api-key"},
                json=self._payload("preprod", "next", [task.id]),
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True})
        release = self.env["support.server.release"].search([("version", "=", "next")])
        self.assertEqual(release.task_ids, task)
        self.assertEqual(task.stage_id, self.stage_preprod)

    def test_post_release_unauthorized(self):
        with self._create_test_client(raise_server_exceptions=False) as test_client:
            response = test_client.post(
                "/cross_connect/release",
                headers={"api-key": "wrong-api-key"},
                json=self._payload("preprod", "next", []),
            )
        self.assertEqual(response.status_code, 401)

    def test_post_release_invalid_environment(self):
        with self._create_test_client(raise_server_exceptions=False) as test_client:
            response = test_client.post(
                "/cross_connect/release",
                headers={"api-key": "release-api-key"},
                json=self._payload("dev", "next", []),
            )
        self.assertEqual(response.status_code, 422)

    def test_post_release_empty_version(self):
        with self._create_test_client(raise_server_exceptions=False) as test_client:
            response = test_client.post(
                "/cross_connect/release",
                headers={"api-key": "release-api-key"},
                json=self._payload("preprod", "", []),
            )
        self.assertEqual(response.status_code, 422)
