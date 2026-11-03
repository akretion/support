# Copyright 2026 Akretion (http://www.akretion.com).
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
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
        help="Partner of the projects of the client.",
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

    @api.model
    def _get_client_partner(self, client):
        """Partner of the projects of the client, which has to be unique."""
        partners = client.project_ids.partner_id
        if len(partners) > 1:
            raise ValidationError(
                _(
                    "The projects of %(client)s belong to several partners: "
                    "%(partners)s",
                    client=client.name,
                    partners=", ".join(partners.mapped("name")),
                )
            )
        return partners

    @api.model
    def _filter_tickets(self, partner, ticket_ids):
        """Keep the tickets of the partner of the client, report the others.

        The tickets of an internal project have no cross connect client but
        share the partner of the customer, so they belong to the release too,
        the mail leaving them out.
        """
        tasks = self.env["project.task"].browse(ticket_ids).exists()
        messages = []
        unknown = sorted(set(ticket_ids) - set(tasks.ids))
        if unknown:
            messages.append(_("Unknown tickets: %s", unknown))
        if not partner:
            if tasks:
                messages.append(
                    _("No partner on the projects of the client, no ticket linked.")
                )
            return self.env["project.task"], messages
        kept = tasks.filtered(lambda task: task.project_id.partner_id == partner)
        dropped = tasks - kept
        if dropped:
            messages.append(
                _("Tickets of another partner, not linked: %s", dropped.ids)
            )
        return kept, messages

    def _prepare_release_vals(self, partner, environment, tasks, messages):
        return {
            DEPLOYED_FIELDS[environment]: fields.Datetime.now(),
            "message": "\n".join(messages) or False,
            "partner_id": partner.id,
            "task_ids": [Command.set(tasks.ids)],
        }

    def _add_message(self, message):
        self.ensure_one()
        self.message = "\n".join(filter(None, [self.message, message]))

    def _apply_stages(self, stage):
        """Move the tickets of the release to the stage of the environment."""
        self.task_ids.sudo().stage_id = stage

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
        """Emails of the users to notify, set on the partner of the release."""
        users = self.partner_id.support_release_notification_user_ids.filtered(
            lambda user: user.active and user.email
        )
        return ", ".join(sorted(set(users.mapped("email"))))

    def _get_notified_tasks(self):
        """Tickets announced to the customer.

        The projects without a cross connect client are internal maintenance,
        invisible on the portal of the customer, so their tickets stay out of
        the mail even when they are linked to the release.
        """
        return self.task_ids.filtered(
            lambda task: task.project_id.cross_connect_client_id
        )

    def _notify_prod_release(self):
        """Tell the users of the customer that the release reached production."""
        self.ensure_one()
        if not self._get_notification_emails():
            self._add_message(
                _("No user with an email address to notify the production deployment.")
            )
            return
        if not self._get_notified_tasks():
            self._add_message(
                _("No ticket of a customer project to announce in the release mail.")
            )
            return
        self.env.ref(RELEASE_IN_PROD_TEMPLATE).send_mail(self.id, force_send=False)

    @api.model
    def _process(self, client, payload):
        """Record a release received from a client and apply it."""
        release = self._get_release(client, payload["version"])
        if release.prod_deployed_at:
            return release
        environment = payload["environment"]
        partner = self._get_client_partner(client)
        tasks, messages = self._filter_tickets(partner, payload.get("tickets") or [])
        release.write(self._prepare_release_vals(partner, environment, tasks, messages))
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
