import { defineStore } from 'pinia'
import { notificationApi } from '@/api/notification'

export const useNotificationStore = defineStore('notification', {
  state: () => ({ items: [] as any[], unreadCount: 0 }),
  actions: {
    async fetchUnread() {
      try {
        const r = await notificationApi.unreadCount()
        this.unreadCount = r.unread_count
      } catch {
        /* ignore */
      }
    },
    async fetchList() {
      const r = await notificationApi.list({ page: 1, page_size: 8 })
      this.items = r.items || []
      this.unreadCount = r.unread_count || 0
    },
    async markRead(id: number) {
      await notificationApi.markRead(id)
      await this.fetchUnread()
    },
    async markAll() {
      await notificationApi.markAll()
      await this.fetchList()
    },
  },
})
