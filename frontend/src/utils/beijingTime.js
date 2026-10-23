/** 解析 API 返回的时间（无偏移时按 UTC 处理） */
export function parseApiTime(iso) {
  if (!iso) return null
  const s = String(iso).trim()
  if (!s) return null
  if (/[zZ]$/.test(s) || /[+-]\d{2}:\d{2}$/.test(s)) {
    const d = new Date(s)
    return Number.isNaN(d.getTime()) ? null : d
  }
  const d = new Date(`${s}Z`)
  return Number.isNaN(d.getTime()) ? null : d
}

/** 北京时间下的 YYYY-MM-DD，用于今天/昨天判断 */
export function shanghaiDateKey(iso) {
  const d = parseApiTime(iso)
  if (!d) return ''
  return new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(d)
}

/** 格式化为北京时间 */
export function formatShanghai(iso, options = {}) {
  const d = parseApiTime(iso)
  if (!d) return ''
  return new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai',
    ...options,
  }).format(d)
}

const CHAT_TIME_GAP_MS = 5 * 60 * 1000

/** 是否在该条消息前显示时间条（首条或与上一条间隔超过 5 分钟） */
export function shouldShowChatTime(messages, index) {
  if (!messages?.length || index < 0 || index >= messages.length) return false
  const curr = messages[index]?.created_at
  if (!curr) return false
  if (index === 0) return true
  const prev = messages[index - 1]?.created_at
  if (!prev) return true
  const t0 = parseApiTime(prev)?.getTime()
  const t1 = parseApiTime(curr)?.getTime()
  if (!t0 || !t1) return true
  return t1 - t0 > CHAT_TIME_GAP_MS
}

/** 聊天页灰色时间条文案（北京时间） */
export function formatChatMessageTime(iso) {
  if (!iso) return ''
  const dayKey = shanghaiDateKey(iso)
  const nowKey = shanghaiDateKey(new Date().toISOString())
  const hm = formatShanghai(iso, { hour: '2-digit', minute: '2-digit', hour12: false })

  if (dayKey === nowKey) return hm

  const yesterday = new Date()
  yesterday.setDate(yesterday.getDate() - 1)
  if (dayKey === shanghaiDateKey(yesterday.toISOString())) {
    return `昨天 ${hm}`
  }

  const [y, m, d] = dayKey.split('-').map(Number)
  const [ny] = nowKey.split('-').map(Number)
  if (y === ny) {
    return `${m}月${d}日 ${hm}`
  }
  return `${y}年${m}月${d}日 ${hm}`
}
