<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import { commentMoment, deleteMoment, listMoments, toggleMomentLike } from '../api/client'
import { hasMomentDraft } from '../utils/momentDraft'
import { formatShanghai } from '../utils/beijingTime'

const emit = defineEmits(['compose'])

const posts = ref([])
const loading = ref(false)
const error = ref('')
const replyDraft = ref({})
const rootDraft = ref({})
const pollTimer = ref(null)
const draftBadge = ref(hasMomentDraft())
/** 当前展开操作菜单的动态 id */
const openMenuId = ref(null)
/** 正在输入评论的动态 id */
const commentingId = ref(null)
const commentInputRefs = ref({})

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
    draftBadge.value = hasMomentDraft()
  } catch (e) {
    error.value = e.response?.data?.detail || e.message || '加载失败'
  } finally {
    loading.value = false
  }
}

defineExpose({ refresh })

async function removePost(post) {
  if (post.author_type !== 'user') return
  if (!confirm('删除这条朋友圈？')) return
  await deleteMoment(post.id)
  await refresh()
}

function rootComments(post) {
  return (post.comments || []).filter((c) => !c.parent_id)
}

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

function toggleMenu(postId) {
  openMenuId.value = openMenuId.value === postId ? null : postId
}

async function onLike(post) {
  openMenuId.value = null
  try {
    const res = await toggleMomentLike(post.id)
    post.liked_by_me = !!res.liked
    await refresh()
  } catch (e) {
    alert(e.response?.data?.detail || e.message || '点赞失败')
  }
}

async function startComment(post) {
  openMenuId.value = null
  commentingId.value = post.id
  if (!rootDraft.value[post.id]) rootDraft.value[post.id] = ''
  await nextTick()
  commentInputRefs.value[post.id]?.focus?.()
}

async function sendRootComment(post) {
  const text = (rootDraft.value[post.id] || '').trim()
  if (!text) return
  try {
    await commentMoment(post.id, text, null)
    rootDraft.value[post.id] = ''
    commentingId.value = null
    await refresh()
  } catch (e) {
    alert(e.response?.data?.detail || e.message || '评论失败')
  }
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

function onFeedClick() {
  openMenuId.value = null
}

onMounted(() => {
  refresh()
  pollTimer.value = setInterval(refresh, 15000)
})

onUnmounted(() => {
  if (pollTimer.value) clearInterval(pollTimer.value)
})
</script>

<template>
  <div class="moments-page">
    <header class="nav">
      <span class="nav-spacer" />
      <h1 class="title">朋友圈</h1>
      <button type="button" class="camera" title="发朋友圈" @click="emit('compose')">
        <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.8">
          <path d="M4 8h3l2-2h6l2 2h3v11H4V8z" stroke-linejoin="round" />
          <circle cx="12" cy="13" r="3.5" />
        </svg>
        <span v-if="draftBadge" class="draft-dot" title="有草稿" />
      </button>
    </header>

    <div class="feed" @click="onFeedClick">
      <p v-if="error" class="hint err">{{ error }}</p>
      <p v-else-if="loading && !posts.length" class="hint">加载中…</p>
      <p v-else-if="!posts.length" class="hint">还没有动态，点右上角相机发一条吧</p>
      <article v-for="post in posts" :key="post.id" class="post">
        <img :src="post.author_avatar || '/default-avatar.svg'" alt="" class="avatar" />
        <div class="body">
          <div class="head">
            <span class="name">{{ post.author_name }}</span>
            <button
              v-if="post.author_type === 'user'"
              type="button"
              class="del"
              @click.stop="removePost(post)"
            >
              删除
            </button>
          </div>
          <p v-if="post.content" class="text">{{ post.content }}</p>
          <div v-if="post.images?.length" class="imgs" :class="'n' + Math.min(post.images.length, 3)">
            <img v-for="img in post.images" :key="img.id" :src="img.url" alt="" />
          </div>

          <div class="meta-row">
            <span class="time">{{ fmtTime(post.created_at) }}</span>
            <div class="act-wrap" @click.stop>
              <div v-if="openMenuId === post.id" class="act-menu">
                <button type="button" class="act-item" @click="onLike(post)">
                  {{ post.liked_by_me ? '取消' : '赞' }}
                </button>
                <span class="act-split" />
                <button type="button" class="act-item" @click="startComment(post)">评论</button>
              </div>
              <button type="button" class="more-btn" aria-label="赞与评论" @click="toggleMenu(post.id)">
                <span class="dots">···</span>
              </button>
            </div>
          </div>

          <div
            v-if="post.likes?.length || post.comments?.length || commentingId === post.id"
            class="social"
          >
            <p v-if="post.likes?.length" class="likes">♥ {{ likeNames(post) }}</p>
            <div v-for="root in rootComments(post)" :key="root.id" class="cmt-block">
              <p class="cmt">
                <b>{{ root.author_name }}</b>：{{ root.content }}
              </p>
              <p v-for="ch in threadUnder(post, root)" :key="ch.id" class="cmt sub">
                <b>{{ ch.author_name }}</b>：{{ ch.content }}
              </p>
              <div v-if="root.author_type === 'contact'" class="reply-row">
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
            <div v-if="commentingId === post.id" class="reply-row root-row">
              <input
                :ref="(el) => { if (el) commentInputRefs[post.id] = el }"
                v-model="rootDraft[post.id]"
                type="text"
                maxlength="200"
                placeholder="评论…"
                @keyup.enter="sendRootComment(post)"
              />
              <button type="button" @click="sendRootComment(post)">发送</button>
            </div>
          </div>
          <p v-else-if="post.author_type === 'user'" class="pending">联系人正在赶来点赞评论…</p>
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
  flex-shrink: 0;
}
.nav-spacer {
  width: 36px;
}
.camera {
  position: relative;
  border: none;
  background: none;
  padding: 4px;
  cursor: pointer;
  color: #111;
  width: 36px;
  display: flex;
  justify-content: flex-end;
}
.draft-dot {
  position: absolute;
  top: 2px;
  right: 2px;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #fa5151;
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
.hint.err {
  color: #fa5151;
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
.meta-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 4px 0 8px;
  gap: 8px;
}
.time {
  font-size: 12px;
  color: #999;
}
.act-wrap {
  position: relative;
  display: flex;
  align-items: center;
}
.more-btn {
  border: none;
  background: #f7f7f7;
  border-radius: 4px;
  width: 32px;
  height: 22px;
  padding: 0;
  cursor: pointer;
  color: #576b95;
  display: flex;
  align-items: center;
  justify-content: center;
}
.dots {
  font-size: 16px;
  letter-spacing: 1px;
  line-height: 1;
  font-weight: 700;
}
.act-menu {
  position: absolute;
  right: 36px;
  top: 50%;
  transform: translateY(-50%);
  display: flex;
  align-items: center;
  background: #4c4c4c;
  border-radius: 4px;
  padding: 0 4px;
  z-index: 5;
  white-space: nowrap;
}
.act-item {
  border: none;
  background: none;
  color: #fff;
  font-size: 13px;
  padding: 8px 14px;
  cursor: pointer;
}
.act-split {
  width: 1px;
  height: 16px;
  background: rgba(255, 255, 255, 0.25);
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
.reply-row.root-row {
  margin-top: 8px;
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
</style>
