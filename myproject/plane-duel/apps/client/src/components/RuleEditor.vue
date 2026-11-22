<script setup lang="ts">
/**
 * 规则编辑器。所有判断都在 rule-editor-model.ts，这里只负责绑定控件。
 *
 * 用本地草稿编辑、确认时提交：步进器连点时不该每一下都发 updateRules，
 * 而且房主改规则会清空全桌的准备状态。
 */
import { computed, ref, watch } from 'vue'
import { BOARD_MAX, BOARD_MIN, PRESETS, PRESET_LABELS, TURN_SECONDS, maxPlanes, type TurnSeconds, type RuleSet } from '@plane-duel/shared'
import { clampPlanes, densityWarning, ruleSummary } from '../rule-editor-model'

const props = defineProps<{ rules: RuleSet; submitLabel?: string; showListing?: boolean }>()
const emit = defineEmits<{ submit: [rules: RuleSet, listed: boolean] }>()

const draft = ref<RuleSet>({ ...props.rules })
/** 好友房默认公开到大厅列表（spec §20.6）；WaitingRoom 复用时不传 showListing。 */
const listed = ref(true)
watch(
  () => props.rules,
  (r) => (draft.value = { ...r }),
)

const planeMax = computed(() => maxPlanes(draft.value.boardSize))
const summary = computed(() => ruleSummary(draft.value))
const warning = computed(() => densityWarning(draft.value))

function setBoard(delta: number) {
  const boardSize = Math.min(BOARD_MAX, Math.max(BOARD_MIN, draft.value.boardSize + delta))
  draft.value = clampPlanes({ ...draft.value, boardSize })
}

function setPlanes(delta: number) {
  const planeCount = Math.min(planeMax.value, Math.max(1, draft.value.planeCount + delta))
  draft.value = { ...draft.value, planeCount }
}

function setTurn(sec: TurnSeconds) {
  draft.value = { ...draft.value, turnSeconds: sec }
}

function applyPreset(rules: RuleSet) {
  draft.value = { ...rules }
}
</script>

<template>
  <div class="editor">
    <div class="presets">
      <button v-for="(preset, id) in PRESETS" :key="id" type="button" class="chip" @click="applyPreset(preset)">
        {{ PRESET_LABELS[id] }}
      </button>
    </div>

    <div class="row">
      <span class="name">棋盘边长</span>
      <div class="stepper">
        <button type="button" :disabled="draft.boardSize <= BOARD_MIN" aria-label="减小边长" @click="setBoard(-1)">−</button>
        <span class="value">{{ draft.boardSize }}×{{ draft.boardSize }}</span>
        <button type="button" :disabled="draft.boardSize >= BOARD_MAX" aria-label="增大边长" @click="setBoard(1)">+</button>
      </div>
    </div>

    <div class="row">
      <span class="name">飞机数<span class="muted small"> 上限 {{ planeMax }}</span></span>
      <div class="stepper">
        <button type="button" :disabled="draft.planeCount <= 1" aria-label="减少飞机" @click="setPlanes(-1)">−</button>
        <span class="value">{{ draft.planeCount }} 架</span>
        <button type="button" :disabled="draft.planeCount >= planeMax" aria-label="增加飞机" @click="setPlanes(1)">+</button>
      </div>
    </div>

    <div class="row wrap">
      <span class="name">回合时长</span>
      <div class="segments">
        <button
          v-for="sec in TURN_SECONDS"
          :key="sec"
          type="button"
          class="chip"
          :class="{ on: draft.turnSeconds === sec }"
          @click="setTurn(sec)"
        >
          {{ sec }}秒
        </button>
      </div>
    </div>

    <label class="row">
      <span class="name">推理提示</span>
      <input v-model="draft.hintAllowed" type="checkbox" class="switch" />
    </label>

    <label v-if="showListing" class="row">
      <span class="name">公开到房间列表<span class="muted small"> 其他玩家可以在大厅看到并加入</span></span>
      <input v-model="listed" type="checkbox" class="switch" />
    </label>

    <p class="summary">{{ summary }}</p>
    <p v-if="warning" class="warn">{{ warning }}</p>

    <button type="button" class="btn primary" @click="emit('submit', { ...draft }, listed)">
      {{ submitLabel ?? '保存规则' }}
    </button>
  </div>
</template>

<style scoped>
.editor {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.presets,
.segments {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.chip {
  padding: 6px 12px;
  border-radius: 999px;
  border: 1px solid var(--grid-line);
  background: var(--sea-dim);
  color: var(--ink-soft);
  font-size: 13px;
  cursor: pointer;
}
.chip.on {
  border-color: var(--accent);
  color: var(--ink);
  background: rgb(240 160 48 / 0.16);
}
.row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.row.wrap {
  flex-wrap: wrap;
  align-items: flex-start;
}
.name {
  font-size: 14px;
  color: var(--ink-soft);
}
.small {
  font-size: 12px;
}
.stepper {
  display: flex;
  align-items: center;
  gap: 4px;
}
.stepper button {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  border: 1px solid var(--grid-line);
  background: var(--sea-dim);
  font-size: 18px;
  line-height: 1;
  cursor: pointer;
}
.stepper button:disabled {
  opacity: 0.35;
  cursor: default;
}
.value {
  min-width: 4.5em;
  text-align: center;
  font-variant-numeric: tabular-nums;
}
.switch {
  width: 22px;
  height: 22px;
  accent-color: var(--accent);
  cursor: pointer;
}
.summary {
  margin: 0;
  font-size: 13px;
  color: var(--ink-soft);
  letter-spacing: 0.04em;
}
.warn {
  margin: 0;
  font-size: 13px;
  color: var(--warn-ink, var(--hit));
}
</style>
