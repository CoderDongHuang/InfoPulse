"""OpenAI-compatible LLM client with streaming and JSON helpers."""

import json
import re
from typing import AsyncIterator

from openai import AsyncOpenAI

from app.config import get_settings

settings = get_settings()

_client: AsyncOpenAI | None = None


def get_llm_client() -> AsyncOpenAI:
    """Return a singleton AsyncOpenAI client."""
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_API_BASE,
        )
    return _client


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
    client = get_llm_client()
    stream = await client.chat.completions.create(
        model=settings.LLM_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
        stream=True,
    )

    async for chunk in stream:
        delta = chunk.choices[0].delta
        if delta.content:
            yield delta.content


async def complete_chat(
    system_prompt: str,
    user_message: str,
    temperature: float = 0.5,
    max_tokens: int = 2048,
    model: str | None = None,
) -> str:
    """Return a complete chat response."""
    client = get_llm_client()
    response = await client.chat.completions.create(
        model=model or settings.LLM_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
        stream=False,
    )
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
