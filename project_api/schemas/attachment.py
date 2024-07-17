# Copyright 2023 ACSONE SA/NV
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from typing import List
from uuid import UUID

from pydantic import BaseModel


class AttachmentReadInput(BaseModel):
    ids: List[int]
    fields: List[str]
    load: str


class AttachmentExistsInput(BaseModel):
    ids: List[int]
    

class AttachmentDownloadInput(BaseModel):
    attachment_id: int
