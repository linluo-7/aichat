<script setup>
import { ref, watch } from 'vue'
import ImageCropModal from './ImageCropModal.vue'
import { CROP_PRESET_AVATAR, useImageCrop } from '../composables/useImageCrop'
import { useAuthStore } from '../stores/auth'
import { useChatStore } from '../stores/chat'
import { useProfileStore } from '../stores/profile'

const emit = defineEmits(['logout'])
const auth = useAuthStore()
const store = useChatStore()
const profile = useProfileStore()
const { cropOpen, cropSrc, cropOptions, handleCropConfirm, handleCropCancel, onImageSelected } =
  useImageCrop()

const nickname = ref(profile.nickname)
const preview = ref(profile.displayAvatar)
const saving = ref(false)
const error = ref('')
const avatarInput = ref(null)
const avatarFile = ref(null)

const showPwd = ref(false)
const oldPwd = ref('')
const newPwd = ref('')
const newPwd2 = ref('')
const pwdSaving = ref(false)
const pwdError = ref('')
const pwdOk = ref('')

watch(
  () => [profile.nickname, profile.displayAvatar],
  () => {
    if (!avatarFile.value) {
      nickname.value = profile.nickname
      preview.value = profile.displayAvatar
    }
  },
)

function pickAvatar() {
  avatarInput.value?.click()
}

function onFileChange(e) {
  onImageSelected(e, CROP_PRESET_AVATAR, (file) => {
    if (!file) return
    preview.value = URL.createObjectURL(file)
    avatarFile.value = file
  })
}

function onCroppedAvatar(file) {
  handleCropConfirm(file)
}

function onCropDismiss() {
  handleCropCancel()
}

async function submit() {
  error.value = ''
  if (!nickname.value.trim()) {
    error.value = '请输入昵称'
    return
  }
  saving.value = true
  try {
    if (nickname.value.trim() !== profile.nickname) {
      await profile.setNickname(nickname.value.trim())
    }
    if (avatarFile.value) {
      await profile.setAvatar(avatarFile.value)
      avatarFile.value = null
    }
  } catch (e) {
    error.value = e.response?.data?.detail || e.message || '保存失败'
  } finally {
    saving.value = false
  }
}

async function submitPassword() {
  pwdError.value = ''
  pwdOk.value = ''
  if (newPwd.value.length < 6) {
    pwdError.value = '新密码至少 6 位'
    return
  }
  if (newPwd.value !== newPwd2.value) {
    pwdError.value = '两次新密码不一致'
    return
  }
  pwdSaving.value = true
  try {
    await auth.changePassword(oldPwd.value, newPwd.value)
    pwdOk.value = '密码已更新'
    oldPwd.value = ''
    newPwd.value = ''
    newPwd2.value = ''
  } catch (e) {
    pwdError.value = e.response?.data?.detail || e.message || '修改失败'
  } finally {
    pwdSaving.value = false
  }
}

function logout() {
  auth.logout()
  store.$reset()
  localStorage.removeItem('aichat_last_sync_id')
  emit('logout')
}
</script>

<template>
  <div class="me-page">
    <header class="nav">
      <h1 class="title">我的</h1>
    </header>

    <div class="scroll">
      <section class="hero">
        <button type="button" class="avatar-btn" @click="pickAvatar">
          <img :src="preview" alt="" class="avatar" />
          <span class="hint">点击更换头像</span>
        </button>
        <input ref="avatarInput" type="file" accept="image/*" hidden @change="onFileChange" />
        <p class="username">账号 {{ auth.user?.username || '—' }}</p>
      </section>

      <label class="field">
        <span>昵称</span>
        <input v-model="nickname" type="text" maxlength="64" placeholder="聊天显示名" />
      </label>

      <p v-if="error" class="err">{{ error }}</p>
      <button type="button" class="save-btn" :disabled="saving" @click="submit">
        {{ saving ? '保存中…' : '保存资料' }}
      </button>

      <section class="block">
        <button type="button" class="link" @click="showPwd = !showPwd">
          {{ showPwd ? '收起改密' : '修改密码' }}
        </button>
        <div v-if="showPwd" class="pwd">
          <label class="field">
            <span>原密码</span>
            <input v-model="oldPwd" type="password" autocomplete="current-password" />
          </label>
          <label class="field">
            <span>新密码</span>
            <input v-model="newPwd" type="password" autocomplete="new-password" />
          </label>
          <label class="field">
            <span>确认新密码</span>
            <input v-model="newPwd2" type="password" autocomplete="new-password" />
          </label>
          <p v-if="pwdError" class="err">{{ pwdError }}</p>
          <p v-if="pwdOk" class="ok">{{ pwdOk }}</p>
          <button type="button" class="save-btn" :disabled="pwdSaving" @click="submitPassword">
            {{ pwdSaving ? '提交中…' : '确认改密' }}
          </button>
        </div>
      </section>

      <p class="tip">本站无偿学习分享；若觉有用，可自愿赞赏作者（入口稍后放这里）。</p>
      <button type="button" class="logout" @click="logout">退出登录</button>
    </div>

    <ImageCropModal
      v-if="cropOpen"
      :src="cropSrc"
      :aspect-ratio="cropOptions.aspectRatio"
      :title="cropOptions.title"
      :max-width="cropOptions.maxWidth"
      :max-height="cropOptions.maxHeight"
      @confirm="onCroppedAvatar"
      @cancel="onCropDismiss"
    />
  </div>
</template>

<style scoped>
.me-page {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #ededed;
}
.nav {
  flex-shrink: 0;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #ededed;
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
}
.title {
  margin: 0;
  font-size: 17px;
  font-weight: 600;
}
.scroll {
  flex: 1;
  overflow-y: auto;
  padding: 16px 16px 32px;
}
.hero {
  background: #fff;
  border-radius: 8px;
  padding: 20px 16px;
  text-align: center;
  margin-bottom: 12px;
}
.avatar-btn {
  border: none;
  background: none;
  cursor: pointer;
  padding: 0;
}
.avatar {
  width: 88px;
  height: 88px;
  border-radius: var(--wx-avatar-radius, 6px);
  object-fit: cover;
  border: 1px solid #e5e5e5;
}
.hint {
  display: block;
  margin-top: 8px;
  font-size: 12px;
  color: var(--wx-green, #07c160);
}
.username {
  margin: 10px 0 0;
  font-size: 13px;
  color: #888;
}
.field {
  display: block;
  background: #fff;
  border-radius: 8px;
  padding: 10px 12px;
  margin-bottom: 10px;
}
.field span {
  display: block;
  font-size: 12px;
  color: #888;
  margin-bottom: 4px;
}
.field input {
  width: 100%;
  border: none;
  outline: none;
  font-size: 15px;
  box-sizing: border-box;
}
.save-btn {
  width: 100%;
  border: none;
  border-radius: 8px;
  padding: 11px;
  background: #07c160;
  color: #fff;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  margin-bottom: 12px;
}
.save-btn:disabled {
  opacity: 0.6;
}
.block {
  background: #fff;
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 12px;
}
.link {
  border: none;
  background: none;
  color: #576b95;
  font-size: 14px;
  cursor: pointer;
  padding: 0;
}
.pwd {
  margin-top: 12px;
}
.err {
  color: #fa5151;
  font-size: 13px;
  margin: 0 0 8px;
}
.ok {
  color: #07c160;
  font-size: 13px;
  margin: 0 0 8px;
}
.tip {
  font-size: 12px;
  color: #999;
  line-height: 1.5;
  margin: 8px 0 12px;
}
.logout {
  width: 100%;
  border: 1px solid #fa5151;
  background: #fff;
  color: #fa5151;
  border-radius: 8px;
  padding: 11px;
  font-size: 15px;
  cursor: pointer;
}
</style>
