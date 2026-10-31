# Copyright 2026 Akretion (http://www.akretion.com).
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.fields import Command

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
    _order = "id desc"

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
    message = fields.Text(
        readonly=True,
        copy=False,
        help="What could not be applied to this release, to be checked by hand.",
    )

    _sql_constraints = [
        (
            "client_version_uniq",
            "unique(cross_connect_client_id, version)",
            "This version is already registered for this client.",
        ),
    ]

    @api.model
    def _get_release(self, client, version):
        release = self.search(
            [("cross_connect_client_id", "=", client.id), ("version", "=", version)]
        )
        if release:
            return release
        return self.create({"version": version, "cross_connect_client_id": client.id})

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

    def _filter_tickets(self, release, ticket_ids):
        """Keep the tickets of the partner of the release, report what is dropped."""
        tasks = self.env["project.task"].browse(ticket_ids).exists()
        messages = []
        unknown = sorted(set(ticket_ids) - set(tasks.ids))
        if unknown:
            messages.append(_("Unknown tickets: %s", unknown))
        partner = release.partner_id or tasks.project_id.partner_id[:1]
        if not partner:
            if tasks:
                messages.append(
                    _("No partner on the projects of the tickets, no ticket linked.")
                )
            return self.env["project.task"], messages
        kept = tasks.filtered(lambda task: task.project_id.partner_id == partner)
        dropped = tasks - kept
        if dropped:
            messages.append(
                _("Tickets of another partner, not linked: %s", dropped.ids)
            )
        return kept, messages

    def _release_vals(self, environment, tasks, messages):
        vals = {
            DEPLOYED_FIELDS[environment]: fields.Datetime.now(),
            "message": "\n".join(messages) or False,
        }
        if tasks:
            vals["task_ids"] = [Command.link(task.id) for task in tasks]
            vals["partner_id"] = tasks.project_id.partner_id[:1].id
        return vals

    def _add_message(self, message):
        self.ensure_one()
        self.message = "\n".join(filter(None, [self.message, message]))

    def _apply_stages(self, stage):
        """Move the tickets of the release to the stage of the environment."""
        for task in self.task_ids:
            if stage not in task.project_id.type_ids:
                task.project_id.sudo().write({"type_ids": [Command.link(stage.id)]})
            task.sudo().write({"stage_id": stage.id})

    def _remove_next_release(self):
        """Drop the pending 'next' release, the payload already carries its tickets."""
        self.search(
            [
                ("cross_connect_client_id", "=", self.cross_connect_client_id.id),
                ("version", "=", NEXT_VERSION),
            ]
        ).unlink()

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
            self._add_message(
                _("No user with an email address to notify the production deployment.")
            )
            return
        self.env.ref(RELEASE_IN_PROD_TEMPLATE).send_mail(self.id, force_send=False)

    @api.model
    def _process(self, client, payload):
        """Record a release received from a client and apply it."""
        environment = payload["environment"]
        release = self._get_release(client, payload["version"])
        if environment == "preprod" and release.prod_deployed_at:
            return release
        tasks, messages = self._filter_tickets(release, payload.get("tickets") or [])
        release.write(self._release_vals(environment, tasks, messages))
        stage = self._get_stage(environment)
        if stage:
            release._apply_stages(stage)
        else:
            release._add_message(
                _("No stage configured for %s, no ticket moved.", environment)
            )
        if payload["version"] != NEXT_VERSION:
            release._remove_next_release()
        if environment == "prod":
            release._notify_prod_release()
        return release
