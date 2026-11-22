<script setup lang="ts">
/**
 * 启动门禁：玩家入口必须是登录页，token（localStorage 'plane-duel:vpnToken'，
 * 见 net/auth.ts）拿不到就渲染登录视图，绝不先连 WS。
 *
 * 有 token → 挂 AppShell（每次登录都是全新实例：store/socket 随挂载重建，
 * 退出与过期回登录时随卸载断开，内存态天然清空）。
 *
 * 过期链路：AppShell 上抛 expired（从未认证成功 + 重连 ≥3 次，见 net/socket.ts）
 * → 这里回登录视图并提示；刻意不清 localStorage 里的 token，成功登录时覆盖写。
 */
import { ref } from 'vue'
import Login from './views/Login.vue'
import AppShell from './AppShell.vue'
import { clearToken } from './net/auth'
import { getVpnToken } from './net/socket'

/**
 * 门禁只看一处 token 口径：getVpnToken() = localStorage（正式登录写入）
 * → VITE_VPN_TOKEN（原生壳调试兜底）。都拿不到 → 登录视图，绝不先连 WS。
 */
const loggedIn = ref(getVpnToken() !== '')
const expired = ref(false)
/** 换 key 强制重建 AppShell：登录/重登后一定拿到全新 store 与连接 */
const session = ref(0)

function onLoggedIn() {
  loggedIn.value = true
  expired.value = false
  session.value += 1
}

function onExpired() {
  // 清空内存态即"卸载 shell"；token 留到下次 login() 成功覆盖（服务端可能已换发）
  loggedIn.value = false
  expired.value = true
}

function onLogout() {
  clearToken()
  loggedIn.value = false
  expired.value = false
}
</script>

<template>
  <AppShell v-if="loggedIn" :key="session" @expired="onExpired" @logout="onLogout" />
  <Login v-else :title="expired ? '登录已过期，请重新登录' : undefined" @logged-in="onLoggedIn" />
</template>
