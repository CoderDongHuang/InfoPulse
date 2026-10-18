"""Private configuration persistence and effective owner settings."""
import json

from cryptography.fernet import InvalidToken
from fastapi import HTTPException
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError

from app.config import get_settings
from app.models.service_settings import UserServiceSettings
from app.schemas.service_settings import ServiceSettingsUpdate
from app.services.platform import cipher

SECRET_FIELDS = {"llm_api_key", "smtp_password"}
FIELDS = {
    "llm_api_base": "LLM_API_BASE", "llm_model": "LLM_MODEL", "llm_api_key": "LLM_API_KEY",
    "media_vision_model": "MEDIA_VISION_MODEL", "media_transcription_model": "MEDIA_TRANSCRIPTION_MODEL",
    "smtp_host": "SMTP_HOST", "smtp_port": "SMTP_PORT", "smtp_username": "SMTP_USERNAME",
    "smtp_password": "SMTP_PASSWORD", "smtp_from": "SMTP_FROM",
}


def encryption_ready():
    key = get_settings().PLATFORM_ENCRYPTION_KEY
    return len(key) >= 32 and key != get_settings().JWT_SECRET_KEY and not key.startswith("change-me")


async def load_private(db, user_id):
    row = await db.get(UserServiceSettings, user_id)
    if not row:
        return {}, 0
    if not encryption_ready():
        raise HTTPException(503, "Private configuration encryption is unavailable; contact the instance owner")
    try:
        envelope = json.loads(cipher().decrypt(row.ciphertext.encode()))
        # Bind ciphertext to its owner, preventing accidental row swaps on restore.
        if envelope["user_id"] != user_id:
            raise ValueError("owner mismatch")
        return envelope["values"], row.revision
    except (InvalidToken, ValueError, KeyError, TypeError):
        raise HTTPException(503, "Private configuration cannot be decrypted; restore the original encryption key") from None


async def owner_settings(db, user_id):
    values, _ = await load_private(db, user_id)
    # Personal execution never silently spends the instance owner's credentials.
    defaults = ServiceSettingsUpdate(revision=0).model_dump(exclude={"revision", "clear_secrets"})
    defaults.update({key: "" for key in SECRET_FIELDS})
    defaults.update(values)
    return get_settings().model_copy(update={FIELDS[key]: value for key, value in defaults.items()})


async def read_settings(db, user_id):
    values, revision = await load_private(db, user_id)
    runtime = await owner_settings(db, user_id)
    public = {key: getattr(runtime, attr) for key, attr in FIELDS.items() if key not in SECRET_FIELDS}
    return {**public, "revision": revision, "encryption_ready": encryption_ready(),
            "llm_api_key_configured": bool(values.get("llm_api_key")),
            "smtp_password_configured": bool(values.get("smtp_password")),
            "capabilities": {
                "public_data": True,
                "text_ai": bool(runtime.LLM_API_KEY),
                "vision": bool(runtime.LLM_API_KEY and runtime.MEDIA_VISION_MODEL),
                "transcription": bool(runtime.LLM_API_KEY and runtime.MEDIA_TRANSCRIPTION_MODEL),
                "email": bool(runtime.SMTP_HOST and runtime.SMTP_FROM),
                "media_worker_enabled": runtime.MEDIA_WORKER_ENABLED,
            }}


async def save_settings(db, user_id, payload: ServiceSettingsUpdate):
    if not encryption_ready():
        raise HTTPException(503, "Set an independent PLATFORM_ENCRYPTION_KEY of at least 32 characters first")
    old, revision = await load_private(db, user_id)
    if revision != payload.revision:
        raise HTTPException(409, "Configuration changed in another tab; reload before saving")
    values = payload.model_dump(exclude={"revision", "clear_secrets", *SECRET_FIELDS})
    for key in SECRET_FIELDS:
        raw = getattr(payload, key).get_secret_value()
        if raw and key in payload.clear_secrets:
            raise HTTPException(422, "A credential cannot be replaced and cleared together")
        values[key] = "" if key in payload.clear_secrets else raw or old.get(key, "")
    # A retained key must never be sent to a newly entered endpoint without explicit re-entry.
    if values["llm_api_base"] != old.get("llm_api_base", values["llm_api_base"]) and values["llm_api_key"] and not payload.llm_api_key.get_secret_value():
        raise HTTPException(422, "Changing the model endpoint requires re-entering or clearing its API key")
    if values["smtp_host"] != old.get("smtp_host", values["smtp_host"]) and values["smtp_password"] and not payload.smtp_password.get_secret_value():
        raise HTTPException(422, "Changing the SMTP host requires re-entering or clearing its password")
    encrypted = cipher().encrypt(json.dumps({"user_id": user_id, "values": values}).encode()).decode()
    try:
        if revision == 0:
            db.add(UserServiceSettings(user_id=user_id, ciphertext=encrypted, revision=1))
        else:
            result = await db.execute(update(UserServiceSettings).where(
                UserServiceSettings.user_id == user_id, UserServiceSettings.revision == revision
            ).values(ciphertext=encrypted, revision=revision + 1))
            if result.rowcount != 1:
                raise HTTPException(409, "Configuration changed in another tab; reload before saving")
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "Configuration changed in another tab; reload before saving") from None
    return await read_settings(db, user_id)
