import http from './index'

export const contractApi = {
  upload: (file: File) => {
    const fd = new FormData()
    fd.append('file', file)
    return http.post<any>('/contract/upload', fd, { headers: { 'Content-Type': 'multipart/form-data' }, timeout: 300000 })
  },
  review: (contract_id: number, contract_type?: string) =>
    http.post<any>('/contract/review', { contract_id, contract_type }, { timeout: 300000 }),
  optimize: (contract_id: number) => http.post<any>('/contract/optimize', { contract_id }, { timeout: 180000 }),
  report: (id: number) => http.get<any>(`/contract/report/${id}`),
  history: (params?: any) => http.get<any>('/contract/history', { params }),
  detail: (id: number) => http.get<any>(`/contract/${id}`),
  remove: (id: number) => http.delete<any>(`/contract/${id}`),
  updateType: (id: number, contract_type: string) => http.patch<any>(`/contract/${id}/type`, { contract_type }),
}
