<script setup lang="ts">
/**
 * 正式登录页：玩家唯一入口（token 不进 URL），过期/退出后也回到这里。
 * 三个模式共用一套卡片与表单语言（16px 输入、busy 禁用、role=alert 错误行、回车提交）：
 *   login    —— 账号密码登录，成功即写 localStorage 'plane-duel:vpnToken'，由 App 重建会话；
 *   register —— 注册（用户名/密码/确认密码/邮箱可选），成功后 auth.register 内部自动 login，直接进游戏；
 *   reset    —— 找回密码两步：step1 邮箱发验证码（60s 倒计时禁用），step2 验证码+新密码，
 *               成功后回登录 tab 并预填、提示"密码已重置，请登录"。
 * 失败一律透出服务端 error 中文文案（见 net/auth.ts）。tab 切换不清空已输入的用户名。
 */
import { computed, onUnmounted, ref } from 'vue'
import { findpass, login, register, resetpass } from '../net/auth'

const props = defineProps<{
  /** 场景文案：首次进入 / 登录已过期（过期覆盖层复用本页） */
  title?: string
}>()

const emit = defineEmits<{ loggedIn: [] }>()

type Mode = 'login' | 'register' | 'reset'

const mode = ref<Mode>('login')
/** 找回密码内部两步 */
const resetStep = ref<1 | 2>(1)

/* ---- 登录 ---- */
const name = ref('')
const pwd = ref('')
const busy = ref(false)

/* ---- 注册（name 与登录共用，tab 切换不清空） ---- */
const regPwd = ref('')
const regRePwd = ref('')
const regEmail = ref('')
const busyReg = ref(false)

/* ---- 找回密码 ---- */
const rpEmail = ref('')
const rpCode = ref('')
const rpPwd = ref('')
const rpRePwd = ref('')
const busySend = ref(false)
const busyReset = ref(false)
/** 验证码发送后的重发倒计时（秒），0 = 可再发 */
const countdown = ref(0)
let timer: ReturnType<typeof setInterval> | null = null

function startCountdown() {
  countdown.value = 60
  timer = setInterval(() => {
    countdown.value -= 1
    if (countdown.value <= 0 && timer) {
      clearInterval(timer)
      timer = null
    }
  }, 1000)
}
onUnmounted(() => {
  if (timer) clearInterval(timer)
})

const error = ref('')
const notice = ref('')
const clearTip = () => {
  error.value = ''
  notice.value = ''
}

const heading = computed(() => {
  if (mode.value === 'reset') return '重置密码'
  return props.title ?? '登录飞机对决'
})

/* ---- 模式切换 ---- */
function switchTab(m: 'login' | 'register') {
  if (mode.value === m) return
  mode.value = m
  clearTip()
}
function goReset() {
  mode.value = 'reset'
  resetStep.value = 1
  clearTip()
}
function backToLogin() {
  mode.value = 'login'
  clearTip()
}

/* ---- 提交 ---- */
async function submitLogin() {
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

async function submitRegister() {
  if (busyReg.value) return
  if (!name.value.trim() || !regPwd.value || !regRePwd.value) {
    error.value = '请填写账号和密码'
    return
  }
  if (regPwd.value !== regRePwd.value) {
    error.value = '两次输入的密码不一致'
    return
  }
  busyReg.value = true
  error.value = ''
  try {
    // register 内部成功后自动 login，直接进游戏
    await register(name.value.trim(), regPwd.value, regRePwd.value, regEmail.value.trim())
    emit('loggedIn')
  } catch (e) {
    error.value = e instanceof Error && e.message ? e.message : '注册失败，请稍后再试'
  } finally {
    busyReg.value = false
  }
}

async function sendCode() {
  if (busySend.value || countdown.value > 0) return
  if (!rpEmail.value.trim()) {
    error.value = '请输入邮箱'
    return
  }
  busySend.value = true
  error.value = ''
  try {
    await findpass(rpEmail.value.trim())
    // 服务端不区分邮箱是否绑定，文案与成功语义保持一致
    notice.value = '若邮箱已绑定账号，验证码已发送，请查收'
    startCountdown()
    resetStep.value = 2
  } catch (e) {
    error.value = e instanceof Error && e.message ? e.message : '发送失败，请稍后再试'
  } finally {
    busySend.value = false
  }
}

async function submitReset() {
  if (busyReset.value) return
  if (!rpCode.value.trim() || !rpPwd.value || !rpRePwd.value) {
    error.value = '请填写验证码和新密码'
    return
  }
  if (rpPwd.value !== rpRePwd.value) {
    error.value = '两次输入的密码不一致'
    return
  }
  busyReset.value = true
  error.value = ''
  try {
    await resetpass(rpEmail.value.trim(), rpCode.value.trim(), rpPwd.value, rpRePwd.value)
    // 回登录 tab：预填用户名，提示直接登录
    name.value = rpEmail.value.trim() || name.value
    pwd.value = ''
    mode.value = 'login'
    notice.value = '密码已重置，请登录'
    error.value = ''
  } catch (e) {
    error.value = e instanceof Error && e.message ? e.message : '重置失败，请稍后再试'
  } finally {
    busyReset.value = false
  }
}

function onSubmit() {
  if (mode.value === 'login') void submitLogin()
  else if (mode.value === 'register') void submitRegister()
  else if (resetStep.value === 1) void sendCode()
  else void submitReset()
}
</script>

<template>
  <div class="gate">
    <form class="card" @submit.prevent="onSubmit">
      <div class="emblem" aria-hidden="true">
        <span v-for="i in 9" :key="i" :class="{ head: i === 5 }" />
      </div>
      <h1>{{ heading }}</h1>

      <!-- 登录/注册 tab（重置流里不出现，用"返回登录"退出） -->
      <div v-if="mode !== 'reset'" class="tabs" role="tablist">
        <button
          type="button"
          role="tab"
          class="tab"
          :class="{ active: mode === 'login' }"
          :aria-selected="mode === 'login'"
          @click="switchTab('login')"
        >
          登录
        </button>
        <button
          type="button"
          role="tab"
          class="tab"
          :class="{ active: mode === 'register' }"
          :aria-selected="mode === 'register'"
          @click="switchTab('register')"
        >
          注册
        </button>
      </div>

      <p v-if="notice" class="notice" role="status">{{ notice }}</p>

      <!-- ===== 登录 ===== -->
      <template v-if="mode === 'login'">
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
            @input="clearTip()"
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
            @input="clearTip()"
          />
        </label>
        <p v-if="error" class="error" role="alert">{{ error }}</p>
        <button type="submit" class="btn primary" :disabled="busy">
          {{ busy ? '登录中…' : '登录' }}
        </button>
        <button type="button" class="link" @click="goReset">忘记密码？</button>
      </template>

      <!-- ===== 注册 ===== -->
      <template v-else-if="mode === 'register'">
        <label class="field">
          <span class="label">用户名</span>
          <input
            v-model="name"
            class="field-input"
            type="text"
            name="username"
            autocomplete="username"
            enterkeyhint="next"
            required
            @input="clearTip()"
          />
        </label>
        <label class="field">
          <span class="label">密码</span>
          <input
            v-model="regPwd"
            class="field-input"
            type="password"
            name="new-password"
            autocomplete="new-password"
            enterkeyhint="next"
            required
            @input="clearTip()"
          />
        </label>
        <label class="field">
          <span class="label">确认密码</span>
          <input
            v-model="regRePwd"
            class="field-input"
            type="password"
            name="confirm-password"
            autocomplete="new-password"
            enterkeyhint="next"
            required
            @input="clearTip()"
          />
        </label>
        <label class="field">
          <span class="label">邮箱</span>
          <input
            v-model="regEmail"
            class="field-input"
            type="email"
            name="email"
            autocomplete="email"
            enterkeyhint="go"
            placeholder="可选，用于找回密码"
            @input="clearTip()"
          />
        </label>
        <p v-if="error" class="error" role="alert">{{ error }}</p>
        <button type="submit" class="btn primary" :disabled="busyReg">
          {{ busyReg ? '注册中…' : '注册并进入游戏' }}
        </button>
      </template>

      <!-- ===== 找回密码 step1：邮箱发验证码 ===== -->
      <template v-else-if="resetStep === 1">
        <p class="tip">填写注册时留的邮箱，我们给它发验证码。</p>
        <label class="field">
          <span class="label">邮箱</span>
          <input
            v-model="rpEmail"
            class="field-input"
            type="email"
            name="email"
            autocomplete="email"
            enterkeyhint="go"
            required
            @input="clearTip()"
          />
        </label>
        <p v-if="error" class="error" role="alert">{{ error }}</p>
        <button type="submit" class="btn primary" :disabled="busySend || countdown > 0">
          {{ countdown > 0 ? `验证码已发送（${countdown}s 后可重发）` : busySend ? '发送中…' : '发送验证码' }}
        </button>
        <button type="button" class="link" @click="backToLogin">返回登录</button>
      </template>

      <!-- ===== 找回密码 step2：验证码 + 新密码 ===== -->
      <template v-else>
        <p class="tip">验证码已发到 {{ rpEmail }}，有效期很短，尽快填写。</p>
        <label class="field">
          <span class="label">验证码</span>
          <input
            v-model="rpCode"
            class="field-input"
            type="text"
            name="one-time-code"
            autocomplete="one-time-code"
            inputmode="numeric"
            pattern="\d{6}"
            maxlength="6"
            enterkeyhint="next"
            placeholder="6 位验证码"
            required
            @input="clearTip()"
          />
        </label>
        <label class="field">
          <span class="label">新密码</span>
          <input
            v-model="rpPwd"
            class="field-input"
            type="password"
            name="new-password"
            autocomplete="new-password"
            enterkeyhint="next"
            required
            @input="clearTip()"
          />
        </label>
        <label class="field">
          <span class="label">确认新密码</span>
          <input
            v-model="rpRePwd"
            class="field-input"
            type="password"
            name="confirm-password"
            autocomplete="new-password"
            enterkeyhint="go"
            required
            @input="clearTip()"
          />
        </label>
        <p v-if="error" class="error" role="alert">{{ error }}</p>
        <button type="submit" class="btn primary" :disabled="busyReset">
          {{ busyReset ? '重置中…' : '重置密码' }}
        </button>
        <button
          type="button"
          class="link"
          :disabled="countdown > 0"
          @click="resetStep = 1; clearTip()"
        >
          {{ countdown > 0 ? `重新发送（${countdown}s）` : '重新发送验证码' }}
        </button>
      </template>
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
.tabs {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 4px;
  padding: 4px;
  border-radius: 12px;
  background: var(--sea-dim);
  border: 1px solid var(--grid-line);
}
.tab {
  padding: 10px 0;
  border: 0;
  border-radius: 9px;
  background: transparent;
  color: var(--ink-soft);
  font-size: 15px;
  font-weight: 600;
  letter-spacing: 0.04em;
  cursor: pointer;
  transition: background-color 120ms ease, color 120ms ease;
}
.tab.active {
  background: var(--surface);
  color: var(--accent-ink);
  box-shadow: var(--ring);
}
.tab:focus-visible {
  outline: 2px solid var(--focus);
  outline-offset: 2px;
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
.field-input::placeholder {
  color: var(--ink-soft);
}
.field-input:focus-visible {
  outline: 2px solid var(--focus);
  outline-offset: 2px;
}
.tip {
  margin: 0;
  font-size: 13px;
  color: var(--ink-soft);
}
.error {
  margin: 0;
  font-size: 14px;
  color: var(--kill);
}
.notice {
  margin: 0;
  font-size: 14px;
  color: var(--ok-ink);
}
.link {
  align-self: center;
  padding: 4px 8px;
  border: 0;
  background: transparent;
  color: var(--accent-ink);
  font-size: 14px;
  cursor: pointer;
}
.link:disabled {
  color: var(--ink-soft);
  cursor: default;
}
.link:focus-visible {
  outline: 2px solid var(--focus);
  outline-offset: 2px;
}
</style>
