<script setup lang="ts">
/**
 * 结算页（spec §19.9）：排名列表 + 再来一局 / 返回大厅。
 * 对局中离开的人不在这里——他们没打完，服务器直接把他们踢出对局。
 */
import { computed, watch } from 'vue'
import { COIN_REASON_LABELS, TIERS, type GameResult } from '@plane-duel/shared'
import { fx, haptics } from '../fx/fx'
import type { GameStore } from '../net/store'
import type { SocketHandle } from '../net/socket'

const props = defineProps<{ store: GameStore; socket: SocketHandle }>()
const emit = defineEmits<{ dismiss: [] }>()
const s = props.store.state

const result = computed<GameResult | null>(() => s.table?.lastResult ?? null)
const myRank = computed(() => result.value?.ranking.find((r) => r.playerId === s.playerId)?.rank ?? null)
const total = computed(() => result.value?.ranking.length ?? 0)
const botIds = computed(() => new Set(s.table?.lastResult?.botIds ?? []))
const withBots = computed(() => botIds.value.size > 0)

// P6 手感：结算弹层出现的一刻播胜负音 + 震动（本组件挂载即 result 已在）
watch(
  result,
  (r) => {
    if (r === null) return
    const win = r.ranking.find((x) => x.playerId === s.playerId)?.rank === 1
    fx.play(win ? 'win' : 'lose')
    haptics.vibrate(win ? 'win' : 'lose')
  },
  { immediate: true },
)

const seatOf = (playerId: string): number => s.table!.seats.findIndex((x) => x?.playerId === playerId)
const nickOf = (playerId: string): string => {
  const nick = s.table!.seats.find((x) => x?.playerId === playerId)?.nickname ?? '玩家'
  return botIds.value.has(playerId) ? `🤖 ${nick}` : nick
}

// P4 金币行：coinFlash 由 coinsChanged 写入、新一局 tableState 清除
const coinFlash = computed(() => s.coinFlash)
const coinNote = computed(() => {
  const f = coinFlash.value
  if (!f) return null
  return `金币 ${f.delta > 0 ? '+' : ''}${f.delta} · ${COIN_REASON_LABELS[f.reason]}`
})

/** 出局轮次为空时：只有第 1 名才是"存活"（对决的输家也没有出局轮次，但并非存活） */
function roundText(r: { rank: number; eliminatedRound: number | null }): string {
  if (r.eliminatedRound !== null) return `第 ${r.eliminatedRound} 轮`
  return r.rank === 1 ? '存活' : '—'
}

function reasonText(): string {
  if (!result.value) return ''
  switch (result.value.reason) {
    case 'head':
      return '机头被击中'
    case 'allPlanes':
      return '全部飞机被击落'
    case 'forfeit':
      return '对手掉线或中途离开'
    case 'lastStanding':
      return '最后存活'
  }
}

function rematch() {
  props.socket.send({ type: 'setReady', ready: true, rulesVersion: props.store.state.table?.rulesVersion ?? 0 })
}

function leave() {
  if (!s.roomClosed) props.socket.send({ type: 'leaveRoom' })
  props.store.resetToLobby()
}
</script>

<template>
  <div v-if="result" class="overlay" role="dialog" aria-live="polite">
    <div class="sheet">
      <h2 :class="myRank === 1 ? 'win' : 'lose'">
        {{ myRank === 1 ? '胜利' : `第 ${myRank} 名` }}
      </h2>
      <p class="muted">{{ reasonText() }} · {{ total }} 人</p>

      <ol class="ranking">
        <li v-for="r in result.ranking" :key="r.playerId" :class="{ me: r.playerId === s.playerId }">
          <span class="rank">{{ r.rank }}</span>
          <span class="dot" :style="{ '--seat': ['#22d3ee', '#6d9cfe', '#eaacf8', '#ff9e55'][seatOf(r.playerId) >= 0 ? seatOf(r.playerId) : 0] }" aria-hidden="true" />
          <span class="nick">{{ nickOf(r.playerId) }}</span>
          <span class="stat muted">{{ roundText(r) }} · 命中 {{ r.hits }}</span>
        </li>
      </ol>

      <p v-if="withBots" class="bots-note muted">本局有电脑参与，不计段位</p>
      <p v-else-if="store.state.rankFlash" class="rank-note" :class="store.state.rankFlash.delta > 0 ? 'up' : store.state.rankFlash.delta < 0 ? 'down' : ''">
        {{
          store.state.rankFlash.delta > 0
            ? `段位 +1 星 · ${TIERS[store.state.rankFlash.tier]} ${store.state.rankFlash.stars}★`
            : store.state.rankFlash.delta < 0
              ? `段位 −1 星 · ${TIERS[store.state.rankFlash.tier]} ${store.state.rankFlash.stars}★`
              : '保星成功（连败保护或垫底保护）'
        }}
      </p>
      <!-- P4：金币行（完成局 +5 / 门票奖励 / 门票退款）；票费在排队时就扣了，这里只报"这局挣了多少" -->
      <p v-if="coinNote" class="coin-note" :class="coinFlash && coinFlash.delta > 0 ? 'up' : 'down'">{{ coinNote }}</p>

      <button v-if="!s.roomClosed" class="btn primary" @click="rematch">再来一局</button>
      <button v-if="!s.roomClosed" class="btn ghost" @click="emit('dismiss')">查看等候室</button>
      <button class="btn" :class="s.roomClosed ? 'primary' : 'ghost'" @click="leave">返回大厅</button>
    </div>
  </div>
</template>

<style scoped>
.overlay {
  position: fixed;
  inset: 0;
  z-index: 20;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  background: rgb(4 8 18 / 0.72);
  backdrop-filter: blur(3px);
  animation: sheet-fade 200ms ease-out;
}
.sheet {
  width: 100%;
  max-width: 360px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 22px 18px;
  border-radius: 16px;
  background: var(--bg-raised);
  border: 1px solid var(--grid-line);
  text-align: center;
  animation: sheet-rise 260ms cubic-bezier(0.2, 1.2, 0.4, 1);
  box-shadow: var(--shadow);
}
/* P6 手感：结算弹层淡入 + 上滑 */
@keyframes sheet-fade {
  from {
    opacity: 0;
  }
}
@keyframes sheet-rise {
  from {
    opacity: 0;
    transform: translateY(26px) scale(0.96);
  }
}
.sheet h2 {
  margin: 0;
  font-family: var(--font-display);
  font-size: 34px;
  letter-spacing: 0.16em;
}
.sheet p {
  margin: 0;
}
.win {
  color: var(--accent);
}
.lose {
  color: var(--ink);
}
.ranking {
  width: 100%;
  list-style: none;
  margin: 4px 0 8px;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.bots-note {
  margin: 0;
  font-size: 12px;
}
.rank-note {
  margin: 0;
  font-size: 13px;
}
.rank-note.up {
  color: var(--accent);
}
.rank-note.down {
  color: var(--kill);
}
.coin-note {
  margin: 0;
  font-size: 13px;
}
.coin-note.up {
  color: var(--accent);
}
.coin-note.down {
  color: var(--kill);
}
.ranking li {
  display: grid;
  grid-template-columns: 24px 10px 1fr auto;
  gap: 8px;
  align-items: center;
  padding: 8px 10px;
  border-radius: 8px;
  background: var(--sea-dim);
  font-size: 13px;
  text-align: left;
}
.ranking li.me {
  outline: 1px solid var(--accent);
}
.rank {
  font-family: var(--font-display);
  font-size: 16px;
  text-align: center;
}
.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--seat);
}
.nick {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.stat {
  font-size: 11px;
  white-space: nowrap;
}
</style>
