import http from './index'

export const notificationApi = {
  list: (params: { page?: number; page_size?: number; is_read?: boolean }) => http.get<any>('/notifications/', { params }),
  unreadCount: () => http.get<{ unread_count: number }>('/notifications/unread-count'),
  markRead: (id: number) => http.put<any>(`/notifications/${id}/read`),
  markAll: () => http.put<any>('/notifications/read-all'),
}
