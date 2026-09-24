#!/usr/bin/env node
/** One-shot: create ~/NaviForge, write LaunchAgent, start the HTTP helper. */
import { spawn } from 'node:child_process'
import { chmod, mkdir, writeFile } from 'node:fs/promises'
import { homedir } from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { defaultWorkspaceRoot, ensureWorkspace, registerNativeHost, resolveHostToken } from './workspace.js'

const LABEL = 'com.naviforge.host'
const PORT = Number(process.env.NAVIFORGE_HOST_PORT ?? 17373)

function run(cmd: string, args: string[]): Promise<void> {
  return new Promise((resolve, reject) => {
    const child = spawn(cmd, args, { stdio: 'inherit' })
    child.on('error', reject)
    child.on('exit', (code) => {
      if (code === 0) resolve()
      else resolve()
    })
  })
}

async function main(): Promise<void> {
  const root = defaultWorkspaceRoot()
  await ensureWorkspace(root)
  const token = await resolveHostToken(root, process.env.NAVIFORGE_HOST_TOKEN)
  const here = path.dirname(fileURLToPath(import.meta.url))
  const hostJs = path.join(here, 'index.js')
  const nativeJs = path.join(here, 'native-host.js')
  const binDir = path.join(root, 'bin')
  await mkdir(binDir, { recursive: true })
  const wrapper = path.join(binDir, 'naviforge-host')
  const nativeWrapper = path.join(binDir, 'naviforge-native-host')
  await writeFile(
    wrapper,
    `#!/bin/sh\nexport NAVIFORGE_HOST_HTTP_ONLY=1\nexport NAVIFORGE_WORKSPACE=${JSON.stringify(root)}\nexec ${JSON.stringify(process.execPath)} ${JSON.stringify(hostJs)}\n`
  )
  await writeFile(
    nativeWrapper,
    `#!/bin/sh\nexport NAVIFORGE_HOST_HTTP_ONLY=1\nexport NAVIFORGE_WORKSPACE=${JSON.stringify(root)}\nexec ${JSON.stringify(process.execPath)} ${JSON.stringify(nativeJs)}\n`
  )
  await chmod(wrapper, 0o755)
  await chmod(nativeWrapper, 0o755)

  if (process.platform === 'darwin') {
    const agents = path.join(homedir(), 'Library', 'LaunchAgents')
    await mkdir(agents, { recursive: true })
    const plistPath = path.join(agents, `${LABEL}.plist`)
    const plist = `<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>${LABEL}</string>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>ProgramArguments</key>
  <array>
    <string>${wrapper}</string>
  </array>
  <key>StandardOutPath</key><string>${path.join(root, 'logs', 'host.out.log')}</string>
  <key>StandardErrorPath</key><string>${path.join(root, 'logs', 'host.err.log')}</string>
</dict>
</plist>
`
    await writeFile(plistPath, plist)
    await run('launchctl', ['bootout', `gui/${process.getuid?.() ?? 501}`, plistPath])
    await run('launchctl', ['bootstrap', `gui/${process.getuid?.() ?? 501}`, plistPath])
    await run('launchctl', ['kickstart', '-k', `gui/${process.getuid?.() ?? 501}/${LABEL}`])
  }

  const extensionId = process.argv.find((arg) => arg.startsWith('--extension-id='))?.slice(15)
  if (extensionId) {
    await registerNativeHost(root, extensionId)
  }

  console.log(`NaviForge workspace: ${root}`)
  console.log(`Helper URL: http://127.0.0.1:${PORT}`)
  console.log(`Token file: ${path.join(root, '.host-token')} (${token.slice(0, 6)}…)`)
  if (!extensionId) {
    console.log('Native messaging: the extension will register its own id on first helper connect.')
  }
}

main().catch((error: unknown) => {
  console.error((error as Error).message)
  process.exitCode = 1
})
