import type { OpenAiFunctionTool } from '@naviforge/shared'

export const INTAKE_TOOL_NAMES = ['system_clarify', 'system_begin_task'] as const

export const INTAKE_OPENAI_TOOLS: OpenAiFunctionTool[] = [
  {
    type: 'function',
    function: {
      name: 'system_clarify',
      description: 'Ask the user structured clarification questions before execution.',
      parameters: {
        type: 'object',
        properties: {
          questions: {
            type: 'array',
            items: {
              type: 'object',
              properties: {
                id: { type: 'string' },
                prompt: { type: 'string' },
                kind: { type: 'string', enum: ['single', 'multi', 'text'] },
                required: { type: 'boolean' },
                defaultOptionId: { type: 'string' },
                options: {
                  type: 'array',
                  items: {
                    type: 'object',
                    properties: {
                      id: { type: 'string' },
                      label: { type: 'string' },
                      description: { type: 'string' },
                    },
                    required: ['id', 'label'],
                  },
                },
              },
              required: ['id', 'prompt', 'kind'],
            },
          },
        },
        required: ['questions'],
        additionalProperties: false,
      },
    },
  },
  {
    type: 'function',
    function: {
      name: 'system_begin_task',
      description: 'Finish intake; begin browser execution with confirmed requirements.',
      parameters: {
        type: 'object',
        properties: {
          summary: { type: 'string', description: 'Confirmed goal and assumptions' },
          assumptions: {
            type: 'array',
            items: { type: 'string' },
          },
        },
        required: ['summary'],
        additionalProperties: false,
      },
    },
  },
]
