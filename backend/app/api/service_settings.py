"""Authenticated write-only credentials; no arbitrary-user configuration endpoint."""
import asyncio
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.llm import complete_chat
from app.core.private_clients import smtp_connection
from app.core.runtime_settings import use_settings
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.service_settings import ServiceSettingsUpdate
from app.services.service_settings import owner_settings, read_settings, save_settings

router = APIRouter(prefix="/api/v1/settings/services", tags=["Private service settings"])


def no_store(response):
    response.headers["Cache-Control"] = "no-store"


@router.get("")
async def read(response: Response, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    no_store(response)
    return await read_settings(db, user.id)


@router.put("")
async def save(payload: ServiceSettingsUpdate, response: Response, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    no_store(response)
    return await save_settings(db, user.id, payload)


@router.post("/test/{service}")
async def test(service: Literal["llm", "smtp"], response: Response, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    no_store(response)
    settings = await owner_settings(db, user.id)
    try:
        if service == "llm":
            if not settings.LLM_API_KEY:
                raise ValueError("missing credential")
            with use_settings(settings):
                result = await complete_chat("Reply briefly.", "Reply OK.", max_tokens=16, temperature=0)
            if not result.strip():
                raise ValueError("empty response")
        else:
            if not settings.SMTP_HOST or not settings.SMTP_FROM:
                raise ValueError("missing SMTP configuration")
            def check():
                with smtp_connection(settings) as smtp:
                    if smtp.noop()[0] != 250:
                        raise ValueError("SMTP handshake rejected")
            await asyncio.wait_for(asyncio.to_thread(check), timeout=35)
    except Exception:
        raise HTTPException(400, "Connection test failed. Check saved configuration, network access and provider permissions; credentials and provider errors are hidden.") from None
    return {"ok": True, "service": service, "message": "Model replied successfully" if service == "llm" else "SMTP TLS/authentication succeeded; no email was sent"}
