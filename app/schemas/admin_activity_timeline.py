from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _to_optional_string(value: Any) -> str | None:
    if value is None or value == "":
        return None
    return str(value)


class ActivityTimelineLogItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    timestamp: str | None = None
    operatorEmail: str | None = None
    operatorFullName: str | None = None
    operatorRole: str | None = None
    area: str | None = None
    module: str | None = None
    action: str | None = None
    actionLabel: str | None = None
    severity: str | None = None
    targetType: str | None = None
    targetId: str | None = None
    targetLabel: str | None = None
    summary: str | None = None
    metadata: str | None = None
    ipAddress: str | None = None
    userAgent: str | None = None
    traceId: str | None = None

    @field_validator("*", mode="before")
    @classmethod
    def coerce_to_string(cls, value: Any) -> str | None:
        return _to_optional_string(value)


class ActivityTimelineSummaryRequest(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    userId: str | None = None
    email: str | None = None
    from_time: str | None = Field(default=None, alias="from")
    to: str | None = None
    severity: str | None = None
    module: str | None = None
    action: str | None = None
    size: int | None = None
    logs: list[ActivityTimelineLogItem] = Field(default_factory=list)

    @field_validator("userId", "email", "from_time", "to", "severity", "module", "action", mode="before")
    @classmethod
    def coerce_filter_to_string(cls, value: Any) -> str | None:
        return _to_optional_string(value)

    @field_validator("logs", mode="before")
    @classmethod
    def default_logs(cls, value: Any) -> list[Any]:
        if value is None:
            return []
        return value


class ActivityTimelineSummaryResponse(BaseModel):
    lines: list[str]