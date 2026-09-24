import { registerStubProvider } from '../stub-provider.js'

registerStubProvider({
  id: 'codex',
  label: 'Codex',
  description: 'OpenAI Codex / ChatGPT 编码额度',
})
registerStubProvider({
  id: 'anthropic',
  label: 'Claude',
  description: 'Anthropic Claude / Claude Code 用量',
})
registerStubProvider({
  id: 'antigravity',
  label: 'Antigravity',
  description: 'Google Antigravity AI Credits',
})
registerStubProvider({
  id: 'newapi',
  label: 'NaviForge 托管',
  description: 'NewAPI 插件额度',
})
