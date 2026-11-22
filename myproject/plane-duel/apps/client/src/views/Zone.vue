<script setup lang="ts">
/**
 * 专区：一个专区 = 一档人数。四档预设分别排队（含电脑补位倒计时），
 * 可以开人机练习，可以看/加入公开房间，或展开规则编辑器创建好友房。
 * 排队中点别的档位 = 换队列（服务端 queueJoin 会先退出当前队列）。
 */
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { PRESETS, PRESET_LABELS, TICKETS, type Capacity, type PresetId, type RuleSet, type TicketId } from '@plane-duel/shared'
import RuleEditor from '../components/RuleEditor.vue'
import RoomList from '../components/RoomList.vue'
import { botFillText } from '../lobby-model'
import { practiceRequest, ruleSummary } from '../rule-editor-model'
import type { GameStore } from '../net/store'
import type { SocketHandle } from '../net/socket'

const props = defineProps<{ store: GameStore; socket: SocketHandle; capacity: Capacity }>()
const s = props.store.state
const emit = defineEmits<{ back: [] }>()

const PRESET_IDS = Object.keys(PRESETS) as PresetId[]
const TICKET_IDS = ['free', 'standard', 'advanced'] as const
const TICKET_LABELS: Record<TicketId, string> = { free: '免费场', standard: '标准场', advanced: '高级场' }
const creating = ref(false)
const capacityText = computed(() => (props.capacity === 2 ? '2 人对决' : `${props.capacity} 人混战`))

/** 门票档（spec §廿二.7）：只对匹配排队生效；免费档不发 ticket 字段（v4 兼容路径） */
const ticket = ref<TicketId>('free')
const canAfford = (id: TicketId) => s.coins >= TICKETS[id].fee

/** 只认本专区的队列：在别的专区排队时，这里显示未排队 */
const myQueue = computed(() => (s.queue && s.queue.capacity === props.capacity ? s.queue : null))

// 倒计时要自己走表：服务端只给 botFillAt 时刻
const now = ref(Date.now())
let clock: ReturnType<typeof setInterval> | undefined
onMounted(() => {
  clock = setInterval(() => (now.value = Date.now()), 1000)
  props.socket.send({ type: 'roomListSubscribe', capacity: props.capacity })
})
onUnmounted(() => {
  if (clock !== undefined) clearInterval(clock)
  props.socket.send({ type: 'roomListUnsubscribe' })
})

const fillText = computed(() => (myQueue.value ? botFillText(myQueue.value, now.value) : null))

/** 订阅快照只认本专区；别的专区的列表到达时（不会发生，但状态共享）忽略 */
const roomEntries = computed(() => (s.roomList?.capacity === props.capacity ? s.roomList.entries : null))

function queueJoin(preset: PresetId) {
  creating.value = false
  // 免费场不带 ticket 字段：与服务端 v4 兼容路径完全一致
  props.socket.send(
    ticket.value === 'free'
      ? { type: 'queueJoin', capacity: props.capacity, preset }
      : { type: 'queueJoin', capacity: props.capacity, preset, ticket: ticket.value },
  )
}

function pickTicket(id: TicketId) {
  ticket.value = id
  // 排队中切档 = 换队列；服务端 queueJoin 会退旧队列并退旧票
  if (myQueue.value) queueJoin(myQueue.value.preset)
}

function queueLeave() {
  props.socket.send({ type: 'queueLeave' })
}

function createPractice(preset: PresetId) {
  creating.value = false
  props.socket.send(practiceRequest(props.capacity, preset))
}

function joinListed(tableId: string) {
  props.socket.send({ type: 'joinListed', tableId })
}

function createRoom(rules: RuleSet, listed: boolean) {
  creating.value = false
  props.socket.send({ type: 'createRoom', capacity: props.capacity, rules, listed })
}
</script>

<template>
  <section class="zone">
    <header class="head">
      <button type="button" class="back" aria-label="返回大厅" @click="emit('back')">‹</button>
      <h1>{{ capacityText }}</h1>
      <span class="spacer" aria-hidden="true" />
    </header>

    <div class="tickets" role="radiogroup" aria-label="门票档">
      <button
        v-for="id in TICKET_IDS"
        :key="id"
        type="button"
        role="radio"
        :aria-checked="ticket === id"
        class="ticket"
        :class="{ on: ticket === id }"
        :disabled="!canAfford(id)"
        @click="pickTicket(id)"
      >
        <span class="ticket-name">{{ TICKET_LABELS[id] }}</span>
        <span class="ticket-price" :class="{ free: id === 'free' }">
          {{ id === 'free' ? '0' : `${TICKETS[id].fee} 币` }}
        </span>
        <span v-if="id !== 'free'" class="ticket-sub muted">胜者 +{{ TICKETS[id].reward }}</span>
        <span v-else class="ticket-sub muted">随时可退</span>
      </button>
    </div>
    <p v-if="ticket !== 'free'" class="ticket-note muted small">
      排位先扣门票；没成真人局（含电脑补位）原路退回。奖励固定额，与对手无关。
    </p>

    <div v-if="myQueue" class="card searching">
      <div class="radar" aria-hidden="true" />
      <p>
        排队中 <strong>{{ myQueue.waiting }}/{{ capacity }}</strong>
        <span class="muted"> · {{ PRESET_LABELS[myQueue.preset] }}</span>
        <span v-if="myQueue.ticket && myQueue.ticket !== 'free'" class="muted"> · {{ TICKET_LABELS[myQueue.ticket] }}</span>
      </p>
      <p v-if="fillText" class="fill">{{ fillText }}</p>
      <p v-if="s.queueTimedOut" class="muted small">
        暂时没有对手在线。可以继续等待，或者创建好友房邀请朋友。
      </p>
      <button type="button" class="btn ghost" @click="queueLeave">取消排队</button>
    </div>

    <div class="presets">
      <button
        v-for="id in PRESET_IDS"
        :key="id"
        type="button"
        class="preset"
        :class="{ on: myQueue?.preset === id }"
        @click="queueJoin(id)"
      >
        <span class="preset-name">{{ PRESET_LABELS[id] }}</span>
        <span class="preset-rules muted">{{ ruleSummary(PRESETS[id]) }}</span>
      </button>
    </div>

    <div class="card">
      <h2>人机练习 <span class="muted small">练习 · 不计段位</span></h2>
      <p class="muted small">缺的座位由电脑补上，随时可退出。</p>
      <div class="practice">
        <button v-for="id in PRESET_IDS" :key="id" type="button" class="chip" @click="createPractice(id)">
          {{ PRESET_LABELS[id] }}
        </button>
      </div>
    </div>

    <div class="card">
      <h2>公开房间</h2>
      <RoomList :entries="roomEntries" @join="joinListed" />
    </div>

    <div class="card">
      <h2>好友房</h2>
      <template v-if="!creating">
        <p class="muted small">人满且全员准备才开局。规则可以自己定。</p>
        <button type="button" class="btn" @click="creating = true">创建好友房</button>
      </template>
      <template v-else>
        <RuleEditor :rules="PRESETS.standard" submit-label="创建好友房" show-listing @submit="createRoom" />
        <button type="button" class="btn ghost" @click="creating = false">取消</button>
      </template>
    </div>
  </section>
</template>

<style scoped>
.zone {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.head {
  display: flex;
  align-items: center;
  gap: 8px;
}
.head h1 {
  flex: 1;
  margin: 0;
  font-family: var(--font-display);
  font-size: 24px;
  letter-spacing: 0.1em;
  text-align: center;
}
.back,
.spacer {
  width: 36px;
  height: 36px;
}
.back {
  border: 0;
  background: none;
  font-size: 26px;
  line-height: 1;
  color: var(--ink-soft);
  cursor: pointer;
}
.tickets {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
}
.ticket {
  display: flex;
  flex-direction: column;
  gap: 2px;
  align-items: flex-start;
  padding: 10px 12px;
  border-radius: 12px;
  border: 1px solid var(--grid-line);
  background: rgb(21 37 59 / 0.7);
  text-align: left;
  cursor: pointer;
  transition: border-color 120ms ease;
}
.ticket:hover:not(:disabled) {
  border-color: var(--pending);
}
.ticket.on {
  border-color: var(--accent);
  background: rgb(240 160 48 / 0.12);
}
.ticket:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}
.ticket-name {
  font-family: var(--font-display);
  font-size: 15px;
  letter-spacing: 0.06em;
}
.ticket-price {
  font-size: 13px;
  color: var(--accent);
}
.ticket-price.free {
  color: var(--ink-soft);
}
.ticket-sub {
  font-size: 11px;
}
.ticket-note {
  margin: -6px 0 0;
}
.presets {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.preset {
  display: flex;
  flex-direction: column;
  gap: 2px;
  align-items: flex-start;
  padding: 14px 16px;
  border-radius: 12px;
  border: 1px solid var(--grid-line);
  background: rgb(21 37 59 / 0.7);
  text-align: left;
  cursor: pointer;
  transition: border-color 120ms ease;
}
.preset:hover {
  border-color: var(--pending);
}
.preset.on {
  border-color: var(--accent);
  background: rgb(240 160 48 / 0.12);
}
.preset-name {
  font-family: var(--font-display);
  font-size: 19px;
  letter-spacing: 0.08em;
}
.preset-rules {
  font-size: 12px;
}
.card {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 16px;
  border-radius: 14px;
  background: rgb(21 37 59 / 0.7);
  border: 1px solid var(--grid-line);
}
.card h2 {
  margin: 0;
  font-size: 14px;
  letter-spacing: 0.1em;
  color: var(--ink-soft);
}
.card p {
  margin: 0;
}
.small {
  font-size: 13px;
}
.searching {
  align-items: center;
  text-align: center;
}
.fill {
  color: var(--accent);
  font-size: 14px;
}
.radar {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  border: 1px solid var(--pending);
  background: conic-gradient(from 0deg, rgb(240 160 48 / 0.35), transparent 30%);
  animation: sweep 1.6s linear infinite;
}
@keyframes sweep {
  to {
    transform: rotate(1turn);
  }
}
.practice {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.chip {
  padding: 8px 14px;
  border-radius: 999px;
  border: 1px solid var(--grid-line);
  background: var(--sea-dim);
  color: var(--ink);
  font-size: 14px;
  cursor: pointer;
}
.chip:hover {
  border-color: var(--pending);
}
</style>
