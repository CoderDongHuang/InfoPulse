"""OpenAI-compatible LLM client with streaming and JSON helpers."""

import asyncio
import json
import re
from typing import AsyncIterator

from openai import AsyncOpenAI

from app.core.runtime_settings import RuntimeSettings
from app.core.private_clients import managed_model_client, model_http_client
from app.core.model_compat import chat_options

settings = RuntimeSettings()


def get_llm_client() -> AsyncOpenAI:
    """Create an owned client; credentials must never be cached across users."""
    return AsyncOpenAI(
        api_key=settings.LLM_API_KEY,
        base_url=settings.LLM_API_BASE,
        timeout=settings.LLM_TIMEOUT_SECONDS,
        max_retries=0,
        http_client=model_http_client(settings.LLM_TIMEOUT_SECONDS),
    )


def llm_is_configured() -> bool:
    key = settings.LLM_API_KEY.strip()
    return bool(key and "your-api-key" not in key)


async def stream_chat(
    system_prompt: str,
    user_message: str,
    temperature: float = 0.7,
    max_tokens: int = 2048,
) -> AsyncIterator[str]:
    """
    Stream a chat completion from the LLM.

    Yields text chunks (str) as they arrive from the API.
    Caller should concatenate chunks to form the full response.
    """
    async with managed_model_client(get_llm_client) as client:
        deadline = asyncio.get_running_loop().time() + settings.LLM_TIMEOUT_SECONDS
        stream = await asyncio.wait_for(client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_message}],
            temperature=temperature, max_tokens=max_tokens, stream=True,
            **chat_options(settings.LLM_API_BASE, settings.LLM_MODEL),
        ), timeout=settings.LLM_TIMEOUT_SECONDS)
        try:
            iterator = stream.__aiter__()
            while True:
                remaining = deadline - asyncio.get_running_loop().time()
                if remaining <= 0:raise asyncio.TimeoutError("LLM stream total budget exhausted")
                try:chunk = await asyncio.wait_for(iterator.__anext__(), timeout=remaining)
                except StopAsyncIteration:break
                if chunk.choices:
                    delta = chunk.choices[0].delta
                    if delta.content:yield delta.content
        finally:
            await stream.close()


async def complete_chat(
    system_prompt: str,
    user_message: str,
    temperature: float = 0.5,
    max_tokens: int = 2048,
    model: str | None = None,
) -> str:
    """Return a complete chat response."""
    async with managed_model_client(get_llm_client) as client:
        response = await asyncio.wait_for(client.chat.completions.create(
            model=model or settings.LLM_MODEL,
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_message}],
            temperature=temperature, max_tokens=max_tokens, stream=False,
            **chat_options(settings.LLM_API_BASE, model or settings.LLM_MODEL),
        ), timeout=settings.LLM_TIMEOUT_SECONDS)
        return response.choices[0].message.content or ""


async def complete_json(
    system_prompt: str,
    user_message: str,
    temperature: float = 0.3,
    max_tokens: int = 2048,
) -> dict:
    """Request JSON and tolerate fenced model output."""
    text = await complete_chat(system_prompt, user_message, temperature, max_tokens)
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    return json.loads(cleaned)
