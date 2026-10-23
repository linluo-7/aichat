<script setup>
import { ref } from 'vue'
import ImageCropModal from './ImageCropModal.vue'
import { CROP_PRESET_AVATAR, useImageCrop } from '../composables/useImageCrop'
import { useProfileStore } from '../stores/profile'

const emit = defineEmits(['close'])
const profile = useProfileStore()
const { cropOpen, cropSrc, cropOptions, handleCropConfirm, handleCropCancel, onImageSelected } =
  useImageCrop()

const nickname = ref(profile.nickname)
const preview = ref(profile.displayAvatar)
const saving = ref(false)
const error = ref('')
const avatarInput = ref(null)
const avatarFile = ref(null)

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
</script>

<template>
  <div class="qq-modal-mask" @click.self="emit('close')">
    <div class="qq-modal profile-modal">
      <h2>我的资料</h2>
      <p class="sub">设置你在聊天里显示的头像和昵称</p>

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
</style>
