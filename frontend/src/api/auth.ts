import http from './index'

export interface UserInfo {
  id: number
  username: string
  email: string
  phone?: string
  avatar?: string
  is_superuser: boolean
  is_active: boolean
  roles: { id: number; code: string; name: string }[]
  permission_codes: string[]
}

export interface TokenResp {
  access_token: string
  refresh_token: string
  token_type: string
  user: UserInfo
}

export const authApi = {
  login: (username: string, password: string) => http.post<TokenResp>('/auth/login', { username, password }),
  register: (data: { username: string; email: string; password: string; phone?: string }) =>
    http.post<TokenResp>('/auth/register', data),
  refresh: (refresh_token: string) => http.post<any>('/auth/refresh', { refresh_token }),
  me: () => http.get<UserInfo>('/auth/me'),
  updateMe: (data: { email?: string; phone?: string }) => http.put<UserInfo>('/auth/me', data),
  uploadAvatar: (file: File) => {
    const fd = new FormData()
    fd.append('file', file)
    return http.post<UserInfo>('/auth/avatar', fd, { headers: { 'Content-Type': 'multipart/form-data' } })
  },
  deleteAvatar: () => http.delete<UserInfo>('/auth/avatar'),
  changePassword: (old_password: string, new_password: string) =>
    http.put<any>('/auth/password', { old_password, new_password }),
}
