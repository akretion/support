# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).


from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    @api.depends('user_ids.cross_connect_client_id')
    def _compute_display_name(self):
        return super()._compute_display_name()

    def name_get(self):
        res = super().name_get()
        name_dict = dict(res)
        final_res = []
        # avoid to give rights on cross_connect_client
        for partner in self.sudo():
            name = name_dict.get(partner.id)
            server = partner.user_ids.cross_connect_client_id
            if server:
                name = f"{name} ({server.name})"
            final_res.append((partner.id, name))
        return final_res
