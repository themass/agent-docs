export type SniffProjectStatus = 'idle' | 'recording'

export type SniffProject = {
  id: string
  name: string
  /** Host or URL prefix filter, e.g. `www.bilibili.com` or `https://api.example.com` */
  origin: string
  status: SniffProjectStatus
  recordingTabId?: number
  createdAt: number
  updatedAt: number
}

export type SniffApi = {
  id: string
  projectId: string
  /** Stable grouping key: METHOD host/path/{id} */
  key: string
  method: string
  displayUrl: string
  sampleCount: number
  lastStatus?: number
  lastMimeType?: string
  /** Inferred from latest JSON response */
  outputSchema?: Record<string, unknown>
  exposed: boolean
  updatedAt: number
}

export type SniffSample = {
  id: string
  apiId: string
  projectId: string
  method: string
  url: string
  status?: number
  mimeType?: string
  resBody?: string
  ts: number
}

export type SniffStore = {
  projects: SniffProject[]
  apis: SniffApi[]
  samples: SniffSample[]
}
