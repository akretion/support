# Copyright 2026 Akretion (http://www.akretion.com).
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from typing import Annotated

from fastapi import APIRouter, Depends

from odoo import api

from odoo.addons.cross_connect_server.dependencies import (
    authenticated_cross_connect_client,
)
from odoo.addons.cross_connect_server.models.cross_connect_client import (
    CrossConnectClient,
)
from odoo.addons.fastapi.dependencies import odoo_env

from ..schemas import ReleasePayload

release_router = APIRouter(tags=["Support Release"])


@release_router.post("/cross_connect/release")
def post_release(
    env: Annotated[api.Environment, Depends(odoo_env)],
    client: Annotated[CrossConnectClient, Depends(authenticated_cross_connect_client)],
    payload: ReleasePayload,
) -> dict:
    """Receive a release deployed on a customer project."""
    env["support.server.release"].sudo()._process(client, payload.model_dump())
    return {"ok": True}
