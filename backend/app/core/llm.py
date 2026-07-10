"""
InfoPulse — LLM Client
=======================
OpenAI-compatible chat client with streaming support.
"""

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
