<script setup>
import { computed, ref, watch } from 'vue'
import ImageCropModal from './ImageCropModal.vue'
import { CROP_PRESET_AVATAR, useImageCrop } from '../composables/useImageCrop'
import { useChatStore } from '../stores/chat'

const props = defineProps({
  contactId: { type: Number, required: true },
})

const emit = defineEmits(['close', 'saved'])

const store = useChatStore()
const { cropOpen, cropSrc, cropOptions, handleCropConfirm, handleCropCancel, onImageSelected } =
  useImageCrop()

const contact = computed(() => store.contacts.find((c) => c.id === props.contactId) || null)

const name = ref('')
const persona = ref('')
const apiKey = ref('')
const avatarFile = ref(null)
const avatarPreview = ref(null)
const autoMessageEnabled = ref(false)
const autoMessageInterval = ref(30)
const memoryEnabled = ref(true)
const saving = ref(false)
const error = ref('')

/** 打开时从当前联系人填充表单，不沿用上次编辑缓存 */
function resetForm() {
  const c = contact.value
  if (!c) return
  name.value = c.name
  persona.value = c.persona || ''
  apiKey.value = ''
  avatarFile.value = null
  avatarPreview.value = c.avatar_url || null
  autoMessageEnabled.value = !!c.auto_message_enabled
  autoMessageInterval.value = c.auto_message_interval_minutes || 30
  memoryEnabled.value = c.memory_enabled !== false
  error.value = ''
}

watch(
  () => props.contactId,
  () => resetForm(),
  { immediate: true },
)

function onAvatarChange(e) {
  onImageSelected(e, CROP_PRESET_AVATAR, (file) => {
    avatarFile.value = file
    avatarPreview.value = file
      ? URL.createObjectURL(file)
      : contact.value?.avatar_url || null
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
  if (!name.value.trim()) {
    error.value = '请填写昵称'
    return
  }
  const key = apiKey.value.trim()
  if (key && key.length < 8) {
    error.value = 'API Key 至少 8 位，或留空表示不修改'
    return
  }
  if (autoMessageEnabled.value) {
    const mins = Number(autoMessageInterval.value)
    if (!Number.isFinite(mins) || mins < 1) {
      error.value = '自动发消息间隔至少 1 分钟'
      return
    }
  }
  saving.value = true
  try {
    const payload = {
      name: name.value.trim(),
      persona: persona.value,
      memory_enabled: memoryEnabled.value,
      auto_message_enabled: autoMessageEnabled.value,
      auto_message_interval_minutes: autoMessageEnabled.value
        ? Math.min(10080, Math.max(1, Math.round(Number(autoMessageInterval.value))))
        : undefined,
    }
    if (key) payload.api_key = key
    await store.updateContact(props.contactId, payload)
    if (avatarFile.value) {
      await store.setAvatar(props.contactId, avatarFile.value)
    }
    emit('saved')
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
    <form class="qq-modal" autocomplete="off" @submit.prevent="submit">
      <h2>编辑资料</h2>
      <p class="sub">修改昵称、角色设定或 API Key</p>

      <div v-if="avatarPreview" class="preview-row">
        <img :src="avatarPreview" alt="" class="preview-avatar" />
      </div>

      <label class="qq-field">
        <span>昵称</span>
        <input
          v-model="name"
          type="text"
          maxlength="64"
          autocomplete="off"
          autocapitalize="off"
          name="edit-contact-name"
        />
      </label>
      <label class="qq-field">
        <span>角色设定</span>
        <textarea
          v-model="persona"
          rows="10"
          maxlength="32000"
          autocomplete="off"
          name="edit-contact-persona"
        />
      </label>
      <label class="qq-field">
        <span>DeepSeek API Key</span>
        <input
          v-model="apiKey"
          type="password"
          placeholder="留空则不修改"
          autocomplete="new-password"
          name="edit-contact-api-key"
        />
      </label>
      <label class="qq-field">
        <span>更换头像（可选）</span>
        <input type="file" accept="image/*" @change="onAvatarChange" />
      </label>

      <div class="auto-msg-block">
        <label class="switch-row">
          <span class="switch-label">记忆</span>
          <input v-model="memoryEnabled" type="checkbox" class="switch-input" />
        </label>
        <p class="auto-hint">开启后 Ta 会记住重要信息，可在资料页查看「记忆」</p>
      </div>

      <div class="auto-msg-block">
        <label class="switch-row">
          <span class="switch-label">自动发送消息</span>
          <input v-model="autoMessageEnabled" type="checkbox" class="switch-input" />
        </label>
        <p class="auto-hint">
          开启后，双方都安静满间隔时 Ta 会主动找你；你不回复时最多连发 3 次（服务端执行，无需保持页面打开）
        </p>
        <label v-if="autoMessageEnabled" class="qq-field interval-field">
          <span>间隔（分钟）</span>
          <input
            v-model.number="autoMessageInterval"
            type="number"
            min="1"
            max="10080"
            step="1"
            inputmode="numeric"
          />
        </label>
      </div>

      <p v-if="error" class="qq-err">{{ error }}</p>
      <div class="qq-modal-actions">
        <button type="button" class="qq-btn qq-btn-ghost" @click="emit('close')">取消</button>
        <button type="submit" class="qq-btn qq-btn-primary" :disabled="saving">
          {{ saving ? '保存中…' : '保存' }}
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
.sub {
  margin: 0 0 16px;
  font-size: 13px;
  color: var(--wx-text-secondary);
}

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

.auto-msg-block {
  margin: 8px 0 4px;
  padding: 12px;
  background: #f7f7f7;
  border-radius: 8px;
}

.switch-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  cursor: pointer;
}

.switch-label {
  font-size: 14px;
  font-weight: 500;
}

.switch-input {
  width: 18px;
  height: 18px;
  accent-color: var(--wx-green, #07c160);
}

.auto-hint {
  margin: 8px 0 0;
  font-size: 12px;
  color: var(--wx-text-secondary);
  line-height: 1.45;
}

.interval-field {
  margin-top: 10px;
  margin-bottom: 0;
}
</style>
