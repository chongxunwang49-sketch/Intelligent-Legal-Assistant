import { defineStore } from 'pinia'
import { authApi, type UserInfo } from '@/api/auth'
import { TOKEN_KEY, REFRESH_KEY } from '@/api/index'

export const useUserStore = defineStore('user', {
  state: () => ({
    token: localStorage.getItem(TOKEN_KEY) || '',
    userInfo: null as UserInfo | null,
  }),
  getters: {
    isLoggedIn: (s) => !!s.token,
    roleCodes: (s) => (s.userInfo?.roles || []).map((r) => r.code),
    isAdmin: (s) => s.userInfo?.is_superuser === true,
    isLawyer: (s) => !!s.userInfo && (s.userInfo.is_superuser || s.userInfo.roles.some((r) => r.code === 'legal_admin')),
    hasRole: (s) => (codes: string[]) => codes.some((c) => c === 'admin' || (s.userInfo?.roles || []).some((r) => r.code === c) || (c === 'legal_admin' && s.isLawyer)),
    canAnalysis: (s) => s.isAdmin || s.isLawyer,
  },
  actions: {
    setTokens(access: string, refresh: string) {
      this.token = access
      localStorage.setItem(TOKEN_KEY, access)
      localStorage.setItem(REFRESH_KEY, refresh)
    },
    async login(username: string, password: string) {
      const resp = await authApi.login(username, password)
      this.setTokens(resp.access_token, resp.refresh_token)
      this.userInfo = resp.user
    },
    async register(data: any) {
      const resp = await authApi.register(data)
      this.setTokens(resp.access_token, resp.refresh_token)
      this.userInfo = resp.user
    },
    async fetchUserInfo() {
      this.userInfo = await authApi.me()
    },
    async logout() {
      this.token = ''
      this.userInfo = null
      localStorage.removeItem(TOKEN_KEY)
      localStorage.removeItem(REFRESH_KEY)
    },
    async updateProfile(data: { email?: string; phone?: string }) {
      this.userInfo = await authApi.updateMe(data)
    },
    async changePassword(old_password: string, new_password: string) {
      await authApi.changePassword(old_password, new_password)
    },
  },
})
