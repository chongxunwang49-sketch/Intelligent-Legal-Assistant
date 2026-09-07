import http from './index'

export const userApi = {
  list: (params: any) => http.get<any>('/users', { params }),
  roles: () => http.get<any[]>('/users/roles'),
  create: (data: any) => http.post<any>('/users', data),
  setRoles: (id: number, role_codes: string[]) => http.put<any>(`/users/${id}/roles`, { role_codes }),
  setStatus: (id: number, is_active: boolean) => http.put<any>(`/users/${id}/status`, { is_active }),
  update: (id: number, data: any) => http.put<any>(`/users/${id}`, data),
  remove: (id: number) => http.delete<any>(`/users/${id}`),
  resetPwd: (id: number, new_password: string) => http.post<any>(`/users/${id}/reset-password`, { new_password }),
}
