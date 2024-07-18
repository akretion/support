# Copyright 2023 ACSONE SA/NV
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from typing import List

from pydantic import BaseModel, Field


class Partner(BaseModel):
    name: str
    uid: int
    image: str | None
    email: str | None
    mobile: str | None
    phone: str | None


class TaskCreateVals(BaseModel):
    name: str = None
    description: str = None
    origin_model: str = None
    origin_url: str = None
    origin_db: str = None
    origin_name: str = None
    action_id: int = None
    project_id: int = None
    tag_ids: List = None
    priority: str = None
    author: Partner = None
    attachment_ids: List = None
    functional_area: str = None
    assignee_customer: Partner = None


class TaskWriteVals(BaseModel):
    name: str = None
    description: str = None
    project_id: int = None
    stage_name: str = None
    stage_id: int = None
    tag_ids: List = None
    priority: str = None
    attachment_ids: List = None
    functional_area: str = None


class TaskSearchInput(BaseModel):
    domain: List
    offset: int
    limit: int | None
    order: str | None
    count: bool


class TaskReadInput(BaseModel):
    ids: List[int]
    fields: List[str]
    load: str


class TaskReadGroupInput(BaseModel):
    domain: List
    fields: List[str]
    groupby: List[str]
    offset: int
    limit: int | None
    orderby: str
    lazy: bool


class TaskCreateInput(BaseModel):
    name: str = None
    description: str = None
    origin_model: str = None
    origin_url: str = None
    origin_db: str = None
    origin_name: str = None
    action_id: int = None
    project_id: int = None
    tag_ids: List = None
    priority: str = None
    author: Partner = None
    attachment_ids: List = None
    functional_area: str = None
    assignee_customer: Partner = None


class TaskWriteInput(BaseModel):
    ids: List[int]
    vals: TaskWriteVals
    author: Partner
    assignee_customer: Partner | None = None


class TaskMessageFormatInput(BaseModel):
    ids: List[int]


class TaskGetMessageInput(BaseModel):
    ids: str
    domain: str
    message_unload_ids: str
    thread_level: int = 0
    context: str
    parent_id: int = 0
    limit: int = 0


class TaskMessageFetchInput(BaseModel):
    domain: List
    limit: int = 0


class TaskMessagePostInput(BaseModel):
    id: int = Field(alias="_id")
    body: str
    author: Partner
