"""Fork: how the Claude Code backend (claude-agent-acp) is authenticated.

One place decides which environment a ``claude`` session is spawned with, so
the three supported setups never step on each other:

1. **Claude subscription login** -- no ``provider_base_url``, no key. Nothing
   is injected; claude-agent-acp uses the login stored by ``claude /login``.
   Injecting *any* ambient ``ANTHROPIC_API_KEY`` here would silently move the
   user from their subscription onto per-token API billing.
2. **Anthropic API directly** -- no ``provider_base_url``, an explicit key.
   An ``sk-ant-api...`` key rides as ``ANTHROPIC_API_KEY``; a long-lived
   subscription token from ``claude setup-token`` (``sk-ant-oat...``) rides as
   ``CLAUDE_CODE_OAUTH_TOKEN``, which is how a headless gateway (Docker, a
   server) uses a Claude subscription without an interactive login.
3. **Custom endpoint** -- ``provider_base_url`` set (a router, LiteLLM, or the
   built-in shim). The key goes out as ``ANTHROPIC_API_KEY`` and, because
   Claude Code asks for its own background/subagent models by Anthropic name,
   those are all pinned to the session's model so the endpoint never sees a
   model id it does not serve.

Stdlib only: imported from the provider factory, doctor and the vision path.
"""

from __future__ import annotations

import os

#: Prefix of the long-lived OAuth token ``claude setup-token`` prints.
OAUTH_TOKEN_PREFIX = "sk-ant-oat"

#: Default port of the built-in Anthropic->OpenAI shim (``kiro_crew.shim``).
DEFAULT_SHIM_PORT = 8391

#: Claude Code env vars naming the models it uses besides the main one.
ROUTER_MODEL_ENV_VARS = (
    "ANTHROPIC_DEFAULT_OPUS_MODEL",
    "ANTHROPIC_DEFAULT_SONNET_MODEL",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL",
    "ANTHROPIC_SMALL_FAST_MODEL",
    "CLAUDE_CODE_SUBAGENT_MODEL",
)


def is_oauth_token(key: str | None) -> bool:
    """True for a Claude subscription token (``claude setup-token``)."""
    return (key or "").strip().startswith(OAUTH_TOKEN_PREFIX)


def shim_port() -> int:
    try:
        return int(os.environ.get("KIROCREW_SHIM_PORT", "") or DEFAULT_SHIM_PORT)
    except ValueError:
        return DEFAULT_SHIM_PORT


def shim_base_url() -> str:
    """Loopback URL of the built-in shim, as claude-agent-acp should dial it."""
    return f"http://127.0.0.1:{shim_port()}"


def effective_base_url(provider_base_url: str | None, *, use_shim: bool) -> str:
    """The Anthropic base URL a claude session should use ('' = Anthropic).

    An explicit ``provider_base_url`` always wins; with it empty and the shim
    switched on, the shim is the endpoint -- turning the shim on is enough,
    there is no second setting to keep in sync.
    """
    url = (provider_base_url or "").strip()
    if url:
        return url
    return shim_base_url() if use_shim else ""


def claude_env(
    *,
    base_url: str,
    api_key: str,
    model: str = "",
    existing: dict[str, str] | None = None,
) -> dict[str, str]:
    """Env additions for a claude-agent-acp spawn. Never overrides *existing*.

    *api_key* must be the key the user configured for Kiro Crew (config,
    keyring or ``KIROCREW_PROVIDER_API_KEY``), never an ambient
    ``ANTHROPIC_API_KEY`` picked up from the gateway's own environment -- see
    the module docstring for why.
    """
    have = existing or {}
    out: dict[str, str] = {}
    key = (api_key or "").strip()
    if base_url:
        if not have.get("ANTHROPIC_BASE_URL"):
            out["ANTHROPIC_BASE_URL"] = base_url
        if key and not have.get("ANTHROPIC_API_KEY"):
            out["ANTHROPIC_API_KEY"] = key
        pinned = (model or "").strip()
        if pinned and pinned != "auto":
            for var in ROUTER_MODEL_ENV_VARS:
                if not have.get(var):
                    out[var] = pinned
    elif key:
        if is_oauth_token(key):
            if not have.get("CLAUDE_CODE_OAUTH_TOKEN"):
                out["CLAUDE_CODE_OAUTH_TOKEN"] = key
        elif not have.get("ANTHROPIC_API_KEY"):
            out["ANTHROPIC_API_KEY"] = key
    return out


def auth_mode(*, base_url: str, api_key: str) -> str:
    """Short label for doctor / the settings page."""
    if base_url:
        return "custom endpoint"
    if is_oauth_token(api_key):
        return "Claude subscription (setup-token)"
    if (api_key or "").strip():
        return "Anthropic API key"
    return "Claude subscription (claude /login)"
