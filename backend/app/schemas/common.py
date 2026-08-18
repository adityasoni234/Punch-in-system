from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ErrorResponse(BaseModel):
    """Flat, stable error envelope. Clients switch on `code`, never `message`."""

    success: bool = False
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int

    @property
    def pages(self) -> int:  # pragma: no cover - convenience
        return max(1, -(-self.total // self.page_size))


class MessageResponse(BaseModel):
    success: bool = True
    message: str
