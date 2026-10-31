# Copyright 2026 Akretion (http://www.akretion.com).
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from unittest.mock import patch

from odoo import tools
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase


def _set_running_env(environment):
    return patch.dict(tools.config.options, {"running_env": environment})


class TestSupportRelease(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Release = cls.env["support.release"]
        cls.Server = cls.env["cross.connect.server"]

    def _patch_request(self):
        """Mock the transport, keeping the rest of the push logic under test."""
        return patch.object(type(self.Server), "_request")

    def test_register_next(self):
        release = self.Release._register_deployment("next", [42, 12, 42])
        self.assertEqual(release.version, "next")
        self.assertFalse(release.is_sent)
        self.assertEqual(release._get_ticket_ids(), [12, 42])

    def test_register_same_version_merges_tickets(self):
        self.Release._register_deployment("next", [1])
        release = self.Release._register_deployment("next", [2])
        self.assertEqual(self.Release.search_count([("version", "=", "next")]), 1)
        self.assertEqual(release._get_ticket_ids(), [1, 2])

    def test_register_same_version_keeps_is_sent(self):
        release = self.Release._register_deployment("next", [1])
        release.is_sent = True
        release = self.Release._register_deployment("next", [2])
        self.assertTrue(release.is_sent)
        self.assertEqual(release._get_ticket_ids(), [1, 2])

    def test_version_absorbs_next(self):
        self.Release._register_deployment("next", [1, 2])
        release = self.Release._register_deployment("14.0.1.0", [2, 3])
        self.assertFalse(self.Release.search([("version", "=", "next")]))
        self.assertEqual(release.version, "14.0.1.0")
        self.assertEqual(release._get_ticket_ids(), [1, 2, 3])

    def test_next_recreated_after_absorption(self):
        self.Release._register_deployment("next", [1])
        self.Release._register_deployment("14.0.1.0", [1])
        release = self.Release._register_deployment("next", [2])
        self.assertEqual(release.version, "next")
        self.assertEqual(release._get_ticket_ids(), [2])

    def test_next_is_case_insensitive(self):
        self.Release._register_deployment("Next", [1])
        self.assertEqual(self.Release.search_count([("version", "=", "next")]), 1)

    def test_empty_version_is_ignored(self):
        self.assertFalse(self.Release._register_deployment("", [1]))
        self.assertEqual(self.Release.search_count([]), 0)

    def test_non_integer_tickets_are_ignored(self):
        release = self.Release._register_deployment("next", [1, "abc", None])
        self.assertEqual(release._get_ticket_ids(), [1])

    def test_environment(self):
        for environment in ("dev", "ci", "test"):
            with _set_running_env(environment):
                self.assertFalse(self.Release._get_environment())
        for environment in ("preprod", "prod"):
            with _set_running_env(environment):
                self.assertEqual(self.Release._get_environment(), environment)

    def test_payload(self):
        release = self.Release._register_deployment("14.0.1.0", [3, 1])
        with _set_running_env("preprod"):
            self.assertEqual(
                release._build_payload(),
                {
                    "environment": "preprod",
                    "version": "14.0.1.0",
                    "tickets": [1, 3],
                },
            )

    def test_next_release_to_send_is_oldest(self):
        first = self.Release._register_deployment("14.0.1.0", [1])
        second = self.Release._register_deployment("14.0.2.0", [2])
        self.assertEqual(self.Release._next_release_to_send(), first)
        first.is_sent = True
        self.assertEqual(self.Release._next_release_to_send(), second)

    def test_cron_pushes_one_release(self):
        first = self.Release._register_deployment("14.0.1.0", [1])
        second = self.Release._register_deployment("14.0.2.0", [2])
        with _set_running_env("preprod"), self._patch_request() as request:
            self.Release._cron_push_releases()
        self.assertEqual(request.call_count, 1)
        args, kwargs = request.call_args
        self.assertEqual(args, ("POST", "/release"))
        self.assertEqual(
            kwargs["data"],
            {
                "environment": "preprod",
                "version": "14.0.1.0",
                "tickets": [1],
            },
        )
        self.assertTrue(first.is_sent)
        self.assertFalse(second.is_sent)

    def test_cron_is_silent_without_environment(self):
        self.Release._register_deployment("14.0.1.0", [1])
        with _set_running_env("dev"), self._patch_request() as request:
            self.Release._cron_push_releases()
        request.assert_not_called()

    def test_failed_push_keeps_release_pending(self):
        release = self.Release._register_deployment("14.0.1.0", [1])
        with _set_running_env("preprod"), self._patch_request() as request:
            request.side_effect = Exception("boom")
            self.Release._cron_push_releases()
        self.assertFalse(release.is_sent)
        self.assertEqual(self.Release._next_release_to_send(), release)

    def test_button_pushes_all_pending(self):
        first = self.Release._register_deployment("14.0.1.0", [1])
        second = self.Release._register_deployment("14.0.2.0", [2])
        with _set_running_env("prod"), self._patch_request() as request:
            self.Release.action_push_pending()
        self.assertEqual(request.call_count, 2)
        self.assertTrue(first.is_sent)
        self.assertTrue(second.is_sent)

    def test_button_requires_an_environment(self):
        with _set_running_env("dev"):
            with self.assertRaises(UserError):
                self.Release.action_push_pending()
