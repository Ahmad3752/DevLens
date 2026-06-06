from typing import Any, Literal

from pydantic import BaseModel, Field


CacheStatus = Literal["hit", "miss", "disabled", "error"]


class JobFilters(BaseModel):
    employment_type: str | None = None
    experience_level: str | None = None
    workplace_type: str | None = None
    limit: int = 50


class RelevantJob(BaseModel):
    id: str
    title: str
    company: str
    url: str
    platform: str
    platforms: list[str] = Field(default_factory=list)
    location_raw: str | None = None
    city: str | None = None
    country: str = "Pakistan"
    role_keys: list[str] = Field(default_factory=list)
    role_labels: list[str] = Field(default_factory=list)
    employment_type: str = "unknown"
    experience_level: str = "unknown"
    is_internship: bool = False
    is_remote: bool = False
    workplace_type: str = "unknown"
    tech_stack: list[str] = Field(default_factory=list)
    requirements: list[str] = Field(default_factory=list)
    responsibilities: list[str] = Field(default_factory=list)
    benefits: list[str] = Field(default_factory=list)
    salary_min: float | None = None
    salary_max: float | None = None
    salary_currency: str | None = None
    salary_period: str = "unknown"
    salary_raw: str | None = None
    posted_at: str | None = None
    scraped_at: str | None = None


class CandidateJobsResponse(BaseModel):
    candidate_id: str
    role_key: str
    role_label: str
    filters: JobFilters
    cache_status: CacheStatus
    jobs: list[RelevantJob] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
