# Copyright 2026 Akretion (http://www.akretion.com).
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from typing import Literal

from pydantic import BaseModel, Field


class ReleasePayload(BaseModel):
    environment: Literal["preprod", "prod"]
    version: str
    tickets: list[int] = Field(default_factory=list)
