/**
 * Fork (Custom API Edition): the custom / OpenAI-compatible provider that
 * Settings > Chat > Provider configures — the connection test against a base URL
 * (optionally with the keyring-stored key) and which agent-backend binaries
 * (OpenCode, claude-agent-acp) are present on this machine.
 */

import type { ClientTransport } from './transport'

export function createProviderEndpoints({ post, j }: ClientTransport) {
  const customProvider = {
    providerTest: (body: { url: string; api_key?: string; format?: string; use_stored?: boolean }) =>
      post('/api/provider/test', body).then(j),
    providerStatus: () => fetch('/api/provider/status').then(j),
  }

  return { customProvider }
}
