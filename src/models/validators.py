"""Pydantic validation models for API requests."""

from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional
from datetime import date, datetime


class BackfillJiraRequest(BaseModel):
    """Validation for Jira backfill request parameters."""

    days: int = Field(
        default=2555, ge=1, le=3650, description="Number of days to backfill (1-3650)"
    )

    model_config = {"json_schema_extra": {"example": {"days": 365}}}


class BackfillNotionRequest(BaseModel):
    """Validation for Notion backfill request parameters."""

    days: int = Field(
        default=365, ge=1, le=3650, description="Number of days to backfill (1-3650)"
    )

    model_config = {"json_schema_extra": {"example": {"days": 365}}}


class BackfillTempoRequest(BaseModel):
    """Validation for Tempo backfill request parameters."""

    days: Optional[int] = Field(
        default=None, ge=1, le=3650, description="Number of days to backfill (1-3650)"
    )
    from_date: Optional[str] = Field(
        default=None, description="Start date in YYYY-MM-DD format"
    )
    to_date: Optional[str] = Field(
        default=None, description="End date in YYYY-MM-DD format"
    )
    batch_id: Optional[str] = Field(
        default=None, max_length=100, description="Batch identifier for tracking"
    )

    @field_validator("from_date", "to_date")
    @classmethod
    def validate_date_format(cls, v: Optional[str]) -> Optional[str]:
        """Validate date format is YYYY-MM-DD."""
        if v is None:
            return v
        try:
            # Parse and validate date format
            parsed_date = datetime.strptime(v, "%Y-%m-%d").date()
            # Check date is not in the future
            if parsed_date > date.today():
                raise ValueError("Date cannot be in the future")
            return v
        except ValueError as e:
            if "does not match format" in str(e):
                raise ValueError("Date must be in YYYY-MM-DD format")
            raise

    @model_validator(mode="after")
    def validate_date_range(self):
        """Validate to_date is after from_date."""
        if self.to_date and self.from_date:
            from_date_obj = datetime.strptime(self.from_date, "%Y-%m-%d").date()
            to_date_obj = datetime.strptime(self.to_date, "%Y-%m-%d").date()
            if to_date_obj < from_date_obj:
                raise ValueError("to_date must be after from_date")
        return self

    model_config = {
        "json_schema_extra": {
            "example": {
                "from_date": "2024-01-01",
                "to_date": "2024-12-31",
                "batch_id": "2024-annual",
            }
        }
    }


class BackfillFirefliesRequest(BaseModel):
    """Validation for Fireflies backfill request parameters."""

    days: int = Field(
        default=365, ge=1, le=3650, description="Number of days to backfill (1-3650)"
    )
    limit: int = Field(
        default=1000,
        ge=1,
        le=5000,
        description="Maximum number of meetings to process (1-5000)",
    )

    model_config = {"json_schema_extra": {"example": {"days": 365, "limit": 1000}}}


class BackfillGitHubRequest(BaseModel):
    """Validation for GitHub backfill request parameters."""

    days: int = Field(
        default=730, ge=1, le=3650, description="Number of days to backfill (1-3650)"
    )
    repos: Optional[str] = Field(
        default=None, description="Comma-separated list of repos (owner/repo format)"
    )

    model_config = {
        "json_schema_extra": {
            "example": {"days": 730, "repos": "syatt-io/agent-pm,syatt-io/frontend"}
        }
    }


class JiraQueryTestRequest(BaseModel):
    """Validation for Jira query test request parameters."""

    days: int = Field(
        default=2555, ge=1, le=3650, description="Number of days to query (1-3650)"
    )
    limit: int = Field(
        default=100, ge=1, le=1000, description="Maximum results to return (1-1000)"
    )

    model_config = {"json_schema_extra": {"example": {"days": 365, "limit": 100}}}
