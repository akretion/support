# Copyright 2022 Akretion (https://www.akretion.com).
# @author Sébastien BEAU <sebastien.beau@akretion.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import models


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    def binary_content(
        self,
        xmlid=None,
        model="ir.attachment",
        id=None,
        field="datas",
        unique=False,
        filename=None,
        filename_field="name",
        download=False,
        mimetype=None,
        default_mimetype="application/octet-stream",
        access_token=None,
    ):
        if model == "external.attachment":
            data = (
                self.env["external.attachment"]
                .browse(id)
                .read(
                    [
                        "datas_fname",
                        "datas",
                        "mimetype",
                    ]
                )[0]
            )
            return self._binary_set_headers(
                200,
                data["datas"],
                data["datas_fname"],
                data["mimetype"],
                unique,
                download=download,
            )
        else:
            return super().binary_content(
                xmlid=xmlid,
                model=model,
                id=id,
                field=field,
                unique=unique,
                filename=filename,
                filename_field=filename_field,
                download=download,
                mimetype=mimetype,
                default_mimetype=default_mimetype,
                access_token=access_token,
            )
