from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


ParseMode = Literal["decoded", "raw"]


class ParseResponse(BaseModel):
    metadata: dict[str, Any]
    summary: dict[str, Any]
    events: list[dict[str, Any]] | None = Field(default=None)
    aggregates: dict[str, Any] | None = Field(default=None)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class SkillSummaryResponse(BaseModel):
    metadata: dict[str, Any]
    summary: dict[str, Any]
    skill_summary: list[dict[str, Any]] = Field(default_factory=list)
    player_mapping: list[dict[str, Any]] = Field(default_factory=list)
    skill_by_player: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class SkillSyncRequest(BaseModel):
    skill_ids: list[int] = Field(default_factory=list)
    api_key: str | None = None


class SkillSyncResponse(BaseModel):
    requested_count: int
    updated_count: int
    updated: dict[str, str] = Field(default_factory=dict)
