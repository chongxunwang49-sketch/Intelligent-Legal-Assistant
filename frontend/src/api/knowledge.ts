import http from './index'

export const knowledgeApi = {
  documents: (params: any) => http.get<any>('/knowledge/documents', { params }),
  upload: (file: File, doc_type = '法律') => {
    const fd = new FormData()
    fd.append('file', file)
    fd.append('doc_type', doc_type)
    return http.post<any>('/knowledge/upload', fd, { headers: { 'Content-Type': 'multipart/form-data' } })
  },
  search: (data: any) => http.post<any>('/knowledge/search', data),
  stats: () => http.get<any>('/knowledge/stats'),
  detail: (id: number) => http.get<any>(`/knowledge/documents/${id}`),
  content: (id: number) => http.get<any>(`/knowledge/documents/${id}/content`),
  remove: (id: number) => http.delete<any>(`/knowledge/documents/${id}`),
}
