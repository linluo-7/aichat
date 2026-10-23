<script setup>
import { ref } from 'vue'
import ImageCropModal from './ImageCropModal.vue'
import { CROP_PRESET_AVATAR, useImageCrop } from '../composables/useImageCrop'
import { useAuthStore } from '../stores/auth'
import { useChatStore } from '../stores/chat'
import { useProfileStore } from '../stores/profile'

const emit = defineEmits(['close'])
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
    }
    emit('close')
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
  emit('close')
}
</script>

<template>
  <div class="qq-modal-mask" @click.self="emit('close')">
    <div class="qq-modal profile-modal">
      <h2>我的资料</h2>
      <p class="sub">
        账号 {{ auth.user?.username || '—' }} · 设置头像和昵称
      </p>

      <div class="avatar-block">
        <button type="button" class="avatar-btn" @click="pickAvatar">
          <img :src="preview" alt="" class="avatar-lg" />
          <span class="avatar-hint">点击更换头像</span>
        </button>
        <input ref="avatarInput" type="file" accept="image/*" hidden @change="onFileChange" />
      </div>

      <label class="qq-field">
        <span>昵称</span>
        <input v-model="nickname" type="text" maxlength="64" placeholder="我的昵称" />
      </label>

      <p v-if="error" class="qq-err">{{ error }}</p>
      <div class="qq-modal-actions">
        <button type="button" class="qq-btn qq-btn-ghost" @click="emit('close')">取消</button>
        <button type="button" class="qq-btn qq-btn-primary" :disabled="saving" @click="submit">
          {{ saving ? '保存中…' : '保存' }}
        </button>
      </div>

      <div class="extra-block">
        <button type="button" class="text-btn" @click="showPwd = !showPwd">
          {{ showPwd ? '收起改密' : '修改密码' }}
        </button>
        <div v-if="showPwd" class="pwd-form">
          <label class="qq-field">
            <span>原密码</span>
            <input v-model="oldPwd" type="password" autocomplete="current-password" />
          </label>
          <label class="qq-field">
            <span>新密码</span>
            <input v-model="newPwd" type="password" autocomplete="new-password" />
          </label>
          <label class="qq-field">
            <span>确认新密码</span>
            <input v-model="newPwd2" type="password" autocomplete="new-password" />
          </label>
          <p v-if="pwdError" class="qq-err">{{ pwdError }}</p>
          <p v-if="pwdOk" class="ok">{{ pwdOk }}</p>
          <button
            type="button"
            class="qq-btn qq-btn-primary"
            :disabled="pwdSaving"
            @click="submitPassword"
          >
            {{ pwdSaving ? '提交中…' : '确认改密' }}
          </button>
        </div>
      </div>

      <p class="tip">本站无偿学习分享；若觉有用，可自愿赞赏作者（入口稍后放这里）。</p>

      <button type="button" class="logout-btn" @click="logout">退出登录</button>
    </div>
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
</template>

<style scoped>
.profile-modal {
  width: min(400px, 92vw);
  max-height: 90vh;
  overflow-y: auto;
}

.avatar-block {
  display: flex;
  justify-content: center;
  margin-bottom: 18px;
}

.avatar-btn {
  border: none;
  background: none;
  padding: 0;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.avatar-lg {
  width: 88px;
  height: 88px;
  border-radius: var(--wx-avatar-radius);
  object-fit: cover;
  border: 1px solid var(--wx-border);
}

.avatar-hint {
  font-size: 12px;
  color: var(--wx-green);
}

.extra-block {
  margin-top: 18px;
  padding-top: 14px;
  border-top: 1px solid var(--wx-border);
}

.text-btn {
  border: none;
  background: none;
  color: #576b95;
  cursor: pointer;
  padding: 0;
  font-size: 14px;
}

.pwd-form {
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.ok {
  margin: 0 0 8px;
  font-size: 13px;
  color: var(--wx-green);
}

.tip {
  margin: 16px 0 8px;
  font-size: 12px;
  color: #999;
  line-height: 1.5;
}

.logout-btn {
  width: 100%;
  margin-top: 8px;
  border: 1px solid #fa5151;
  background: #fff;
  color: #fa5151;
  border-radius: 8px;
  padding: 10px;
  font-size: 14px;
  cursor: pointer;
}
</style>
