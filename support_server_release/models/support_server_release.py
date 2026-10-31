# Copyright 2026 Akretion (http://www.akretion.com).
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

NEXT_VERSION = "next"
STAGE_PARAMETER = "support_server_release.stage_%s_id"
TASK_ACTION_XMLID = "project.action_view_task"
RELEASE_IN_PROD_TEMPLATE = "support_server_release.mail_template_release_in_prod"
DEPLOYED_FIELDS = {
    "preprod": "preprod_deployed_at",
    "prod": "prod_deployed_at",
}


class SupportServerRelease(models.Model):
    _name = "support.server.release"
    _description = "Support Release"
    _rec_name = "version"
    _order = "version desc, id desc"

    version = fields.Char(
        required=True,
        index=True,
        help="Version of the deployment, or 'next' while no version is defined.",
    )
    cross_connect_client_id = fields.Many2one(
        "cross.connect.client",
        required=True,
        index=True,
        ondelete="cascade",
        string="Client",
    )
    partner_id = fields.Many2one(
        "res.partner",
        index=True,
        help="Partner of the projects of the tickets of this release.",
    )
    task_ids = fields.Many2many(
        "project.task",
        relation="support_server_release_project_task_rel",
        column1="release_id",
        column2="task_id",
        string="Tickets",
    )
    preprod_deployed_at = fields.Datetime()
    prod_deployed_at = fields.Datetime()

    _sql_constraints = [
        (
            "client_version_uniq",
            "unique(cross_connect_client_id, version)",
            "This version is already registered for this client.",
        ),
    ]

    @api.model
    def _get_tickets(self, ticket_ids):
        """Resolve the ticket ids of a payload, ignoring the unknown ones."""
        tasks = self.env["project.task"].browse(ticket_ids).exists()
        unknown = sorted(set(ticket_ids) - set(tasks.ids))
        if unknown:
            _logger.warning("Ignoring unknown ticket ids %s", unknown)
        return tasks

    @api.model
    def _get_partner(self, tasks):
        """Partner of the projects of the tickets, when there is one."""
        partners = tasks.project_id.partner_id.filtered(lambda partner: partner)
        if len(partners) > 1:
            _logger.warning(
                "Tickets belong to several partners %s, keeping %s",
                partners.ids,
                partners[0].id,
            )
        return partners[:1]

    @api.model
    def _get_stage(self, environment):
        stage_id = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param(STAGE_PARAMETER % environment)
        )
        if not stage_id:
            return self.env["project.task.type"]
        return self.env["project.task.type"].browse(int(stage_id)).exists()

    def _apply_stages(self, stage):
        """Move the tickets forward to the stage of the environment, never back."""
        self.ensure_one()
        moved = 0
        for task in self.task_ids:
            try:
                current_stage = task.stage_id
                if current_stage and (stage.sequence, stage.id) <= (
                    current_stage.sequence,
                    current_stage.id,
                ):
                    continue
                with self.env.cr.savepoint():
                    if stage not in task.project_id.type_ids:
                        task.project_id.sudo().write({"type_ids": [(4, stage.id)]})
                    task.sudo().write({"stage_id": stage.id})
                moved += 1
            except Exception:
                _logger.exception(
                    "Unable to move ticket %s to stage %s", task.id, stage.name
                )
        return moved

    def _absorb_next_release(self):
        """Merge the pending 'next' release of the client, then drop it."""
        self.ensure_one()
        next_release = self.search(
            [
                ("cross_connect_client_id", "=", self.cross_connect_client_id.id),
                ("version", "=", NEXT_VERSION),
            ]
        )
        if not next_release:
            return
        if next_release.task_ids:
            self.write(
                {"task_ids": [(4, task_id) for task_id in next_release.task_ids.ids]}
            )
        next_release.unlink()

    def _get_task_url(self, task):
        """URL opening the ticket form in the web client of this database."""
        return f"{self.get_base_url()}/odoo/action-{TASK_ACTION_XMLID}/{task.id}"

    def _get_notification_emails(self):
        """Emails of the users of the client, the recipients of the release mail."""
        users = self.cross_connect_client_id.user_ids.filtered(
            lambda user: user.active and user.email
        )
        return ", ".join(sorted(set(users.mapped("email"))))

    def _notify_prod_release(self):
        """Tell the users of the client that the release reached production."""
        self.ensure_one()
        if not self._get_notification_emails():
            _logger.info(
                "No user to notify for release %s of %s",
                self.version,
                self.cross_connect_client_id.name,
            )
            return
        template = self.env.ref(RELEASE_IN_PROD_TEMPLATE, raise_if_not_found=False)
        if template:
            template.send_mail(self.id, force_send=False)

    @api.model
    def _process(self, client, payload):
        """Handle a release payload received from a client."""
        environment = payload["environment"]
        version = payload["version"]
        release = self.search(
            [
                ("cross_connect_client_id", "=", client.id),
                ("version", "=", version),
            ]
        )
        if environment == "preprod" and release.prod_deployed_at:
            _logger.info(
                "Release %s of %s is already in prod, preprod payload ignored",
                version,
                client.name,
            )
            return release
        tasks = self._get_tickets(payload.get("tickets") or [])
        partner = release.partner_id or self._get_partner(tasks)
        if partner:
            foreign = tasks.filtered(lambda task: task.project_id.partner_id != partner)
            if foreign:
                _logger.warning(
                    "Release %s: tickets %s belong to another partner, ignored",
                    version,
                    foreign.ids,
                )
                tasks -= foreign
        if not release:
            release = self.create(
                {"version": version, "cross_connect_client_id": client.id}
            )
        field_name = DEPLOYED_FIELDS[environment]
        vals = {field_name: fields.Datetime.now()}
        if partner:
            vals["partner_id"] = partner.id
        if tasks:
            vals["task_ids"] = [(4, task_id) for task_id in tasks.ids]
        release.write(vals)
        stage = self._get_stage(environment)
        if stage:
            release._apply_stages(stage)
        if version != NEXT_VERSION:
            release._absorb_next_release()
        if environment == "prod":
            release._notify_prod_release()
        return release
