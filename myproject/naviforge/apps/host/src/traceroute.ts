import { spawn } from 'node:child_process'
import { platform } from 'node:os'

const TARGET_RE = /^[a-zA-Z0-9][a-zA-Z0-9._:-]{0,252}$/

export function assertTracerouteTarget(target: string): string {
  const value = target.trim()
  if (!TARGET_RE.test(value) || value.includes('://') || value.includes('/')) {
    throw new Error('target must be a hostname or IP (no URL path)')
  }
  return value
}

export async function runSystemTraceroute(
  target: string,
  maxHops = 20,
  timeoutMs = 45_000
): Promise<{ target: string; command: string; lines: string[]; timedOut?: boolean }> {
  const host = assertTracerouteTarget(target)
  const hops = Math.min(30, Math.max(1, Math.floor(maxHops)))
  const win = platform() === 'win32'
  const command = win ? 'tracert' : 'traceroute'
  const args = win
    ? ['-d', '-h', String(hops), '-w', '2000', host]
    : ['-n', '-m', String(hops), '-w', '2', host]

  return new Promise((resolve, reject) => {
    const child = spawn(command, args, { stdio: ['ignore', 'pipe', 'pipe'] })
    const chunks: Buffer[] = []
    let timedOut = false
    const timer = setTimeout(() => {
      timedOut = true
      child.kill('SIGTERM')
    }, timeoutMs)
    child.stdout.on('data', (chunk: Buffer) => chunks.push(chunk))
    child.stderr.on('data', (chunk: Buffer) => chunks.push(chunk))
    child.on('error', (error) => {
      clearTimeout(timer)
      reject(
        new Error(
          `${command} failed to start: ${error.message}. Install traceroute (macOS/Linux) or use tracert (Windows).`
        )
      )
    })
    child.on('close', () => {
      clearTimeout(timer)
      const text = Buffer.concat(chunks).toString('utf8')
      const lines = text
        .split(/\r?\n/)
        .map((line) => line.trimEnd())
        .filter((line) => line.length > 0)
        .slice(0, 80)
      resolve({
        target: host,
        command: `${command} ${args.join(' ')}`,
        lines: lines.length ? lines : ['(no output)'],
        timedOut: timedOut || undefined,
      })
    })
  })
}
