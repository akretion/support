# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).


from odoo import api, fields, models


class ResUsers(models.Model):
    _inherit = "res.users"

    def name_get(self):
        result = []
        standard_names = super().name_get()
        name_dict = dict(standard_names)
        
        # avoid to give rights on cross_connect_client
        for user in self.sudo():
            name = name_dict.get(user.id)
            # Si l'utilisateur a un serveur, on modifie le nom
            if user.cross_connect_client_id:
                name = f"{name} ({user.cross_connect_client_id.name})"
            result.append((user.id, name))
        return result
