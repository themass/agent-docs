#!/usr/bin/env node
/**
 * Chrome native-messaging host. Speaks length-prefixed JSON on stdin.
 * Ensures the HTTP helper is up, then returns { url, token, workspaceRoot }.
 */
import { spawn } from 'node:child_process'
import { readSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const PORT = Number(process.env.NAVIFORGE_HOST_PORT ?? 17373)
const BOOTSTRAP = `http://127.0.0.1:${PORT}/local/bootstrap`

type Bootstrap = { ok: boolean; url: string; token: string; workspaceRoot: string }

function writeNative(value: unknown): void {
  const json = Buffer.from(JSON.stringify(value))
  const header = Buffer.alloc(4)
  header.writeUInt32LE(json.length, 0)
  process.stdout.write(header)
  process.stdout.write(json)
}

function readNative(): unknown | null {
  const header = Buffer.alloc(4)
  const n = readSync(0, header, 0, 4, null)
  if (n < 4) return null
  const len = header.readUInt32LE(0)
  if (len <= 0 || len > 1_000_000) return null
  const body = Buffer.alloc(len)
  let off = 0
  while (off < len) {
    const got = readSync(0, body, off, len - off, null)
    if (got <= 0) return null
    off += got
  }
  return JSON.parse(body.toString('utf8'))
}

async function bootstrap(): Promise<Bootstrap | null> {
  try {
    const response = await fetch(BOOTSTRAP)
    if (!response.ok) return null
    return (await response.json()) as Bootstrap
  } catch {
    return null
  }
}

async function ensureHttp(): Promise<Bootstrap> {
  const existing = await bootstrap()
  if (existing?.ok) return existing
  const here = path.dirname(fileURLToPath(import.meta.url))
  const child = spawn(process.execPath, [path.join(here, 'index.js')], {
    detached: true,
    stdio: 'ignore',
    env: { ...process.env, NAVIFORGE_HOST_HTTP_ONLY: '1' },
  })
  child.unref()
  for (let i = 0; i < 20; i++) {
    await new Promise((resolve) => setTimeout(resolve, 150))
    const ready = await bootstrap()
    if (ready?.ok) return ready
  }
  throw new Error('local helper failed to start')
}

async function main(): Promise<void> {
  readNative()
  const info = await ensureHttp()
  writeNative({ url: info.url, token: info.token, workspaceRoot: info.workspaceRoot })
}

main().catch((error: unknown) => {
  writeNative({ error: (error as Error).message })
  process.exitCode = 1
})
