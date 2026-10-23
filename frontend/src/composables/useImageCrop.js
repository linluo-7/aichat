import { ref } from 'vue'

/** 头像：1:1 正方形裁剪 */
export const CROP_PRESET_AVATAR = {
  aspectRatio: 1,
  title: '裁剪头像',
  maxWidth: 512,
  maxHeight: 512,
}

/** 电脑端聊天背景：宽屏比例 */
export const CROP_PRESET_BACKGROUND_DESKTOP = {
  aspectRatio: 16 / 9,
  title: '裁剪电脑端背景',
  maxWidth: 1920,
  maxHeight: 1080,
  portraitCrop: false,
}

/** 手机端聊天背景：竖屏比例，与聊天窗口一致 */
export const CROP_PRESET_BACKGROUND_MOBILE = {
  aspectRatio: 9 / 16,
  title: '裁剪手机端背景',
  maxWidth: 1080,
  maxHeight: 1920,
  portraitCrop: true,
}

/**
 * 选图后打开裁剪弹层，确认后回调裁剪后的 File。
 */
export function useImageCrop() {
  const cropOpen = ref(false)
  const cropSrc = ref('')
  const cropOptions = ref({ ...CROP_PRESET_AVATAR })

  let onResult = null

  function cleanupSrc() {
    if (cropSrc.value) {
      URL.revokeObjectURL(cropSrc.value)
      cropSrc.value = ''
    }
  }

  /** 进入裁剪流程 */
  function startCrop(file, options, callback) {
    if (!file?.type?.startsWith('image/')) {
      callback?.(null)
      return
    }
    cleanupSrc()
    cropOptions.value = { ...CROP_PRESET_AVATAR, ...options }
    cropSrc.value = URL.createObjectURL(file)
    cropOpen.value = true
    onResult = callback
  }

  function finish(result) {
    cropOpen.value = false
    const cb = onResult
    onResult = null
    cleanupSrc()
    cb?.(result)
  }

  function handleCropConfirm(file) {
    finish(file)
  }

  function handleCropCancel() {
    finish(null)
  }

  /**
   * 绑定到 `<input type="file">` 的 change 事件。
   * @param {Event} e
   * @param {object} options 裁剪参数
   * @param {(file: File | null) => void} callback
   */
  function onImageSelected(e, options, callback) {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file) return
    startCrop(file, options, callback)
  }

  return {
    cropOpen,
    cropSrc,
    cropOptions,
    handleCropConfirm,
    handleCropCancel,
    onImageSelected,
  }
}
