import type { ReactNode } from 'react'

import { prettyJson, type McpConnection } from '@naviforge/shared'

type Props = {
  connection: McpConnection
  labels: {
    title: string
    tools: string
    resources: string
    prompts: string
    qualified: string
    empty: string
    checkedAt: string
  }
}

function DiscoverySection({
  title,
  count,
  empty,
  children,
}: {
  title: string
  count: number
  empty: string
  children: ReactNode
}): React.ReactElement {
  return (
    <details className="mcp-discovery-section" open={count > 0}>
      <summary>
        <strong>{title}</strong> <span className="muted">({count})</span>
      </summary>
      {count ? children : <p className="muted">{empty}</p>}
    </details>
  )
}

export function McpDiscoveryPanel({ connection, labels }: Props): React.ReactElement | null {
  if (!connection.checkedAt) return null
  const tools = connection.discoveredTools ?? []
  const resources = connection.discoveredResources ?? []
  const prompts = connection.discoveredPrompts ?? []
  const when = new Date(connection.checkedAt).toLocaleString()

  const toolRows = tools.map((tool) => ({
    qualifiedName: `mcp__${connection.id}__${tool.name}`,
    name: tool.name,
    description: tool.description,
    inputSchema: tool.inputSchema,
  }))

  return (
    <div className="mcp-discovery">
      <div className="section-heading compact">
        <span>{labels.title}</span>
        <small className="muted">{labels.checkedAt.replace('{time}', when)}</small>
      </div>
      <DiscoverySection title={labels.tools} count={tools.length} empty={labels.empty}>
        <pre className="mcp-discovery-json">{prettyJson(toolRows)}</pre>
        <p className="muted">{labels.qualified}</p>
      </DiscoverySection>
      <DiscoverySection title={labels.resources} count={resources.length} empty={labels.empty}>
        <pre className="mcp-discovery-json">{prettyJson(resources)}</pre>
      </DiscoverySection>
      <DiscoverySection title={labels.prompts} count={prompts.length} empty={labels.empty}>
        <pre className="mcp-discovery-json">{prettyJson(prompts)}</pre>
      </DiscoverySection>
    </div>
  )
}
