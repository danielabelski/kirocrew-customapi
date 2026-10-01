# Using Claude and Claude Code (Custom API Edition)

Kiro Crew runs its agents through an ACP harness. Besides the default
`kiro-cli`, the **Claude Code** harness (`claude-agent-acp`, backend `claude`)
drives Anthropic's Claude Code agent. This fork makes it work in four setups,
all from **Settings → Chat → Provider** (backend **Claude Code**) or
`config.json`.

| Setup | Base URL | API key | What happens |
|---|---|---|---|
| **Claude subscription** (Pro / Max) | empty | empty | Uses the login from `claude /login` on the gateway machine. Nothing is injected, so the subscription is never switched to API billing. |
| **Claude subscription, headless** (Docker, server) | empty | `sk-ant-oat…` from `claude setup-token` | Passed as `CLAUDE_CODE_OAUTH_TOKEN`, so no interactive login is needed. |
| **Anthropic API** | empty | `sk-ant-api…` | Passed as `ANTHROPIC_API_KEY`, billed per token. |
| **Custom endpoint** (router, LiteLLM, OpenRouter, 9router, CLIProxyAPI …) | the router URL | the router's key | Passed as `ANTHROPIC_BASE_URL` / `ANTHROPIC_API_KEY`; Claude Code's background and subagent models are pinned to the chat model so the router never sees a model id it does not serve. |
| **Any OpenAI-compatible model** (Ollama, vLLM, llama.cpp, DeepSeek …) via the built-in shim | empty, shim on | optional | See [below](#openai-compatible-models-through-the-built-in-shim). |

## Prerequisites

Claude Code's ACP adapter must be installed where the gateway runs:

```bash
npm i -g @agentclientprotocol/claude-agent-acp
```

`kirocrew doctor` reports whether it was found, and which of the setups above
is active (`claude auth: …`).

## Selecting the backend

In the dashboard pick **Claude Code** under Settings → Chat → Provider, choose a
preset and save. Or in `~/.kiro/crew/config.json`:

```json
{
  "agent": {
    "acp_backend": "claude"
  }
}
```

`"agent": {"provider": "claude_code"}` (the fork's older spelling) still works
and pins the Claude Code backend for every session.

## Keys: where they are stored

The key is resolved in this order, the same everywhere:

1. `KIROCREW_PROVIDER_API_KEY` environment variable,
2. the OS keyring (`kirocrew secret set <KEY>`, or `kirocrew secret migrate` to move a plaintext key),
3. `agent.provider_api_key` in `config.json` (plaintext; `doctor` warns).

An `ANTHROPIC_API_KEY` that happens to be set in the gateway's own environment
is **not** forwarded unless a custom base URL is configured, so it cannot
silently replace a subscription login.

## OpenAI-compatible models through the built-in shim

The shim is a small loopback proxy inside the gateway that speaks the Anthropic
Messages API to Claude Code and OpenAI chat completions to your model server
(tools, streaming, images and token counting included).

```json
{
  "agent": {
    "acp_backend": "claude",
    "use_shim": true,
    "shim_openai_base_url": "http://localhost:11434/v1",
    "shim_openai_api_key": "",
    "model": "qwen3-coder"
  }
}
```

With `use_shim` on and `provider_base_url` empty, Claude Code is pointed at the
shim automatically (`http://127.0.0.1:8391`; change the port with
`KIROCREW_SHIM_PORT`). The shim starts with the gateway, so restart the gateway
after changing its settings. `shim_openai_api_key` is the key of the model
server; when empty, the provider key is used.

Not translated: extended thinking blocks and Anthropic server-side tools.

## Troubleshooting

- **`kirocrew doctor`** prints the active Claude auth mode, the key source, and
  probes a custom endpoint.
- **401 on the subscription setup**: run `claude /login` as the same user the
  gateway runs as, or use `claude setup-token`.
- **"model not found" from a router**: pick a model id the router serves (the
  picker lists what the router advertises) instead of `auto`.
- **`safe_mode`** refuses public endpoints; turn it off to use a hosted router.
