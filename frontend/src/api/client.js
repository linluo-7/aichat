import axios from 'axios'

const TOKEN_KEY = 'aichat_token'

/** 开发走 Vite 代理；生产由 Nginx 同域转发 /api */
const client = axios.create({
  baseURL: '',
  timeout: 120000,
})

client.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY)
  if (token) {
    config.headers = config.headers || {}
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

client.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      const url = err.config?.url || ''
      if (!url.includes('/api/auth/login') && !url.includes('/api/auth/register')) {
        localStorage.removeItem(TOKEN_KEY)
        if (!window.location.hash.includes('auth')) {
          window.dispatchEvent(new CustomEvent('aichat:unauthorized'))
        }
      }
    }
    return Promise.reject(err)
  },
)

export async function login(username, password) {
  const { data } = await client.post('/api/auth/login', { username, password })
  return data
}

export async function register(code, username, password) {
  const { data } = await client.post('/api/auth/register', { code, username, password })
  return data
}

export async function checkInvite(code) {
  const { data } = await client.post('/api/auth/invite/check', { code })
  return data
}

export async function getMe() {
  const { data } = await client.get('/api/auth/me')
  return data
}

export async function changePassword(old_password, new_password) {
  const { data } = await client.post('/api/auth/change-password', {
    old_password,
    new_password,
  })
  return data
}

export async function getProfile() {
  const { data } = await client.get('/api/profile')
  return data
}

export async function updateProfile(payload) {
  const { data } = await client.patch('/api/profile', payload)
  return data
}

export async function uploadMyAvatar(file) {
  const form = new FormData()
  form.append('file', file)
  const { data } = await client.post('/api/profile/avatar', form)
  return data
}

export async function listContacts() {
  const { data } = await client.get('/api/contacts')
  return data
}

export async function createContact(payload) {
  const { data } = await client.post('/api/contacts', payload)
  return data
}

export async function updateContact(id, payload) {
  const { data } = await client.patch(`/api/contacts/${id}`, payload)
  return data
}

export async function deleteContact(id) {
  await client.delete(`/api/contacts/${id}`)
}

export async function uploadAvatar(id, file) {
  const form = new FormData()
  form.append('file', file)
  const { data } = await client.post(`/api/contacts/${id}/avatar`, form)
  return data
}

/** @param {'desktop'|'mobile'} platform */
export async function uploadBackground(id, file, platform) {
  const form = new FormData()
  form.append('file', file)
  const { data } = await client.post(`/api/contacts/${id}/background/${platform}`, form)
  return data
}

/** @param {'desktop'|'mobile'} platform */
export async function clearBackground(id, platform) {
  const { data } = await client.delete(`/api/contacts/${id}/background/${platform}`)
  return data
}

/** 历史分页：返回 { messages, has_more } */
export async function listMessages(contactId, { beforeId, limit = 50 } = {}) {
  const params = { limit }
  if (beforeId != null) params.before_id = beforeId
  const { data } = await client.get(`/api/contacts/${contactId}/messages`, { params })
  return data
}

/** 发送文本消息 */
export async function postMessage(contactId, content) {
  const { data } = await client.post(`/api/contacts/${contactId}/messages`, { content })
  return data
}

/** 发送文件/图片 */
export async function postMessageFile(contactId, file) {
  const form = new FormData()
  form.append('file', file)
  const { data } = await client.post(`/api/contacts/${contactId}/messages/file`, form)
  return data
}

/** 增量同步 */
export async function syncAfter(afterId = 0) {
  const { data } = await client.get('/api/sync', { params: { after_id: afterId } })
  return data
}

export async function retryJob(jobId) {
  const { data } = await client.post(`/api/jobs/${jobId}/retry`)
  return data
}

export async function getMemories(contactId) {
  const { data } = await client.get(`/api/contacts/${contactId}/memories`)
  return data
}

export async function createMemory(contactId, payload) {
  const { data } = await client.post(`/api/contacts/${contactId}/memories`, payload)
  return data
}

export async function updateMemory(memoryId, payload) {
  const { data } = await client.patch(`/api/memories/${memoryId}`, payload)
  return data
}

export async function deleteMemory(memoryId) {
  await client.delete(`/api/memories/${memoryId}`)
}

export async function clearMemories(contactId) {
  const { data } = await client.delete(`/api/contacts/${contactId}/memories`)
  return data
}

export async function refreshDigest(contactId) {
  const { data } = await client.post(`/api/contacts/${contactId}/memories/digest`)
  return data
}

export async function consolidateMemories(contactId) {
  const { data } = await client.post(`/api/contacts/${contactId}/memories/consolidate`)
  return data
}

/** 朋友圈列表 */
export async function listMoments() {
  const { data } = await client.get('/api/moments')
  return data
}

/** 发朋友圈：content 文字 + files 图片数组 */
export async function createMoment(content, files = []) {
  const form = new FormData()
  form.append('content', content || '')
  for (const f of files) {
    form.append('files', f)
  }
  const { data } = await client.post('/api/moments', form)
  return data
}

export async function commentMoment(postId, content, parentId = null) {
  const { data } = await client.post(`/api/moments/${postId}/comments`, {
    content,
    parent_id: parentId,
  })
  return data
}

/** 切换点赞 */
export async function toggleMomentLike(postId) {
  const { data } = await client.post(`/api/moments/${postId}/like`)
  return data
}

export async function deleteMoment(postId) {
  await client.delete(`/api/moments/${postId}`)
}

export default client
