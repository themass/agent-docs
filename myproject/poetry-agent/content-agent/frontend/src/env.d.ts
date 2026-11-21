/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** agent-bff 地址，默认 http://localhost:8100。前端不持有任何令牌。 */
  readonly VITE_AGENT_BFF_URL?: string;
}
