# Copyright 2026 Akretion (http://www.akretion.com).
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models, tools
from odoo.exceptions import UserError

NEXT_VERSION = "next"
SUPPORTED_ENVIRONMENTS = ("preprod", "prod")


class SupportRelease(models.Model):
    _name = "support.release"
    _description = "Support Release"
    _rec_name = "version"
    _order = "create_date, id"

    version = fields.Char(
        required=True,
        index=True,
        help="Version of the deployment, or 'next' while no version is defined.",
    )
    tickets = fields.Json(
        help="Ids of the tickets shipped by this release.",
    )
    is_sent = fields.Boolean(
        default=False,
        copy=False,
        help="Set once the support server has accepted the release.",
    )

    _sql_constraints = [
        (
            "version_uniq",
            "unique(version)",
            "A release already exists for this version.",
        ),
    ]

    @api.model
    def _get_environment(self):
        """Return the deployment environment, or False when releases stay silent."""
        running_env = tools.config.get("running_env")
        return running_env if running_env in SUPPORTED_ENVIRONMENTS else False

    @api.model
    def _register_deployment(self, version, tickets):
        """Record a deployment, called from the migration of the project.

        Each deployment sends every ticket of the release, so the last payload
        replaces the previous one instead of completing it.
        """
        version = (version or "").strip()
        if version.lower() == NEXT_VERSION:
            version = NEXT_VERSION
        if not version:
            raise ValueError("a release needs a version")
        if not isinstance(tickets, list | tuple) or not all(
            isinstance(ticket, int) for ticket in tickets
        ):
            raise ValueError("tickets must be a list of ticket ids")
        release = self.search([("version", "=", version)]) or self.create(
            {"version": version}
        )
        release.tickets = list(tickets)
        if version != NEXT_VERSION:
            self.search([("version", "=", NEXT_VERSION)]).unlink()
        return release

    @api.model
    def _next_release_to_send(self):
        return self.search([("is_sent", "=", False)], limit=1)

    def _build_payload(self):
        self.ensure_one()
        return {
            "environment": self._get_environment(),
            "version": self.version,
            "tickets": self.tickets or [],
        }

    def _push(self):
        self.ensure_one()
        server = self.env.ref("support.support_server", raise_if_not_found=False)
        if not server:
            raise UserError(_("The support server is not configured."))
        server.sudo()._request("POST", "/release", data=self._build_payload())
        self.is_sent = True

    @api.model
    def _cron_push_releases(self):
        """Push the oldest pending release, one per cron run."""
        if not self._get_environment():
            return
        release = self._next_release_to_send()
        if release:
            release._push()
