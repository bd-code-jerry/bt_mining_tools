from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, StrictStr


class LedgerBody(BaseModel):
    model_config = ConfigDict(extra='forbid')


class CategoryBody(LedgerBody):
    name: StrictStr = Field(max_length=200)
    parent_id: StrictInt | None = Field(default=None, ge=1)


class CategoryPatch(LedgerBody):
    name: StrictStr | None = Field(default=None, max_length=200)
    parent_id: StrictInt | None = Field(default=None, ge=1)
    archived: StrictBool | None = None


class CostBody(LedgerBody):
    amount: StrictStr = Field(max_length=100)
    expense_date: StrictStr = Field(max_length=10)
    category_id: StrictInt = Field(ge=1)
    note: StrictStr = Field(default='', max_length=4000)
    participant_ids: list[StrictInt] = Field(min_length=1, max_length=10000)
    request_id: StrictStr | None = Field(default=None, min_length=1, max_length=200)


class CreateCostBody(CostBody):
    request_id: StrictStr = Field(min_length=1, max_length=200)


class TransferBody(LedgerBody):
    kind: Literal['origin','received']
    amount: StrictStr = Field(max_length=100)
    transfer_date: StrictStr = Field(max_length=10)
    note: StrictStr = Field(default='', max_length=4000)
    request_id: StrictStr | None = Field(default=None, min_length=1, max_length=200)


class CreateTransferBody(TransferBody):
    request_id: StrictStr = Field(min_length=1, max_length=200)
