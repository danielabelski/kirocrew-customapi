import { describe, expect, it } from 'vitest'
import { CLAUDE_DIRECT_PRESETS, PROVIDER_PRESETS, savedClaudePreset } from '../pages/settings/providerPresets'

describe('Claude Code provider presets', () => {
  it('offers the subscription login first, with no URL and no key', () => {
    const first = PROVIDER_PRESETS.claude_code[0]
    expect(first.value).toBe('claude-login')
    expect(first.url).toBe('')
    expect(first.keyRequired).toBeFalsy()
  })

  it('treats both direct presets as URL-less', () => {
    for (const value of CLAUDE_DIRECT_PRESETS) {
      expect(PROVIDER_PRESETS.claude_code.find(p => p.value === value)?.url).toBe('')
    }
  })

  it('tells the empty-URL presets apart by the stored key', () => {
    expect(savedClaudePreset('', false)).toBe('claude-login')
    expect(savedClaudePreset('', true)).toBe('anthropic-key')
  })

  it('maps a saved router URL back to its preset, else custom', () => {
    expect(savedClaudePreset('http://localhost:8317/', true)).toBe('cli-proxy-api')
    expect(savedClaudePreset('https://my-router.example', false)).toBe('custom')
  })
})
