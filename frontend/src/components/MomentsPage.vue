<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import {
  commentMoment,
  createMoment,
  deleteMoment,
  listMoments,
} from '../api/client'
import { formatShanghai } from '../utils/beijingTime'

const emit = defineEmits(['back'])

const posts = ref([])
const loading = ref(false)
const error = ref('')
const composing = ref(false)
const draftText = ref('')
const draftFiles = ref([])
const draftPreviews = ref([])
const fileInput = ref(null)
const saving = ref(false)
const replyDraft = ref({}) // commentId -> text
const pollTimer = ref(null)

const likeNames = computed(() => (post) => (post.likes || []).map((l) => l.contact_name).join('、'))

function fmtTime(iso) {
  if (!iso) return ''
  return formatShanghai(iso, {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
}

async function refresh() {
  loading.value = true
  error.value = ''
  try {
    posts.value = await listMoments()
  } catch (e) {
    error.value = e.response?.data?.detail || e.message || '加载失败'
  } finally {
    loading.value = false
  }
}

function openCompose() {
  composing.value = true
  draftText.value = ''
  draftFiles.value = []
  draftPreviews.value = []
}

function pickImages() {
  fileInput.value?.click()
}

function onFiles(e) {
  const list = Array.from(e.target.files || [])
  e.target.value = ''
  const next = [...draftFiles.value, ...list].slice(0, 9)
  draftPreviews.value.forEach((u) => URL.revokeObjectURL(u))
  draftFiles.value = next
  draftPreviews.value = next.map((f) => URL.createObjectURL(f))
}

async function submitPost() {
  if (!draftText.value.trim() && !draftFiles.value.length) {
    error.value = '请填写文字或添加图片'
    return
  }
  saving.value = true
  error.value = ''
  try {
    await createMoment(draftText.value.trim(), draftFiles.value)
    composing.value = false
    await refresh()
  } catch (e) {
    error.value = e.response?.data?.detail || e.message || '发布失败'
  } finally {
    saving.value = false
  }
}

async function removePost(post) {
  if (post.author_type !== 'user') return
  if (!confirm('删除这条朋友圈？')) return
  await deleteMoment(post.id)
  await refresh()
}

function rootComments(post) {
  return (post.comments || []).filter((c) => !c.parent_id)
}

function childComments(post, parentId) {
  return (post.comments || []).filter((c) => c.parent_id === parentId)
}

/** 展开某条首评下的全部回复（含嵌套再回） */
function threadUnder(post, root) {
  const all = post.comments || []
  const out = []
  const walk = (pid) => {
    for (const c of all.filter((x) => x.parent_id === pid)) {
      out.push(c)
      walk(c.id)
    }
  }
  walk(root.id)
  return out
}

async function sendReply(post, parentComment) {
  const key = parentComment.id
  const text = (replyDraft.value[key] || '').trim()
  if (!text) return
  try {
    await commentMoment(post.id, text, parentComment.id)
    replyDraft.value[key] = ''
    await refresh()
  } catch (e) {
    alert(e.response?.data?.detail || e.message || '回复失败')
  }
}

onMounted(() => {
  refresh()
  pollTimer.value = setInterval(refresh, 15000)
})

onUnmounted(() => {
  if (pollTimer.value) clearInterval(pollTimer.value)
  draftPreviews.value.forEach((u) => URL.revokeObjectURL(u))
})
</script>

<template>
  <div class="moments-page">
    <header class="nav">
      <button type="button" class="back" aria-label="返回" @click="emit('back')">
        <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M15 18l-6-6 6-6" stroke-linecap="round" stroke-linejoin="round" />
        </svg>
      </button>
      <h1 class="title">朋友圈</h1>
      <button type="button" class="camera" title="发朋友圈" @click="openCompose">
        <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.8">
          <path d="M4 8h3l2-2h6l2 2h3v11H4V8z" stroke-linejoin="round" />
          <circle cx="12" cy="13" r="3.5" />
        </svg>
      </button>
    </header>

    <div v-if="composing" class="compose-mask" @click.self="composing = false">
      <div class="compose-card">
        <h2>发朋友圈</h2>
        <textarea v-model="draftText" rows="4" maxlength="500" placeholder="这一刻的想法…" />
        <div class="preview-grid">
          <img v-for="(u, i) in draftPreviews" :key="i" :src="u" alt="" />
          <button
            v-if="draftFiles.length < 9"
            type="button"
            class="add-img"
            @click="pickImages"
          >
            +
          </button>
        </div>
        <input ref="fileInput" type="file" accept="image/*" multiple hidden @change="onFiles" />
        <p v-if="error" class="err">{{ error }}</p>
        <div class="actions">
          <button type="button" class="ghost" @click="composing = false">取消</button>
          <button type="button" class="primary" :disabled="saving" @click="submitPost">
            {{ saving ? '发布中…' : '发表' }}
          </button>
        </div>
      </div>
    </div>

    <div class="feed">
      <p v-if="loading && !posts.length" class="hint">加载中…</p>
      <p v-else-if="!posts.length" class="hint">还没有动态，点右上角发一条吧</p>
      <article v-for="post in posts" :key="post.id" class="post">
        <img :src="post.author_avatar || '/default-avatar.svg'" alt="" class="avatar" />
        <div class="body">
          <div class="head">
            <span class="name">{{ post.author_name }}</span>
            <button
              v-if="post.author_type === 'user'"
              type="button"
              class="del"
              @click="removePost(post)"
            >
              删除
            </button>
          </div>
          <p v-if="post.content" class="text">{{ post.content }}</p>
          <div v-if="post.images?.length" class="imgs" :class="'n' + Math.min(post.images.length, 3)">
            <img v-for="img in post.images" :key="img.id" :src="img.url" alt="" />
          </div>
          <p class="time">{{ fmtTime(post.created_at) }}</p>
          <div v-if="post.likes?.length || post.comments?.length" class="social">
            <p v-if="post.likes?.length" class="likes">♥ {{ likeNames(post) }}</p>
            <div v-for="root in rootComments(post)" :key="root.id" class="cmt-block">
              <p class="cmt">
                <b>{{ root.author_name }}</b>：{{ root.content }}
              </p>
              <p
                v-for="ch in threadUnder(post, root)"
                :key="ch.id"
                class="cmt sub"
              >
                <b>{{ ch.author_name }}</b>：{{ ch.content }}
              </p>
              <div
                v-if="root.author_type === 'contact'"
                class="reply-row"
              >
                <input
                  v-model="replyDraft[root.id]"
                  type="text"
                  maxlength="200"
                  placeholder="回复…"
                  @keyup.enter="sendReply(post, root)"
                />
                <button type="button" @click="sendReply(post, root)">发送</button>
              </div>
            </div>
          </div>
          <p v-else class="pending">联系人正在赶来点赞评论…</p>
        </div>
      </article>
    </div>
  </div>
</template>

<style scoped>
.moments-page {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #ededed;
}
.nav {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  background: #ededed;
  border-bottom: 1px solid #ddd;
}
.back,
.camera {
  border: none;
  background: none;
  padding: 4px;
  cursor: pointer;
  color: #111;
}
.title {
  margin: 0;
  font-size: 17px;
  font-weight: 600;
}
.feed {
  flex: 1;
  overflow-y: auto;
  padding: 12px 0 24px;
}
.hint {
  text-align: center;
  color: #888;
  font-size: 13px;
  padding: 40px 16px;
}
.post {
  display: flex;
  gap: 10px;
  padding: 14px 16px;
  background: #fff;
  border-bottom: 1px solid #eee;
}
.avatar {
  width: 44px;
  height: 44px;
  border-radius: 6px;
  object-fit: cover;
  flex-shrink: 0;
}
.body {
  flex: 1;
  min-width: 0;
}
.head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.name {
  color: #576b95;
  font-weight: 600;
  font-size: 15px;
}
.del {
  border: none;
  background: none;
  color: #999;
  font-size: 12px;
  cursor: pointer;
}
.text {
  margin: 6px 0;
  font-size: 15px;
  line-height: 1.45;
  white-space: pre-wrap;
  word-break: break-word;
}
.imgs {
  display: grid;
  gap: 4px;
  margin: 8px 0;
  max-width: 260px;
}
.imgs.n1 {
  grid-template-columns: 1fr;
}
.imgs.n2,
.imgs.n3 {
  grid-template-columns: 1fr 1fr;
}
.imgs img {
  width: 100%;
  aspect-ratio: 1;
  object-fit: cover;
  border-radius: 4px;
  background: #f0f0f0;
}
.time {
  margin: 4px 0 8px;
  font-size: 12px;
  color: #999;
}
.social {
  background: #f7f7f7;
  border-radius: 4px;
  padding: 8px 10px;
  font-size: 13px;
}
.likes {
  margin: 0 0 6px;
  color: #576b95;
}
.cmt {
  margin: 0 0 4px;
  line-height: 1.4;
  word-break: break-word;
}
.cmt.sub {
  padding-left: 8px;
  color: #333;
}
.cmt b {
  color: #576b95;
  font-weight: 600;
}
.reply-row {
  display: flex;
  gap: 6px;
  margin-top: 6px;
}
.reply-row input {
  flex: 1;
  border: 1px solid #e5e5e5;
  border-radius: 4px;
  padding: 6px 8px;
  font-size: 13px;
}
.reply-row button {
  border: none;
  background: #07c160;
  color: #fff;
  border-radius: 4px;
  padding: 0 10px;
  font-size: 12px;
  cursor: pointer;
}
.pending {
  margin: 0;
  font-size: 12px;
  color: #aaa;
}
.compose-mask {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  z-index: 40;
  display: flex;
  align-items: flex-end;
  justify-content: center;
}
.compose-card {
  width: 100%;
  max-width: 520px;
  background: #fff;
  border-radius: 12px 12px 0 0;
  padding: 16px;
}
.compose-card h2 {
  margin: 0 0 10px;
  font-size: 16px;
}
.compose-card textarea {
  width: 100%;
  border: 1px solid #e5e5e5;
  border-radius: 8px;
  padding: 10px;
  font-size: 15px;
  resize: vertical;
  box-sizing: border-box;
}
.preview-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 12px 0;
}
.preview-grid img,
.add-img {
  width: 72px;
  height: 72px;
  border-radius: 6px;
  object-fit: cover;
}
.add-img {
  border: 1px dashed #ccc;
  background: #fafafa;
  font-size: 28px;
  color: #999;
  cursor: pointer;
}
.actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}
.ghost,
.primary {
  border: none;
  border-radius: 8px;
  padding: 8px 16px;
  font-size: 14px;
  cursor: pointer;
}
.ghost {
  background: #f0f0f0;
}
.primary {
  background: #07c160;
  color: #fff;
}
.err {
  color: #fa5151;
  font-size: 13px;
}
</style>
