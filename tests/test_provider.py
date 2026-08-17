"""The provider layer: selection, configuration, and failure modes.

No API calls. Every test here either inspects the registry or constructs a
client with deliberately absent configuration, so the suite runs in CI and
costs nothing.

These exist because the abstraction previously had exactly one implementation
behind it, which meant "the provider is configuration" was a claim in a
docstring rather than a property of the code. A registry with one entry cannot
demonstrate portability.
"""

from __future__ import annotations

import pytest

from src import commentary
from src import config as C
from src import provider as P


def test_both_providers_are_registered():
    assert set(P.PROVIDERS) == {"anthropic", "bedrock"}


def test_each_provider_names_its_own_default_model():
    """A model id is only meaningful relative to the endpoint serving it, so a
    single shared default would be wrong for one of the two."""
    anthropic_model = P.PROVIDERS["anthropic"].default_model
    bedrock_model = P.PROVIDERS["bedrock"].default_model
    assert anthropic_model != bedrock_model
    assert "claude" in anthropic_model
    assert "/" not in bedrock_model  # a Bedrock model id, not an OpenAI-hosted path


def test_provider_is_resolved_from_the_environment(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "bedrock")
    assert P.resolve_provider_name() == "bedrock"
    monkeypatch.setenv("LLM_PROVIDER", "  ANTHROPIC  ")
    assert P.resolve_provider_name() == "anthropic"


def test_provider_defaults_to_anthropic_when_unset(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    assert P.resolve_provider_name() == "anthropic"


def test_an_explicit_argument_beats_the_environment(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    assert P.resolve_provider_name("bedrock") == "bedrock"


def test_unknown_provider_fails_loudly(monkeypatch):
    """A silent fallback would bill the wrong account."""
    monkeypatch.setenv("LLM_PROVIDER", "vertex")
    with pytest.raises(ValueError, match="Unknown LLM_PROVIDER"):
        P.get_provider()


def test_default_model_lookup_rejects_unknown_providers():
    with pytest.raises(ValueError, match="Unknown LLM_PROVIDER"):
        P.default_model_for("azure")


# --------------------------------------------------------------- configuration
def test_bedrock_without_configuration_names_what_is_missing(monkeypatch):
    monkeypatch.setattr(C, "BEDROCK_API_KEY", "")
    monkeypatch.setattr(C, "BEDROCK_BASE_URL", "")
    with pytest.raises(P.ProviderConfigError) as exc:
        P.BedrockProvider()
    message = str(exc.value)
    assert "BEDROCK_API_KEY" in message and "BEDROCK_BASE_URL" in message


def test_bedrock_missing_only_the_url_says_only_that(monkeypatch):
    monkeypatch.setattr(C, "BEDROCK_API_KEY", "sk-not-a-real-key")
    monkeypatch.setattr(C, "BEDROCK_BASE_URL", "")
    with pytest.raises(P.ProviderConfigError) as exc:
        P.BedrockProvider()
    assert "BEDROCK_BASE_URL" in str(exc.value)
    assert "BEDROCK_API_KEY" not in str(exc.value)


def test_anthropic_without_a_key_fails_at_construction(monkeypatch):
    """At construction, not at call time: a misconfigured deployment should
    fail with a readable message, not an SDK auth error three frames deep."""
    monkeypatch.setattr(C, "ANTHROPIC_API_KEY", "")
    with pytest.raises(P.ProviderConfigError, match="ANTHROPIC_API_KEY"):
        P.AnthropicProvider()


def test_bedrock_client_targets_the_configured_endpoint(monkeypatch):
    """The endpoint comes from config, not from the SDK's own environment
    lookup — otherwise a stray OPENAI_API_KEY would silently redirect the run
    to a different vendor."""
    monkeypatch.setattr(C, "BEDROCK_API_KEY", "sk-not-a-real-key")
    monkeypatch.setattr(C, "BEDROCK_BASE_URL", "https://example.invalid/v1")
    client = P.BedrockProvider()._client
    assert str(client.base_url).rstrip("/") == "https://example.invalid/v1"


def test_expired_bedrock_key_is_reported_as_a_credential_problem(monkeypatch):
    """A short-term Bedrock key works when created and then starts failing.
    Surfacing that as a raw SDK traceback makes an expired credential look
    like a broken integration."""
    import httpx
    import openai

    monkeypatch.setattr(C, "BEDROCK_API_KEY", "sk-not-a-real-key")
    monkeypatch.setattr(C, "BEDROCK_BASE_URL", "https://example.invalid/v1")
    bedrock = P.BedrockProvider()

    class _Expired:
        def create(self, **kwargs):
            raise openai.AuthenticationError(
                "Signature expired",
                response=httpx.Response(
                    401, request=httpx.Request("POST", "https://example.invalid/v1/responses")
                ),
                body=None,
            )

    monkeypatch.setattr(bedrock._client.chat, "completions", _Expired())

    with pytest.raises(P.ProviderConfigError, match="short-term key"):
        bedrock.complete(system="s", user="u", model="m", max_tokens=10)


# ------------------------------------------------------------------- wiring
class _RecordingProvider:
    """Captures what commentary.write() asks for, without calling anything."""

    name = "recording"
    default_model = "provider-default-model"

    def __init__(self):
        self.calls = []

    def complete(self, *, system, user, model, max_tokens):
        self.calls.append({"model": model, "max_tokens": max_tokens})
        return P.Completion(text="Revenue was 24811.0.", usage={"input_tokens": 1, "output_tokens": 1})


def _fixed_result() -> dict:
    return {"actual": {"revenue": 24811.0}, "driver_based": {"revenue": 25585.2}}


def test_commentary_falls_back_to_the_provider_default_model(monkeypatch):
    recording = _RecordingProvider()
    monkeypatch.setattr(P, "get_provider", lambda *a, **k: recording)
    monkeypatch.setattr(C, "COMMENTARY_MODEL", "")

    _, _, provenance = commentary.write(_fixed_result())

    assert recording.calls[0]["model"] == "provider-default-model"
    assert provenance["model"] == "provider-default-model"
    assert provenance["provider"] == "recording"


def test_an_explicit_model_overrides_the_provider_default(monkeypatch):
    recording = _RecordingProvider()
    monkeypatch.setattr(P, "get_provider", lambda *a, **k: recording)
    monkeypatch.setattr(C, "COMMENTARY_MODEL", "explicitly-configured-model")

    _, _, provenance = commentary.write(_fixed_result())

    assert recording.calls[0]["model"] == "explicitly-configured-model"
    assert provenance["model"] == "explicitly-configured-model"


def test_commentary_records_which_vendor_wrote_it(monkeypatch):
    """Stored commentary without provenance is prose nobody can attribute —
    which is how a pipeline can appear to run on one vendor while billing
    another."""
    recording = _RecordingProvider()
    monkeypatch.setattr(P, "get_provider", lambda *a, **k: recording)
    monkeypatch.setattr(C, "COMMENTARY_MODEL", "")

    _, _, provenance = commentary.write(_fixed_result())

    assert set(provenance) == {"provider", "model", "usage"}
    assert provenance["usage"] == {"input_tokens": 1, "output_tokens": 1}
