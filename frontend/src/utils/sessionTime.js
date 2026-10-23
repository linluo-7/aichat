import { formatShanghai, parseApiTime, shanghaiDateKey } from './beijingTime'

/** 会话列表时间展示（仿微信，北京时间） */
export function formatSessionTime(iso) {
  const d = parseApiTime(iso)
  if (!d) return ''

  const nowKey = shanghaiDateKey(new Date().toISOString())
  const dayKey = shanghaiDateKey(iso)
  if (dayKey === nowKey) {
    return formatShanghai(iso, { hour: '2-digit', minute: '2-digit', hour12: false })
  }

  const yesterday = new Date()
  yesterday.setDate(yesterday.getDate() - 1)
  if (dayKey === shanghaiDateKey(yesterday.toISOString())) {
    return '昨天'
  }

  const parts = dayKey.split('-')
  const y = Number(parts[0])
  const m = Number(parts[1])
  const day = Number(parts[2])
  const nowParts = nowKey.split('-')
  const nowY = Number(nowParts[0])
  if (y === nowY) {
    return `${m}/${day}`
  }
  return `${y}/${m}/${day}`
}
