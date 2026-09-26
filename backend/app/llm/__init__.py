import json
import httpx

from app import config


class LLMError(RuntimeError):
    pass


def _complete(base_url: str, api_key: str, model: str, messages: list[dict],
              max_tokens: int, temperature: float) -> str:
    body = {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": temperature}
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    resp = httpx.post(base_url.rstrip("/") + "/chat/completions", json=body, headers=headers,
                      timeout=config.LLM_TIMEOUT_S)
    if resp.status_code != 200:
        raise LLMError(f"LLM returned {resp.status_code}: {resp.text[:300]}")
    try:
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, ValueError) as exc:
        raise LLMError(f"LLM returned unexpected payload: {resp.text[:300]}") from exc
    if not isinstance(content, str) or not content.strip():
        raise LLMError("LLM returned empty completion")
    return content.strip()


def chat(messages: list[dict], *, model: str | None = None,
         max_tokens: int = 2500, temperature: float = 0.2) -> str:
    """Call the primary LLM endpoint, falling back to the keyless default."""
    model = model or config.LLM_MODEL
    try:
        return _complete(config.LLM_BASE_URL, config.LLM_API_KEY, model, messages, max_tokens, temperature)
    except LLMError as primary_err:
        if config.LLM_FALLBACK_BASE_URL and config.LLM_FALLBACK_BASE_URL != config.LLM_BASE_URL:
            try:
                return _complete(config.LLM_FALLBACK_BASE_URL, "", config.LLM_FALLBACK_MODEL, messages, max_tokens, temperature)
            except LLMError:
                pass
        raise primary_err


def chat_json(messages: list[dict], **kwargs) -> dict:
    text = chat(messages, **kwargs)
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise LLMError("LLM output contained no JSON object")
    try:
        parsed = json.loads(text[start:end + 1])
    except json.JSONDecodeError as exc:
        raise LLMError(f"LLM output was not valid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise LLMError("LLM output JSON was not an object")
    return parsed