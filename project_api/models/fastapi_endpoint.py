# Copyright 2024 Akretion (http://www.akretion.com).
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import SUPERUSER_ID, _, api, fields, models
from ..routers.support import support_api_router
from fastapi.security import APIKeyHeader
from fastapi import APIRouter, Depends, HTTPException, status
from odoo.addons.fastapi.dependencies import (
    authenticated_partner_impl,
    fastapi_endpoint_id,
    odoo_env,
)

from typing import List

from odoo.api import Environment
from odoo.exceptions import ValidationError

from odoo.addons.base.models.res_partner import Partner


def api_key_based_authenticated_partner_impl(
    api_key: str = Depends(  # noqa: B008
        APIKeyHeader(
            name="api-key",
            description="In this demo, you can use a user's login as api key.",
        )
    ),
    _id: int = Depends(fastapi_endpoint_id),  # noqa: B008
    env: Environment = Depends(odoo_env),  # noqa: B008
) -> Partner:
    key = env["auth.api.key"].with_user(SUPERUSER_ID)._retrieve_api_key(api_key)
    endpoint = env["fastapi.endpoint"].sudo().browse(_id)

    partner = env["res.partner"].sudo().search(
        [("project_auth_api_key_id", "=", key.id)], limit=1
    )
    if not key or key.user_id != endpoint.user_id or not partner:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect API Key"
        )
    return partner


class FastapiEndpoint(models.Model):
    _inherit = "fastapi.endpoint"

    app: str = fields.Selection(
        selection_add=[("support", "Support Endpoint")],
        ondelete={"support": "cascade"},
    )
    support_auth_method = fields.Selection(
        selection=[("api_key", "Api Key")],
        string="Authenciation method",
    )

    @api.constrains("app", "support_auth_method")
    def _valdiate_support_auth_method(self):
        for rec in self:
            if rec.app == "support" and not rec.support_auth_method:
                raise ValidationError(
                    _(
                        "The authentication method is required for app %(app)s",
                        app=rec.app,
                    )
                )
    
    def _get_fastapi_routers(self):
        if self.app == "support":
            return [support_api_router]
        return super()._get_fastapi_routers()

    @api.model
    def _fastapi_app_fields(self) -> List[str]:
        fields = super()._fastapi_app_fields()
        fields.append("support_auth_method")
        return fields

    def _get_app(self):
        app = super()._get_app()
        if self.app == "support":
            app.dependency_overrides[
                authenticated_partner_impl
            ] = api_key_based_authenticated_partner_impl
        return app
