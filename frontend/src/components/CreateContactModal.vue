<script setup>
import { ref } from 'vue'
import ImageCropModal from './ImageCropModal.vue'
import { CROP_PRESET_AVATAR, useImageCrop } from '../composables/useImageCrop'
import { useChatStore } from '../stores/chat'

const emit = defineEmits(['close'])
const store = useChatStore()
const { cropOpen, cropSrc, cropOptions, handleCropConfirm, handleCropCancel, onImageSelected } =
  useImageCrop()

const name = ref('')
const persona = ref('')
const apiKey = ref('')
const avatarFile = ref(null)
const avatarPreview = ref(null)
const saving = ref(false)
const error = ref('')

function onAvatarChange(e) {
  onImageSelected(e, CROP_PRESET_AVATAR, (file) => {
    avatarFile.value = file
    avatarPreview.value = file ? URL.createObjectURL(file) : null
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
  if (!name.value.trim() || !apiKey.value.trim()) {
    error.value = '请填写姓名和 DeepSeek API Key'
    return
  }
  saving.value = true
  try {
    const contact = await store.addContact({
      name: name.value.trim(),
      persona: persona.value,
      api_key: apiKey.value.trim(),
    })
    if (avatarFile.value) {
      await store.setAvatar(contact.id, avatarFile.value)
    }
    emit('close')
  } catch (e) {
    error.value = e.response?.data?.detail || e.message || '创建失败'
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="qq-modal-mask" @click.self="emit('close')">
    <form class="qq-modal" autocomplete="off" @submit.prevent="submit">
      <h2>添加联系人</h2>
      <p class="sub">填写昵称、角色设定与 DeepSeek Key</p>

      <div v-if="avatarPreview" class="preview-row">
        <img :src="avatarPreview" alt="" class="preview-avatar" />
      </div>

      <label class="qq-field">
        <span>昵称</span>
        <input
          v-model="name"
          type="text"
          maxlength="64"
          placeholder="例如：小深"
          autocomplete="off"
          autocapitalize="off"
          name="new-contact-name"
        />
      </label>
      <label class="qq-field">
        <span>角色设定</span>
        <textarea
          v-model="persona"
          rows="10"
          maxlength="32000"
          placeholder="Ta 的性格、说话方式、背景故事…"
          autocomplete="off"
          name="new-contact-persona"
        />
      </label>
      <label class="qq-field">
        <span>DeepSeek API Key</span>
        <input
          v-model="apiKey"
          type="password"
          placeholder="sk-..."
          autocomplete="new-password"
          name="new-contact-api-key"
        />
      </label>
      <label class="qq-field">
        <span>头像（可选）</span>
        <input type="file" accept="image/*" @change="onAvatarChange" />
      </label>

      <p v-if="error" class="qq-err">{{ error }}</p>
      <div class="qq-modal-actions">
        <button type="button" class="qq-btn qq-btn-ghost" @click="emit('close')">取消</button>
        <button type="submit" class="qq-btn qq-btn-primary" :disabled="saving">
          {{ saving ? '创建中…' : '创建并开聊' }}
        </button>
      </div>
    </form>
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
.preview-row {
  display: flex;
  justify-content: center;
  margin-bottom: 12px;
}

.preview-avatar {
  width: 64px;
  height: 64px;
  border-radius: var(--wx-avatar-radius);
  object-fit: cover;
}
</style>
