"""Provider-independent LLM layer that returns validated JSON.

- ollama:    a local model, free, for development
- anthropic: Claude through the official SDK, for the real results
- stub:      deterministic rules, for CI and end-to-end tests (no model needed)
- fake:      scripted responses for unit tests
"""

import json
from dataclasses import dataclass, field
from typing import Protocol

import httpx

from app.config import settings


@dataclass
class LLMResult:
    data: dict
    model: str
    input_tokens: int = 0
    output_tokens: int = 0


class LLMError(RuntimeError):
    """The model call failed or returned something unusable."""


class LLMRefusal(LLMError):
    """The model declined the request (safety classifiers). The request goes to a human."""


class LLM(Protocol):
    name: str

    def complete_json(self, system: str, user: str, schema: dict, effort: str = "low") -> LLMResult: ...


class OllamaLLM:
    def __init__(self, url: str = settings.ollama_url, model: str = settings.ollama_model):
        self.url = url.rstrip("/")
        self.name = f"ollama:{model}"
        self._model = model

    def complete_json(self, system: str, user: str, schema: dict, effort: str = "low") -> LLMResult:
        try:
            r = httpx.post(
                f"{self.url}/api/chat",
                json={
                    "model": self._model,
                    "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                    "format": schema,  # Ollama constrains the output to this JSON schema
                    "stream": False,
                    "options": {"temperature": 0},
                },
                timeout=120,
            )
            r.raise_for_status()
        except httpx.HTTPError as e:
            raise LLMError(f"Ollama call failed: {e}") from e
        body = r.json()
        try:
            data = json.loads(body["message"]["content"])
        except (KeyError, json.JSONDecodeError) as e:
            raise LLMError("Ollama returned invalid JSON") from e
        return LLMResult(
            data=data,
            model=self.name,
            input_tokens=body.get("prompt_eval_count", 0),
            output_tokens=body.get("eval_count", 0),
        )


# Models that accept server-side refusal fallbacks (`fallbacks: "default"`)
_FALLBACK_MODELS = ("claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5", "claude-fable-5-2", "claude-fable-5-1")


class AnthropicLLM:
    def __init__(self, model: str = settings.anthropic_model):
        import anthropic

        self._anthropic = anthropic
        self._client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY (or an `ant auth login` profile)
        self._model = model
        self.name = model

    def complete_json(self, system: str, user: str, schema: dict, effort: str = "low") -> LLMResult:
        a = self._anthropic
        kwargs = {
            "model": self._model,
            "max_tokens": 8000,
            "system": system,
            "messages": [{"role": "user", "content": user}],
            "output_config": {"effort": effort, "format": {"type": "json_schema", "schema": schema}},
        }
        if self._model in _FALLBACK_MODELS:
            kwargs |= {"betas": ["server-side-fallback-2026-07-01"], "fallbacks": "default"}
        try:
            response = self._client.beta.messages.create(**kwargs)
        except a.RateLimitError as e:
            raise LLMError("Claude rate limit reached, try again shortly") from e
        except a.APIStatusError as e:
            raise LLMError(f"Claude API error {e.status_code}: {e.message}") from e
        except a.APIConnectionError as e:
            raise LLMError("Could not reach the Claude API") from e

        if response.stop_reason == "refusal":
            raise LLMRefusal("Claude declined this request")
        if response.stop_reason == "max_tokens":
            raise LLMError("Claude response was cut off (max_tokens)")
        text = next((b.text for b in response.content if b.type == "text"), None)
        if text is None:
            raise LLMError("Claude returned no text block")
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            raise LLMError("Claude returned invalid JSON") from e
        return LLMResult(
            data=data,
            model=response.model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )


@dataclass
class FakeLLM:
    """Returns scripted responses in order. Used by the unit tests."""

    responses: list[dict] = field(default_factory=list)
    name: str = "fake"
    calls: list[dict] = field(default_factory=list)

    def complete_json(self, system: str, user: str, schema: dict, effort: str = "low") -> LLMResult:
        self.calls.append({"system": system, "user": user, "effort": effort})
        if not self.responses:
            raise LLMError("FakeLLM has no scripted response left")
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return LLMResult(data=item, model=self.name, input_tokens=100, output_tokens=20)


def get_llm() -> LLM:
    provider = settings.llm_provider.lower()
    if provider == "anthropic":
        return AnthropicLLM()
    if provider == "ollama":
        return OllamaLLM()
    if provider == "stub":
        from app.stub_llm import StubLLM

        return StubLLM()
    if provider == "fake":
        return FakeLLM()
    raise ValueError(f"Unknown LLM_PROVIDER: {settings.llm_provider}")
