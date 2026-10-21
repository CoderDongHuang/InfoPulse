"""Explicit compatibility options for Qwen's official OpenAI endpoints."""
from urllib.parse import urlsplit


def chat_options(base_url: str, model: str) -> dict:
    # Existing callers consume final text/JSON, not reasoning traces. Some Qwen
    # models otherwise enable thinking by default and reject non-streaming calls.
    host = urlsplit(base_url).hostname
    if host in {"dashscope.aliyuncs.com", "dashscope-intl.aliyuncs.com", "dashscope-us.aliyuncs.com"} and model.startswith("qwen"):
        return {"extra_body": {"enable_thinking": False}}
    return {}
