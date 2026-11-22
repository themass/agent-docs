<script setup lang="ts">
/**
 * 正式登录页：玩家唯一入口（token 不进 URL），过期/退出后也回到这里。
 * 提交走 auth.login()：成功即写 localStorage 'plane-duel:vpnToken'，由 App 重建会话；
 * 失败透出服务端 error 文案。移动端优先：大字输入、回车提交、提交中禁用。
 */
import { ref } from 'vue'
import { login } from '../net/auth'

defineProps<{
  /** 场景文案：首次进入 / 登录已过期（过期覆盖层复用本页） */
  title?: string
}>()

const emit = defineEmits<{ loggedIn: [] }>()

const name = ref('')
const pwd = ref('')
const busy = ref(false)
const error = ref('')

async function submit() {
  if (busy.value) return
  if (!name.value.trim() || !pwd.value) {
    error.value = '请输入账号和密码'
    return
  }
  busy.value = true
  error.value = ''
  try {
    await login(name.value.trim(), pwd.value)
    emit('loggedIn')
  } catch (e) {
    error.value = e instanceof Error && e.message ? e.message : '登录失败，请稍后再试'
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="gate">
    <form class="card" @submit.prevent="submit">
      <div class="emblem" aria-hidden="true">
        <span v-for="i in 9" :key="i" :class="{ head: i === 5 }" />
      </div>
      <h1>{{ title ?? '登录飞机对决' }}</h1>
      <label class="field">
        <span class="label">账号</span>
        <input
          v-model="name"
          class="field-input"
          type="text"
          name="username"
          autocomplete="username"
          enterkeyhint="next"
          required
          @input="error = ''"
        />
      </label>
      <label class="field">
        <span class="label">密码</span>
        <input
          v-model="pwd"
          class="field-input"
          type="password"
          name="password"
          autocomplete="current-password"
          enterkeyhint="go"
          required
          @input="error = ''"
        />
      </label>
      <p v-if="error" class="error" role="alert">{{ error }}</p>
      <button type="submit" class="btn primary" :disabled="busy">
        {{ busy ? '登录中…' : '登录' }}
      </button>
    </form>
  </div>
</template>

<style scoped>
.gate {
  position: fixed;
  inset: 0;
  z-index: 40;
  display: flex;
  align-items: center;
  justify-content: center;
  /* 与大厅同一氛围：近黑靛蓝底 + 顶部电光青光晕 */
  background:
    radial-gradient(circle at 50% -10%, rgb(34 211 238 / 0.12) 0%, transparent 55%),
    var(--bg);
  padding: max(24px, env(safe-area-inset-top)) 20px max(24px, env(safe-area-inset-bottom));
  overflow-y: auto;
}
.card {
  width: 100%;
  max-width: 340px;
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 28px 22px;
  border-radius: 16px;
  background: var(--bg-raised);
  border: 1px solid var(--grid-line);
  box-shadow: var(--shadow);
}
.emblem {
  display: inline-grid;
  grid-template-columns: repeat(3, 14px);
  gap: 3px;
  justify-self: center;
}
.emblem span {
  width: 14px;
  height: 14px;
  border-radius: 2px;
  background: var(--hit);
}
.emblem span.head {
  background: var(--kill);
}
.card h1 {
  margin: 0 0 6px;
  font-family: var(--font-display);
  font-size: 26px;
  letter-spacing: 0.12em;
  text-align: center;
}
.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.label {
  font-size: 13px;
  color: var(--ink-soft);
}
.field-input {
  width: 100%;
  /* ≥16px 防 iOS 聚焦自动放大 */
  font-size: 16px;
  padding: 12px 14px;
  border-radius: 10px;
  border: 1px solid var(--grid-line);
  background: var(--sea-dim);
  color: var(--ink);
}
.field-input:focus-visible {
  outline: 2px solid var(--focus);
  outline-offset: 2px;
}
.error {
  margin: 0;
  font-size: 14px;
  color: var(--kill);
}
</style>
