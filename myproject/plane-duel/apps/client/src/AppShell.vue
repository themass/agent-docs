<script setup lang="ts">
/**
 * 登录后的应用外壳：连接 WS + store + 视图路由（原 App.vue 的内容）。
 * App.vue 只在有 token 时挂载本组件：每次登录（含过期重登）都是全新实例，
 * store/连接/页面状态天然清空；卸载时断开 socket。
 */
import { computed, onUnmounted, ref, watch } from 'vue'
import type { Capacity } from '@plane-duel/shared'
import Lobby from './views/Lobby.vue'
import Zone from './views/Zone.vue'
import WaitingRoom from './views/WaitingRoom.vue'
import Place from './views/Place.vue'
import DuelPlay from './views/DuelPlay.vue'
import MeleePlay from './views/MeleePlay.vue'
import ResultSheet from './components/ResultSheet.vue'
import ProfileSheet from './components/ProfileSheet.vue'
import RankListSheet from './components/RankListSheet.vue'
import CoinSheet from './components/CoinSheet.vue'
import { createGameStore } from './net/store'
import { connectSocket, defaultWsUrl, getNickname, getPlayerId } from './net/socket'
import { leaveOnRoomClosed, routeView } from './route'

const emit = defineEmits<{
  /** 登录过期（从未认证成功 + 重连触顶）：App 层清内存态并弹回登录视图 */
  expired: []
  /** 档案页点"退出登录"：App 层 clearToken 并弹回登录视图 */
  logout: []
}>()

const store = createGameStore()
const socket = connectSocket({
  url: defaultWsUrl(),
  playerId: getPlayerId(),
  nickname: getNickname,
  onExpired: () => emit('expired'),
})
socket.onMessage(store.apply)
onUnmounted(() => socket.close())

const s = store.state

/** 大厅内部的两级：专区列表 → 某个专区 */
const zone = ref<Capacity | null>(null)
/** P3/P4 弹层：个人战绩 / 段位榜 / 金币账本 */
const sheet = ref<'none' | 'profile' | 'rankList' | 'coin'>('none')

const view = computed(() => routeView(s, zone.value))

const mode = computed(() => s.game?.mode ?? 'duel')

function dismissResult() {
  store.dismissResult()
}

// 错误提示 3 秒后自动消失
let errTimer: ReturnType<typeof setTimeout> | null = null
watch(
  () => s.error,
  (e) => {
    if (errTimer) clearTimeout(errTimer)
    if (e) errTimer = setTimeout(() => (s.error = null), 3000)
  },
)

// 房间真正关闭：正在看结算页 → 留在那里（只剩"返回大厅"）；否则回大厅。
watch(
  () => s.roomClosed,
  (closed) => {
    if (!closed) return
    if (leaveOnRoomClosed(s)) {
      store.resetToLobby()
      zone.value = null
      s.error = '房间已关闭'
    }
  },
)

// 被房主踢出：回大厅（store 已复位并写好提示文案，toast 由 error watch 负责）
watch(
  () => s.kicked,
  (kicked) => {
    if (kicked) zone.value = null
  },
)

const pausedOverlay = computed(
  () => s.game !== null && s.game.phase === 'paused' && s.game.mode === 'duel',
)

const connText = computed(() => {
  switch (socket.status.value) {
    case 'connecting':
      return '正在连接服务器…'
    case 'closed':
      return '连接已断开，正在重连…'
    case 'superseded':
      return '你已在其他页面或设备上登录，本页已停止'
    default:
      return null
  }
})
</script>

<template>
  <div v-if="connText" class="conn">{{ connText }}</div>

  <Lobby
    v-if="view === 'lobby'"
    :store="store"
    :socket="socket"
    @zone="zone = $event"
    @profile="sheet = 'profile'"
    @rank-list="sheet = 'rankList'"
    @coin="sheet = 'coin'"
  />
  <Zone
    v-else-if="view === 'zone' && zone !== null"
    :store="store"
    :socket="socket"
    :capacity="zone"
    @back="zone = null"
  />
  <WaitingRoom
    v-else-if="view === 'waiting'"
    :store="store"
    :socket="socket"
    @back="zone = null"
  />
  <template v-else-if="view === 'place'">
    <Place :store="store" :socket="socket" />
  </template>
  <template v-else-if="view === 'play'">
    <DuelPlay v-if="mode === 'duel'" :store="store" :socket="socket" />
    <MeleePlay v-else :store="store" :socket="socket" />
  </template>
  <ResultSheet
    v-else-if="view === 'result'"
    :store="store"
    :socket="socket"
    @dismiss="dismissResult"
  />
  <section v-else class="placeholder">
    <p>对局进行中…</p>
  </section>

  <!-- 弹层在 v-else-if 链之外：插在链中间会把 v-else 接错（占位段会常驻） -->
  <ProfileSheet v-if="sheet === 'profile'" :store="store" @close="sheet = 'none'" @logout="emit('logout')" />
  <RankListSheet v-if="sheet === 'rankList'" :store="store" :socket="socket" @close="sheet = 'none'" />
  <CoinSheet v-if="sheet === 'coin'" :store="store" :socket="socket" @close="sheet = 'none'" />

  <!-- 暂停遮罩：摆放和对战阶段都可能暂停 -->
  <div v-if="pausedOverlay" class="overlay" role="alertdialog" aria-live="polite">
    <div class="sheet">
      <div class="radar" aria-hidden="true" />
      <p>对手已掉线，等待重连…</p>
      <p class="muted small">计时已暂停。30 秒未回则判你获胜</p>
    </div>
  </div>

  <div v-if="s.error" class="toast" role="status">{{ s.error }}</div>
</template>

<style scoped>
.conn {
  margin-bottom: 12px;
  padding: 8px 12px;
  border-radius: 8px;
  background: rgb(229 72 60 / 0.15);
  color: var(--kill);
  font-size: 13px;
  text-align: center;
}
.overlay {
  position: fixed;
  inset: 0;
  z-index: 20;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: rgb(6 12 22 / 0.72);
  backdrop-filter: blur(3px);
}
.sheet {
  width: 100%;
  max-width: 340px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 24px 20px;
  border-radius: 16px;
  background: var(--bg-raised);
  border: 1px solid var(--grid-line);
  text-align: center;
}
.sheet p {
  margin: 0;
}
.small {
  font-size: 13px;
}
.radar {
  width: 56px;
  height: 56px;
  border-radius: 50%;
  border: 1px solid var(--pending);
  background: conic-gradient(from 0deg, rgb(229 72 60 / 0.4), transparent 30%);
  animation: sweep 1.6s linear infinite;
}
@keyframes sweep {
  to {
    transform: rotate(1turn);
  }
}
.placeholder {
  padding: 48px 0;
  text-align: center;
  color: var(--ink-soft);
}
</style>
