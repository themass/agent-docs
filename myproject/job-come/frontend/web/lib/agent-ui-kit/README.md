# agent-ui-kit

Portable React UI for agent **conversation** (thread + queue + composer). Copy this folder into a Next/Vite + Tailwind app.

## Entry point

**`AgentConversation`** — pass `state`, `events`, `labels`, `chrome`, `items`.

```tsx
<AgentConversation
  labels={myLabels}
  chrome={{ renderAgentIcon: (p) => <MyIcon {...p} /> }}
  state={viewState}
  events={handlers}
  items={streamItems}
/>
```

Types: `AgentConversationProps`, `AgentConversationViewState`, `AgentConversationEvents`, `AgentConversationChrome`, `AgentUiDisplayItem`.

Lower-level exports: `AgentInputDock`, `AgentMessageQueue`, `AgentComposer`, `AgentConversationThread`, `AgentThinkingIndicator`, `AgentAvatarMark`.

## Tailwind

Add `agent-think` keyframe (see existing `tailwind.config.ts` in JobCome web).

## JobCome

- `lib/agent/jobcome-conversation-labels.ts` — copy
- `components/agent/AgentConversation.tsx` — wires `useAgentSession` + `AgentMark`
- `components/agent/AgentMark.tsx` — brand initials
