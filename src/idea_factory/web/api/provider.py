"""Provider and API key management endpoints."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from idea_factory.web.deps import get_settings

router = APIRouter(tags=["provider"])


class ProviderStatus(BaseModel):
    provider: str
    model: str
    has_key: bool


class SetProviderPayload(BaseModel):
    provider: str
    api_key: str = ""


@router.get("/provider")
def get_provider() -> ProviderStatus:
    settings = get_settings()
    has_key = bool(settings.active_api_key())
    return ProviderStatus(
        provider=settings.llm_provider,
        model=settings.model,
        has_key=has_key,
    )


@router.post("/provider")
def set_provider(payload: SetProviderPayload) -> ProviderStatus:
    settings = get_settings()
    api_key = payload.api_key.strip() if payload.api_key else None
    settings.set_provider(payload.provider, api_key)
    has_key = bool(settings.active_api_key())
    return ProviderStatus(
        provider=settings.llm_provider,
        model=settings.model,
        has_key=has_key,
    )
