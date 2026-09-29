"""Fork: Claude Code backend auth wiring (kiro_crew.claude_auth) and the shim
request/response translation details Claude Code depends on."""

from __future__ import annotations

import pytest

from kiro_crew import claude_auth
from kiro_crew.claude_auth import ROUTER_MODEL_ENV_VARS, claude_env, effective_base_url
from kiro_crew.shim import anthropic_to_openai, openai_to_anthropic


# ── claude_env ───────────────────────────────────────────────────────────


def test_subscription_login_injects_nothing() -> None:
    assert claude_env(base_url="", api_key="") == {}


def test_direct_api_key_rides_as_anthropic_api_key() -> None:
    env = claude_env(base_url="", api_key="sk-ant-api03-abc")
    assert env == {"ANTHROPIC_API_KEY": "sk-ant-api03-abc"}


def test_setup_token_rides_as_oauth_token_not_api_key() -> None:
    env = claude_env(base_url="", api_key="sk-ant-oat01-xyz")
    assert env == {"CLAUDE_CODE_OAUTH_TOKEN": "sk-ant-oat01-xyz"}


def test_custom_endpoint_pins_every_background_model() -> None:
    env = claude_env(base_url="http://127.0.0.1:8391", api_key="k", model="qwen3-coder")
    assert env["ANTHROPIC_BASE_URL"] == "http://127.0.0.1:8391"
    assert env["ANTHROPIC_API_KEY"] == "k"
    for var in ROUTER_MODEL_ENV_VARS:
        assert env[var] == "qwen3-coder"


def test_custom_endpoint_with_auto_model_pins_nothing() -> None:
    env = claude_env(base_url="http://r", api_key="", model="auto")
    assert env == {"ANTHROPIC_BASE_URL": "http://r"}


def test_existing_env_is_never_overridden() -> None:
    existing = {"ANTHROPIC_API_KEY": "mine", "ANTHROPIC_SMALL_FAST_MODEL": "tiny"}
    env = claude_env(base_url="http://r", api_key="k", model="m", existing=existing)
    assert "ANTHROPIC_API_KEY" not in env
    assert "ANTHROPIC_SMALL_FAST_MODEL" not in env
    assert env["ANTHROPIC_DEFAULT_HAIKU_MODEL"] == "m"


def test_effective_base_url_prefers_explicit_then_shim(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("KIROCREW_SHIM_PORT", raising=False)
    assert effective_base_url("https://r.example", use_shim=True) == "https://r.example"
    assert effective_base_url("", use_shim=True) == "http://127.0.0.1:8391"
    assert effective_base_url("", use_shim=False) == ""
    monkeypatch.setenv("KIROCREW_SHIM_PORT", "9000")
    assert effective_base_url(" ", use_shim=True) == "http://127.0.0.1:9000"
    monkeypatch.setenv("KIROCREW_SHIM_PORT", "junk")
    assert claude_auth.shim_port() == claude_auth.DEFAULT_SHIM_PORT


def test_auth_mode_labels() -> None:
    assert claude_auth.auth_mode(base_url="", api_key="") == "Claude subscription (claude /login)"
    assert claude_auth.auth_mode(base_url="", api_key="sk-ant-oat01-x").startswith(
        "Claude subscription (setup-token)"
    )
    assert claude_auth.auth_mode(base_url="", api_key="sk-ant-api03-x") == "Anthropic API key"
    assert claude_auth.auth_mode(base_url="http://r", api_key="") == "custom endpoint"


# ── provider factory wiring ──────────────────────────────────────────────


def _claude_env_for(monkeypatch: pytest.MonkeyPatch, **agent_fields: object) -> dict[str, str]:
    """extra_env the REAL provider factory hands a claude session."""
    from kiro_crew.config.loader import KiroCrewConfig

    captured: dict[str, object] = {}

    class _FakeProvider:
        def __init__(self, **kwargs: object) -> None:
            captured.update(kwargs)

    monkeypatch.setattr("kiro_crew.providers.acp.AcpProvider", _FakeProvider, raising=True)
    monkeypatch.delenv("KIROCREW_PROVIDER_API_KEY", raising=False)
    monkeypatch.delenv("KIROCREW_SHIM_PORT", raising=False)
    monkeypatch.setattr(
        "kiro_crew.provider_secrets.load_provider_key", lambda: "", raising=True
    )
    cfg = KiroCrewConfig()
    cfg.agent.acp_backend = "claude"
    for name, value in agent_fields.items():
        setattr(cfg.agent, name, value)
    cfg.create_provider_factory()(session_key="test:claude", agent="")
    return dict(captured.get("extra_env") or {})


def test_factory_subscription_login_ignores_ambient_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "ambient")
    monkeypatch.setenv("CLIPROXY_API_KEY", "router")
    try:
        env = _claude_env_for(monkeypatch)
    except TypeError as exc:  # factory signature drift: surface clearly
        pytest.fail(f"create_provider signature changed: {exc}")
    assert "ANTHROPIC_API_KEY" not in env
    assert "ANTHROPIC_BASE_URL" not in env


def test_factory_shim_switch_points_claude_at_the_shim(monkeypatch: pytest.MonkeyPatch) -> None:
    env = _claude_env_for(monkeypatch, use_shim=True, model="qwen3-coder")
    assert env["ANTHROPIC_BASE_URL"] == "http://127.0.0.1:8391"
    assert env["ANTHROPIC_DEFAULT_HAIKU_MODEL"] == "qwen3-coder"


# ── shim translation ─────────────────────────────────────────────────────


def test_shim_maps_tool_choice_stop_and_top_p() -> None:
    out = anthropic_to_openai(
        {
            "model": "m",
            "max_tokens": 10,
            "top_p": 0.9,
            "stop_sequences": ["a", "b", "c", "d", "e"],
            "tool_choice": {"type": "tool", "name": "Read"},
            "messages": [{"role": "user", "content": "hi"}],
        }
    )
    assert out["top_p"] == 0.9
    assert out["stop"] == ["a", "b", "c", "d"]
    assert out["tool_choice"] == {"type": "function", "function": {"name": "Read"}}
    assert anthropic_to_openai({"tool_choice": {"type": "any"}, "messages": []})[
        "tool_choice"
    ] == "required"
    assert "tool_choice" not in anthropic_to_openai(
        {"tool_choice": {"type": "auto"}, "messages": []}
    )


def test_shim_keeps_tool_error_signal() -> None:
    out = anthropic_to_openai(
        {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "tool_result", "tool_use_id": "t1", "content": "boom", "is_error": True}
                    ],
                }
            ]
        }
    )
    assert out["messages"] == [{"role": "tool", "tool_call_id": "t1", "content": "[tool error] boom"}]


def test_shim_non_stream_response_is_an_anthropic_message() -> None:
    out = openai_to_anthropic(
        {"id": "x", "choices": [{"message": {"content": "hi"}, "finish_reason": "stop"}]}, "m"
    )
    assert out["type"] == "message"
    assert out["stop_reason"] == "end_turn"
