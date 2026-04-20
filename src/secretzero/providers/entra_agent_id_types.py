"""Typed models for Entra Agent ID provider operations."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class EntraCredentialSpec(BaseModel):
    """Credential definition for an Entra Agent Identity Blueprint."""

    type: str
    display_name: str | None = None
    end_date_time: str | None = None
    name: str | None = None
    issuer: str | None = None
    subject: str | None = None
    audiences: list[str] = Field(default_factory=list)
    certificate_pem: str | None = None
    custom_claims: dict[str, Any] = Field(default_factory=dict)


class EntraAgentIdentitySpec(BaseModel):
    """Child agent identity declaration."""

    display_name: str
    sponsor: str | None = None
    tags: list[str] = Field(default_factory=list)


class EntraBlueprintSpec(BaseModel):
    """Top-level blueprint declaration."""

    display_name: str
    sponsors: list[str] = Field(default_factory=list)
    owners: list[str] = Field(default_factory=list)
    identifier_uris: list[str] = Field(default_factory=list)
    oauth_scopes: list[dict[str, Any]] = Field(default_factory=list)


class EntraBlueprintOperationSpec(BaseModel):
    """Complete provider operation payload for blueprint orchestration."""

    tenant_id: str
    blueprint: EntraBlueprintSpec
    credentials: list[EntraCredentialSpec] = Field(default_factory=list)
    agent_identities: list[EntraAgentIdentitySpec] = Field(default_factory=list)
    rotation_policy: dict[str, Any] = Field(default_factory=dict)
