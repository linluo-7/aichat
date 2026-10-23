<script setup>
import { onMounted, onUnmounted, ref, watch } from 'vue'
import { createMoment } from '../api/client'
import {
  clearMomentDraft,
  draftImageToFile,
  fileToDraftImage,
  loadMomentDraft,
  saveMomentDraft,
} from '../utils/momentDraft'

const emit = defineEmits(['back', 'published'])

const text = ref('')
/** @type {import('vue').Ref<Array<{ name: string, type: string, dataUrl: string }>>} */
const images = ref([])
const saving = ref(false)
const error = ref('')
const hydrated = ref(false)
/** 用户明确丢弃或已成功发布时，不再写草稿 */
const discardDraft = ref(false)

onMounted(() => {
  const draft = loadMomentDraft()
  if (draft) {
    text.value = draft.text || ''
    images.value = draft.images || []
  }
  hydrated.value = true
})

/** 编辑过程中自动落盘，意外退出也能恢复 */
watch([text, images], () => {
  if (!hydrated.value || discardDraft.value) return
  saveMomentDraft(text.value, images.value)
}, { deep: true })

onUnmounted(() => {
  if (discardDraft.value) return
  if (hydrated.value && (text.value.trim() || images.value.length)) {
    saveMomentDraft(text.value, images.value)
  }
})

async function onFiles(e) {
  const list = Array.from(e.target.files || [])
  e.target.value = ''
  if (!list.length) return
  const room = 9 - images.value.length
  const take = list.slice(0, room)
  try {
    const converted = await Promise.all(take.map((f) => fileToDraftImage(f)))
    images.value = [...images.value, ...converted]
  } catch (err) {
    error.value = err?.message || '读取图片失败'
  }
}

function removeImage(idx) {
  images.value = images.value.filter((_, i) => i !== idx)
}

/** 取消：有内容则询问是否保留草稿（微信同款文案） */
function onBack() {
  const dirty = !!(text.value.trim() || images.value.length)
  if (!dirty) {
    discardDraft.value = true
    clearMomentDraft()
    emit('back')
    return
  }
  const keep = window.confirm('保留此次编辑？')
  if (keep) {
    saveMomentDraft(text.value, images.value)
  } else {
    discardDraft.value = true
    clearMomentDraft()
  }
  emit('back')
}

async function submit() {
  if (!text.value.trim() && !images.value.length) {
    error.value = '请填写文字或添加图片'
    return
  }
  saving.value = true
  error.value = ''
  try {
    const files = await Promise.all(images.value.map((img) => draftImageToFile(img)))
    await createMoment(text.value.trim(), files)
    discardDraft.value = true
    clearMomentDraft()
    emit('published')
    emit('back')
  } catch (e) {
    error.value = e.response?.data?.detail || e.message || '发布失败'
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="compose-page">
    <header class="nav">
      <button type="button" class="nav-btn" @click="onBack">取消</button>
      <h1 class="title">发朋友圈</h1>
      <button type="button" class="nav-btn publish" :disabled="saving" @click="submit">
        {{ saving ? '…' : '发表' }}
      </button>
    </header>

    <div class="body">
      <textarea
        v-model="text"
        rows="8"
        maxlength="500"
        placeholder="这一刻的想法…"
      />
      <div class="grid">
        <div v-for="(img, i) in images" :key="i" class="cell">
          <img :src="img.dataUrl" alt="" />
          <button type="button" class="rm" aria-label="删除" @click="removeImage(i)">×</button>
        </div>
        <!-- 用 label + 透明 input，避免 hidden 在移动端无法唤起相册 -->
        <label v-if="images.length < 9" class="cell add" aria-label="添加图片">
          <span class="plus" aria-hidden="true">+</span>
          <input
            type="file"
            class="file-hit"
            accept="image/*"
            multiple
            @change="onFiles"
          />
        </label>
      </div>
      <p v-if="error" class="err">{{ error }}</p>
      <p class="hint">未发完可退出并保存草稿，下次进入自动恢复</p>
    </div>
  </div>
</template>

<style scoped>
.compose-page {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #fff;
}
.nav {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 48px;
  padding: 0 8px;
  border-bottom: 1px solid #eee;
  flex-shrink: 0;
}
.title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
}
.nav-btn {
  border: none;
  background: none;
  color: #576b95;
  font-size: 15px;
  padding: 8px 10px;
  cursor: pointer;
  min-width: 56px;
}
.nav-btn.publish {
  color: #fff;
  background: #07c160;
  border-radius: 4px;
  padding: 6px 12px;
  min-width: auto;
}
.nav-btn.publish:disabled {
  opacity: 0.6;
}
.body {
  flex: 1;
  overflow-y: auto;
  padding: 12px 16px 24px;
}
textarea {
  width: 100%;
  border: none;
  resize: none;
  font-size: 16px;
  line-height: 1.5;
  outline: none;
  box-sizing: border-box;
  min-height: 140px;
}
.grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
  margin-top: 12px;
  max-width: 320px;
}
.cell {
  position: relative;
  aspect-ratio: 1;
  border-radius: 4px;
  overflow: hidden;
  background: #f5f5f5;
}
.cell img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.cell.add {
  border: 1px dashed #ccc;
  background: #fafafa;
  color: #bbb;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}
.cell.add .plus {
  font-size: 32px;
  line-height: 1;
  pointer-events: none;
}
.cell.add .file-hit {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  opacity: 0;
  cursor: pointer;
  font-size: 0;
}
.rm {
  position: absolute;
  top: 2px;
  right: 2px;
  width: 22px;
  height: 22px;
  border: none;
  border-radius: 50%;
  background: rgba(0, 0, 0, 0.55);
  color: #fff;
  font-size: 14px;
  line-height: 1;
  cursor: pointer;
}
.err {
  color: #fa5151;
  font-size: 13px;
  margin-top: 12px;
}
.hint {
  margin-top: 16px;
  font-size: 12px;
  color: #999;
}
</style>
