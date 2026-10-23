import { defineStore } from 'pinia'
import { getProfile, updateProfile, uploadMyAvatar } from '../api/client'

export const useProfileStore = defineStore('profile', {
  state: () => ({
    nickname: '我',
    avatar_url: null,
    loaded: false,
  }),
  getters: {
    displayAvatar(state) {
      return state.avatar_url || '/default-avatar.svg'
    },
  },
  actions: {
    async fetchProfile() {
      const data = await getProfile()
      this.nickname = data.nickname
      this.avatar_url = data.avatar_url
      this.loaded = true
    },
    async setNickname(nickname) {
      const data = await updateProfile({ nickname })
      this.nickname = data.nickname
      this.avatar_url = data.avatar_url
    },
    async setAvatar(file) {
      const data = await uploadMyAvatar(file)
      this.nickname = data.nickname
      this.avatar_url = data.avatar_url
    },
  },
})
