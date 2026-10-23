<script setup>
import { onMounted, ref } from 'vue'
import {
  clearMemories,
  consolidateMemories,
  createMemory,
  deleteMemory,
  getMemories,
  refreshDigest,
  updateMemory,
} from '../api/client'
import { formatShanghai } from '../utils/beijingTime'

const props = defineProps({
  contactId: { type: Number, required: true },
  contactName: { type: String, default: '' },
})

const emit = defineEmits(['back'])

const loading = ref(true)
const digest = ref('')
const digestAt = ref(null)
const profile = ref([])
const relationship = ref([])
const event = ref([])
const retired = ref([])
const state = ref({})
const error = ref('')
const showRetired = ref(false)
const showAdd = ref(false)
const addCategory = ref('profile')
const addContent = ref('')
const busy = ref(false)

async function load() {
  loading.value = true
  error.value = ''
  try {
    const data = await getMemories(props.contactId)
    digest.value = data.digest || ''
    digestAt.value = data.digest_at
    profile.value = data.profile || []
    relationship.value = data.relationship || []
    event.value = data.event || []
    retired.value = data.retired || []
    state.value = data.state || {}
  } catch (e) {
    error.value = e.response?.data?.detail || e.message || '加载失败'
  } finally {
    loading.value = false
  }
}

function fmt(iso) {
  if (!iso) return ''
  return formatShanghai(iso, {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
}

async function onRefreshDigest() {
  busy.value = true
  try {
    const data = await refreshDigest(props.contactId)
    digest.value = data.digest || ''
    digestAt.value = new Date().toISOString()
  } catch (e) {
    error.value = e.response?.data?.detail || e.message || '总结失败'
  } finally {
    busy.value = false
  }
}

async function onConsolidate() {
  busy.value = true
  try {
    await consolidateMemories(props.contactId)
    await load()
  } catch (e) {
    error.value = e.response?.data?.detail || e.message || '整理失败'
  } finally {
    busy.value = false
  }
}

async function onEdit(m) {
  const next = prompt('编辑记忆内容', m.content)
  if (next == null) return
  const text = next.trim()
  if (!text) return
  await updateMemory(m.id, { content: text })
  await load()
}

async function onTogglePin(m) {
  await updateMemory(m.id, { pinned: !m.pinned })
  await load()
}

async function onDelete(m) {
  if (!confirm('确定删除这条记忆？')) return
  await deleteMemory(m.id)
  await load()
}

async function onClear() {
  if (!confirm('确定清空全部记忆？此操作不可恢复。')) return
  await clearMemories(props.contactId)
  await load()
}

async function onAdd() {
  const content = addContent.value.trim()
  if (!content) return
  busy.value = true
  try {
    await createMemory(props.contactId, {
      category: addCategory.value,
      content,
      importance: 3,
    })
    addContent.value = ''
    showAdd.value = false
    await load()
  } catch (e) {
    error.value = e.response?.data?.detail || e.message || '添加失败'
  } finally {
    busy.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="memory-page">
    <header class="detail-nav">
      <button type="button" class="nav-back" aria-label="返回" @click="emit('back')">
        <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M15 18l-6-6 6-6" stroke-linecap="round" stroke-linejoin="round" />
        </svg>
      </button>
      <h1 class="nav-title">记忆</h1>
      <span class="nav-spacer" />
    </header>

    <div class="detail-scroll">
      <p v-if="loading" class="hint">加载中…</p>
      <p v-if="error" class="err">{{ error }}</p>

      <template v-if="!loading">
        <section class="digest-card">
          <div class="digest-head">
            <h2>{{ contactName || 'Ta' }}眼中的你</h2>
            <button type="button" class="link-btn" :disabled="busy" @click="onRefreshDigest">
              重新总结
            </button>
          </div>
          <p class="digest-body">{{ digest || '还没有总结' }}</p>
          <p v-if="digestAt" class="meta">更新于 {{ fmt(digestAt) }}</p>
        </section>

        <section v-for="group in [
          { key: 'profile', title: '关于你', list: profile },
          { key: 'relationship', title: '我们之间', list: relationship },
          { key: 'event', title: '往事', list: event },
        ]" :key="group.key" class="cell-group">
          <h3 class="group-title">{{ group.title }}</h3>
          <p v-if="!group.list.length" class="empty">暂无</p>
          <div v-for="m in group.list" :key="m.id" class="mem-row">
            <div class="mem-main">
              <span v-if="m.pinned" class="tag">置顶</span>
              <span v-if="!m.seen" class="tag new">新</span>
              <p class="mem-content">{{ m.content }}</p>
              <p class="meta">
                {{ m.source === 'user' ? '你添加的' : 'Ta 记住的' }}
                <template v-if="m.occurred_at"> · {{ m.occurred_at }}</template>
              </p>
            </div>
            <div class="mem-actions">
              <button type="button" @click="onTogglePin(m)">{{ m.pinned ? '取消置顶' : '置顶' }}</button>
              <button type="button" @click="onEdit(m)">编辑</button>
              <button type="button" class="danger" @click="onDelete(m)">删除</button>
            </div>
          </div>
        </section>

        <section class="cell-group">
          <button type="button" class="fold-btn" @click="showRetired = !showRetired">
            已更新的记忆 {{ showRetired ? '▾' : '▸' }}
          </button>
          <template v-if="showRetired">
            <p v-if="!retired.length" class="empty">暂无</p>
            <div v-for="m in retired" :key="m.id" class="mem-row retired">
              <p class="mem-content">{{ m.content }}</p>
              <p class="meta">已被替代</p>
            </div>
          </template>
        </section>

        <section class="actions">
          <button type="button" class="action-btn" @click="showAdd = !showAdd">手动添加</button>
          <button type="button" class="action-btn" :disabled="busy" @click="onConsolidate">
            立即整理
          </button>
          <button type="button" class="action-btn danger" @click="onClear">清空全部</button>
        </section>

        <div v-if="showAdd" class="add-box">
          <select v-model="addCategory">
            <option value="profile">关于你</option>
            <option value="relationship">我们之间</option>
            <option value="event">往事</option>
          </select>
          <textarea v-model="addContent" rows="3" maxlength="120" placeholder="输入记忆内容" />
          <button type="button" class="action-btn primary" :disabled="busy" @click="onAdd">添加</button>
        </div>

        <p class="meta foot">
          上次整理：{{ state.last_run_at ? fmt(state.last_run_at) : '尚未整理' }}
          <template v-if="state.last_error"> · 失败：{{ state.last_error }}</template>
        </p>
      </template>
    </div>
  </div>
</template>

<style scoped>
.memory-page {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  background: #ededed;
}
.detail-nav {
  display: flex;
  align-items: center;
  height: 48px;
  padding: 0 8px;
  background: #ededed;
  border-bottom: 1px solid #d9d9d9;
  flex-shrink: 0;
}
.nav-back {
  border: none;
  background: none;
  width: 40px;
  height: 40px;
  cursor: pointer;
}
.nav-title {
  flex: 1;
  text-align: center;
  font-size: 16px;
  font-weight: 500;
  margin: 0;
}
.nav-spacer {
  width: 40px;
}
.detail-scroll {
  flex: 1;
  overflow: auto;
  padding: 12px 12px 32px;
}
.digest-card,
.cell-group {
  background: #fff;
  border-radius: 8px;
  padding: 14px;
  margin-bottom: 12px;
}
.digest-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}
.digest-head h2,
.group-title {
  margin: 0 0 8px;
  font-size: 14px;
  font-weight: 600;
}
.digest-body {
  margin: 0;
  font-size: 14px;
  line-height: 1.55;
  color: #333;
}
.meta {
  margin: 6px 0 0;
  font-size: 12px;
  color: #999;
}
.link-btn {
  border: none;
  background: none;
  color: #07c160;
  font-size: 13px;
  cursor: pointer;
}
.mem-row {
  padding: 10px 0;
  border-top: 1px solid #f0f0f0;
}
.mem-row:first-of-type {
  border-top: none;
}
.mem-content {
  margin: 0;
  font-size: 14px;
  line-height: 1.45;
}
.mem-actions {
  display: flex;
  gap: 10px;
  margin-top: 6px;
}
.mem-actions button {
  border: none;
  background: none;
  color: #576b95;
  font-size: 12px;
  cursor: pointer;
  padding: 0;
}
.mem-actions .danger,
.action-btn.danger {
  color: #e64545;
}
.tag {
  display: inline-block;
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 4px;
  background: #f0f0f0;
  margin-right: 6px;
  color: #666;
}
.tag.new {
  background: #e8f8ef;
  color: #07c160;
}
.empty,
.hint {
  font-size: 13px;
  color: #999;
  margin: 0;
}
.err {
  color: #e64545;
  font-size: 13px;
}
.actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 8px;
}
.action-btn {
  height: 44px;
  border: none;
  border-radius: 8px;
  background: #fff;
  font-size: 15px;
  cursor: pointer;
}
.action-btn.primary {
  background: #07c160;
  color: #fff;
}
.fold-btn {
  border: none;
  background: none;
  font-size: 14px;
  font-weight: 600;
  padding: 0;
  cursor: pointer;
}
.retired .mem-content {
  color: #999;
  text-decoration: line-through;
}
.add-box {
  background: #fff;
  border-radius: 8px;
  padding: 12px;
  margin-top: 8px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.add-box select,
.add-box textarea {
  font-size: 14px;
  padding: 8px;
  border: 1px solid #ddd;
  border-radius: 6px;
}
.foot {
  text-align: center;
  margin-top: 16px;
}
</style>
