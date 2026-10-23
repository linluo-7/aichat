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
const avatarPreview = ref('/default-avatar.svg')
const avatarInput = ref(null)
const saving = ref(false)
const error = ref('')

/** 点击顶部头像打开文件选择 */
function pickAvatar() {
  avatarInput.value?.click()
}

function onAvatarChange(e) {
  onImageSelected(e, CROP_PRESET_AVATAR, (file) => {
    avatarFile.value = file
    avatarPreview.value = file ? URL.createObjectURL(file) : '/default-avatar.svg'
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
    <form class="qq-modal create-modal" autocomplete="off" @submit.prevent="submit">
      <h2>添加联系人</h2>
      <p class="sub">填写昵称、角色设定与 DeepSeek Key</p>

      <div class="avatar-block">
        <button type="button" class="avatar-btn" @click="pickAvatar">
          <img :src="avatarPreview" alt="" class="avatar-lg" />
          <span class="avatar-hint">点击设置头像</span>
        </button>
        <input
          ref="avatarInput"
          type="file"
          accept="image/*"
          hidden
          @change="onAvatarChange"
        />
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
.create-modal {
  width: min(440px, 92vw);
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
  background: #f5f5f5;
}

.avatar-hint {
  font-size: 12px;
  color: var(--wx-green);
}
</style>
