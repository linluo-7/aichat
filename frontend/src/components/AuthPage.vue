<script setup>
import { ref } from 'vue'
import { useAuthStore } from '../stores/auth'

const emit = defineEmits(['done'])
const auth = useAuthStore()

/** login | register-code | register-form */
const mode = ref('login')
const username = ref('')
const password = ref('')
const password2 = ref('')
const inviteCode = ref('')
const error = ref('')
const loading = ref(false)

function switchMode(next) {
  mode.value = next
  error.value = ''
}

async function submitLogin() {
  error.value = ''
  if (!username.value.trim() || !password.value) {
    error.value = '请输入用户名和密码'
    return
  }
  loading.value = true
  try {
    await auth.login(username.value.trim(), password.value)
    emit('done')
  } catch (e) {
    error.value = e.response?.data?.detail || e.message || '登录失败'
  } finally {
    loading.value = false
  }
}

async function submitInvite() {
  error.value = ''
  if (!inviteCode.value.trim()) {
    error.value = '请输入邀请码'
    return
  }
  loading.value = true
  try {
    const res = await auth.verifyInvite(inviteCode.value.trim())
    if (!res.ok) {
      error.value = res.message || '邀请码无效'
      return
    }
    mode.value = 'register-form'
  } catch (e) {
    error.value = e.response?.data?.detail || e.message || '校验失败'
  } finally {
    loading.value = false
  }
}

async function submitRegister() {
  error.value = ''
  const u = username.value.trim()
  if (u.length < 2) {
    error.value = '用户名至少 2 个字符'
    return
  }
  if (password.value.length < 6) {
    error.value = '密码至少 6 位'
    return
  }
  if (password.value !== password2.value) {
    error.value = '两次密码不一致'
    return
  }
  loading.value = true
  try {
    await auth.register(inviteCode.value.trim(), u, password.value)
    emit('done')
  } catch (e) {
    error.value = e.response?.data?.detail || e.message || '注册失败'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="auth-page">
    <div class="auth-card">
      <h1 class="brand">AI Chat</h1>
      <p class="tagline">学习分享 · 自带 Key · 邀请注册</p>

      <template v-if="mode === 'login'">
        <h2 class="title">登录</h2>
        <label class="field">
          <span>用户名</span>
          <input v-model="username" type="text" autocomplete="username" @keyup.enter="submitLogin" />
        </label>
        <label class="field">
          <span>密码</span>
          <input
            v-model="password"
            type="password"
            autocomplete="current-password"
            @keyup.enter="submitLogin"
          />
        </label>
        <p v-if="error" class="err">{{ error }}</p>
        <button type="button" class="primary" :disabled="loading" @click="submitLogin">
          {{ loading ? '登录中…' : '登录' }}
        </button>
        <p class="switch">
          没有账号？
          <button type="button" class="link" @click="switchMode('register-code')">用邀请码注册</button>
        </p>
      </template>

      <template v-else-if="mode === 'register-code'">
        <h2 class="title">注册 · 邀请码</h2>
        <p class="hint">请输入站长发给你的一次性邀请码</p>
        <label class="field">
          <span>邀请码</span>
          <input
            v-model="inviteCode"
            type="text"
            autocomplete="off"
            placeholder="例如 ABCD-EFGH12"
            @keyup.enter="submitInvite"
          />
        </label>
        <p v-if="error" class="err">{{ error }}</p>
        <button type="button" class="primary" :disabled="loading" @click="submitInvite">
          {{ loading ? '校验中…' : '下一步' }}
        </button>
        <p class="switch">
          <button type="button" class="link" @click="switchMode('login')">返回登录</button>
        </p>
      </template>

      <template v-else>
        <h2 class="title">注册 · 设置账号</h2>
        <p class="hint">邀请码已通过，请设置用户名和密码</p>
        <label class="field">
          <span>用户名</span>
          <input v-model="username" type="text" autocomplete="username" />
        </label>
        <label class="field">
          <span>密码</span>
          <input v-model="password" type="password" autocomplete="new-password" />
        </label>
        <label class="field">
          <span>确认密码</span>
          <input
            v-model="password2"
            type="password"
            autocomplete="new-password"
            @keyup.enter="submitRegister"
          />
        </label>
        <p v-if="error" class="err">{{ error }}</p>
        <button type="button" class="primary" :disabled="loading" @click="submitRegister">
          {{ loading ? '注册中…' : '完成注册' }}
        </button>
        <p class="switch">
          <button type="button" class="link" @click="switchMode('register-code')">返回修改邀请码</button>
        </p>
      </template>
    </div>
  </div>
</template>

<style scoped>
.auth-page {
  min-height: 100vh;
  min-height: 100dvh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px 16px;
  background:
    radial-gradient(ellipse at 20% 0%, rgba(7, 193, 96, 0.12), transparent 50%),
    radial-gradient(ellipse at 80% 100%, rgba(16, 174, 255, 0.1), transparent 45%),
    #f5f5f5;
}
.auth-card {
  width: 100%;
  max-width: 380px;
  background: #fff;
  border-radius: 12px;
  padding: 28px 24px 22px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.06);
}
.brand {
  margin: 0;
  font-size: 26px;
  font-weight: 700;
  letter-spacing: 0.04em;
  color: #111;
  text-align: center;
}
.tagline {
  margin: 6px 0 22px;
  text-align: center;
  font-size: 12px;
  color: #888;
}
.title {
  margin: 0 0 14px;
  font-size: 17px;
  font-weight: 600;
}
.hint {
  margin: -6px 0 14px;
  font-size: 13px;
  color: #888;
}
.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 12px;
  font-size: 13px;
  color: #555;
}
.field input {
  border: 1px solid #e5e5e5;
  border-radius: 8px;
  padding: 10px 12px;
  font-size: 15px;
  outline: none;
}
.field input:focus {
  border-color: #07c160;
}
.err {
  margin: 0 0 10px;
  font-size: 13px;
  color: #fa5151;
}
.primary {
  width: 100%;
  border: none;
  border-radius: 8px;
  padding: 11px;
  background: #07c160;
  color: #fff;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
}
.primary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.switch {
  margin: 16px 0 0;
  text-align: center;
  font-size: 13px;
  color: #888;
}
.link {
  border: none;
  background: none;
  color: #576b95;
  cursor: pointer;
  padding: 0;
  font-size: inherit;
}
</style>
