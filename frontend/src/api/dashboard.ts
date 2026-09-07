import http from './index'

export const dashboardApi = {
  overview: () => http.get<any>('/dashboard/overview'),
  recent: (params?: any) => http.get<any>('/dashboard/recent-activities', { params }),
  domains: (params?: any) => http.get<any>('/dashboard/domain-distribution', { params }),
  trends: (params?: any) => http.get<any>('/dashboard/trends', { params }),
  graphKnowledge: (params?: any) => http.get<any>('/graph/knowledge', { params }),
  graphStats: () => http.get<any>('/graph/stats'),
  graphRebuild: () => http.post<any>('/graph/rebuild'),
  lawVersions: (params: { at_date: string; keyword?: string }) => http.get<any>('/graph/law-versions', { params }),
}
