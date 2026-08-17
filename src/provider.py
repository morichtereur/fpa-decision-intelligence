"""Model access behind one interface, so the provider is configuration.

The commentary layer needs exactly one capability: a system prompt, a user
prompt, and text back. That is the common denominator across the Anthropic
API, Bedrock, Vertex and OpenAI-compatible endpoints, so it is the whole
contract — a wider one would abstract over differences this project does not
use.

Deliberately duplicated rather than shared with the sibling repositories:
each is a standalone project a reader can clone and run, and a private
package dependency between portfolio repos would buy consistency at the cost
of that.

Swapping providers means setting `LLM_PROVIDER` — not touching
`src/commentary.py`. The forecast never calls a model at all, so nothing
about the numbers depends on this choice.

Each provider owns its own default model id. A model name is only meaningful
relative to the endpoint that serves it, so a single global default would be
wrong for whichever provider was not the one it was written for.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Completion:
    text: str
    usage: dict  # {"input_tokens": int, "output_tokens": int}


class ProviderConfigError(RuntimeError):
    """A provider was selected but the configuration it needs is missing.

    Raised at construction rather than at call time, so a misconfigured
    deployment fails on the first request with a readable message instead of
    an SDK authentication error thrown from three frames deep.
    """


class Provider(Protocol):
    name: str
    default_model: str

    def complete(self, *, system: str, user: str, model: str, max_tokens: int) -> Completion:
        ...


class AnthropicProvider:
    """The Anthropic API directly."""

    name = "anthropic"
    default_model = "claude-haiku-4-5-20251001"

    def __init__(self, api_key: str | None = None):
        from src import config as C

        # Configuration is checked before the SDK is imported, so a missing
        # key reports itself as a missing key rather than as whichever error
        # the import happens to raise first.
        key = api_key or C.ANTHROPIC_API_KEY
        if not key:
            raise ProviderConfigError(
                "LLM_PROVIDER=anthropic requires ANTHROPIC_API_KEY. "
                "Set it in .env, or switch to another provider."
            )

        # Imported here, not at module scope: verify_grounding() is the tested
        # half of the trust layer and must import without the SDK installed.
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover - depends on the install
            raise ProviderConfigError(
                "LLM_PROVIDER=anthropic requires the `anthropic` package: pip install anthropic"
            ) from exc

        self._client = anthropic.Anthropic(api_key=key)

    def complete(self, *, system: str, user: str, model: str, max_tokens: int) -> Completion:
        message = self._client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return Completion(
            text="".join(block.text for block in message.content if block.type == "text"),
            usage={
                "input_tokens": message.usage.input_tokens,
                "output_tokens": message.usage.output_tokens,
            },
        )


class BedrockProvider:
    """Amazon Bedrock through its OpenAI-compatible endpoint.

    Bedrock exposes an OpenAI-shaped API, so the official `openai` SDK is the
    client — no boto3, no SigV4 signing, no separate request/response shape to
    maintain. The only Bedrock-specific parts are the base URL (which carries
    the region) and the model id namespace.

    Credentials and endpoint are read from config rather than left to the
    SDK's own environment lookup. That matters here: the SDK would silently
    fall back to a plain OpenAI key if `OPENAI_API_KEY` happened to be set to
    one, and the run would succeed against the wrong vendor's bill. Passing
    them explicitly means a missing Bedrock configuration is an error, not a
    silent redirect.
    """

    name = "bedrock"
    #: Chosen by measurement, not by name recognition: of the models this
    #: endpoint serves, this one was the one that returned plain prose at a
    #: 1.0 grounding rate with no coherence findings. `openai.gpt-oss-120b`
    #: was the obvious first pick and is unusable here — it ignores the length
    #: and format constraints, and computes figures the prompt forbids it to
    #: compute. See docs in the README on how the comparison was run.
    default_model = "nvidia.nemotron-super-3-120b"

    #: Some models on this endpoint are slow to first token; the SDK default
    #: is short enough to time out on them before they answer.
    timeout_s = 90.0

    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        from src import config as C

        key = api_key or C.BEDROCK_API_KEY
        url = base_url or C.BEDROCK_BASE_URL
        if not key or not url:
            missing = [
                name
                for name, value in (("BEDROCK_API_KEY", key), ("BEDROCK_BASE_URL", url))
                if not value
            ]
            raise ProviderConfigError(
                f"LLM_PROVIDER=bedrock requires {' and '.join(missing)}. "
                "See .env.example — the base URL carries the region, e.g. "
                "https://bedrock-mantle.eu-central-1.api.aws/v1"
            )

        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover - depends on the install
            raise ProviderConfigError(
                "LLM_PROVIDER=bedrock requires the `openai` package: pip install openai"
            ) from exc

        self._client = OpenAI(api_key=key, base_url=url, timeout=self.timeout_s)

    def complete(self, *, system: str, user: str, model: str, max_tokens: int) -> Completion:
        import openai

        # Chat completions rather than the responses API: on this endpoint only
        # the OpenAI-namespace models accept /v1/responses, while every model it
        # serves accepts /v1/chat/completions. Using the narrower one silently
        # limits the provider to a handful of the available models.
        try:
            response = self._client.chat.completions.create(
                model=model,
                max_tokens=max_tokens,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            )
        except openai.AuthenticationError as exc:
            # Bedrock issues both short-term API keys (session-derived, valid
            # for hours) and long-term ones (IAM-backed). A short-term key
            # works when it is created and then starts returning "Signature
            # expired" — which reads like a broken integration rather than an
            # expired credential unless the message says so.
            raise ProviderConfigError(
                f"Bedrock rejected the credentials ({exc}). If the message mentions an "
                "expired signature, BEDROCK_API_KEY is a short-term key that has since "
                "lapsed — generate a long-term API key in the Bedrock console and replace it."
            ) from exc
        text = (response.choices[0].message.content or "").strip() if response.choices else ""
        if not text:
            # An empty completion is not a completion. Returning it would send
            # a paragraph with no numbers downstream, where it scores a
            # grounding rate of None and looks like a verifier problem rather
            # than a model that never answered — which is exactly how a
            # reasoning model that spent its whole budget thinking presents
            # itself.
            raise ProviderConfigError(
                f"Bedrock model {model!r} returned an empty completion. If it is a reasoning "
                "model, the token budget may have been consumed before it produced an answer; "
                "raise max_tokens or choose a model that answers directly."
            )

        usage = getattr(response, "usage", None)
        return Completion(
            text=text,
            usage={
                "input_tokens": getattr(usage, "prompt_tokens", 0) or 0,
                "output_tokens": getattr(usage, "completion_tokens", 0) or 0,
            },
        )


PROVIDERS: dict[str, type] = {
    "anthropic": AnthropicProvider,
    "bedrock": BedrockProvider,
}


def resolve_provider_name(name: str | None = None) -> str:
    """The active provider name, without constructing a client.

    Separate from get_provider() so callers that only need to know which
    provider is configured — a health endpoint, a test, a log line — do not
    have to build an SDK client and supply credentials to find out.
    """
    return (name or os.getenv("LLM_PROVIDER") or "anthropic").strip().lower()


def get_provider(name: str | None = None) -> Provider:
    """Unknown names fail loudly rather than falling back to a default the
    caller did not ask for — a silent fallback would bill the wrong account."""
    resolved = resolve_provider_name(name)
    if resolved not in PROVIDERS:
        raise ValueError(
            f"Unknown LLM_PROVIDER {resolved!r}. Available: {sorted(PROVIDERS)}. "
            "Adding one means implementing Provider.complete() in src/provider.py."
        )
    return PROVIDERS[resolved]()


def default_model_for(name: str | None = None) -> str:
    """The model id a provider uses when none is configured explicitly."""
    resolved = resolve_provider_name(name)
    if resolved not in PROVIDERS:
        raise ValueError(f"Unknown LLM_PROVIDER {resolved!r}. Available: {sorted(PROVIDERS)}.")
    return PROVIDERS[resolved].default_model
