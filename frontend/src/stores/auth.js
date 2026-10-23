import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import {
  changePassword as apiChangePassword,
  checkInvite,
  getMe,
  login as apiLogin,
  register as apiRegister,
} from '../api/client'

const TOKEN_KEY = 'aichat_token'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem(TOKEN_KEY) || '')
  const user = ref(null)
  const bootstrapped = ref(false)

  const isLoggedIn = computed(() => !!token.value && !!user.value)

  function setToken(value) {
    token.value = value || ''
    if (value) localStorage.setItem(TOKEN_KEY, value)
    else localStorage.removeItem(TOKEN_KEY)
  }

  /** 应用启动时根据本地 token 拉取当前用户 */
  async function bootstrap() {
    if (!token.value) {
      user.value = null
      bootstrapped.value = true
      return
    }
    try {
      user.value = await getMe()
    } catch {
      setToken('')
      user.value = null
    } finally {
      bootstrapped.value = true
    }
  }

  async function login(username, password) {
    const data = await apiLogin(username, password)
    setToken(data.token)
    user.value = data.user
    return data.user
  }

  async function register(code, username, password) {
    const data = await apiRegister(code, username, password)
    setToken(data.token)
    user.value = data.user
    return data.user
  }

  async function verifyInvite(code) {
    return checkInvite(code)
  }

  async function changePassword(oldPassword, newPassword) {
    await apiChangePassword(oldPassword, newPassword)
  }

  function logout() {
    setToken('')
    user.value = null
  }

  return {
    token,
    user,
    bootstrapped,
    isLoggedIn,
    bootstrap,
    login,
    register,
    verifyInvite,
    changePassword,
    logout,
    setToken,
  }
})
