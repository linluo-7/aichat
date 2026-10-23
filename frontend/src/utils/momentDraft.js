/** 朋友圈草稿：文字 + 图片（dataURL）存 localStorage */

const KEY = 'aichat_moment_draft'

/**
 * @returns {{ text: string, images: Array<{ name: string, type: string, dataUrl: string }> } | null}
 */
export function loadMomentDraft() {
  try {
    const raw = localStorage.getItem(KEY)
    if (!raw) return null
    const data = JSON.parse(raw)
    if (!data || typeof data !== 'object') return null
    return {
      text: typeof data.text === 'string' ? data.text : '',
      images: Array.isArray(data.images) ? data.images.slice(0, 9) : [],
    }
  } catch {
    return null
  }
}

/** 保存草稿 */
export function saveMomentDraft(text, images) {
  const payload = {
    text: text || '',
    images: (images || []).slice(0, 9),
  }
  if (!payload.text.trim() && !payload.images.length) {
    clearMomentDraft()
    return
  }
  localStorage.setItem(KEY, JSON.stringify(payload))
}

export function clearMomentDraft() {
  localStorage.removeItem(KEY)
}

export function hasMomentDraft() {
  const d = loadMomentDraft()
  return !!(d && (d.text.trim() || d.images.length))
}

/** File -> { name, type, dataUrl } */
export function fileToDraftImage(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => {
      resolve({
        name: file.name || 'image.jpg',
        type: file.type || 'image/jpeg',
        dataUrl: String(reader.result || ''),
      })
    }
    reader.onerror = () => reject(reader.error)
    reader.readAsDataURL(file)
  })
}

/** draft image -> File */
export async function draftImageToFile(img) {
  const res = await fetch(img.dataUrl)
  const blob = await res.blob()
  return new File([blob], img.name || 'image.jpg', { type: img.type || blob.type || 'image/jpeg' })
}
