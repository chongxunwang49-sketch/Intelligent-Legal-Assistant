import http from './index'

export const analysisApi = {
  hotTopics: (params?: any) => http.get<any>('/analysis/hot-topics', { params }),
  citations: (params?: any) => http.get<any>('/analysis/citations', { params }),
  clusters: (params?: any) => http.get<any>('/analysis/user-clusters', { params }),
  trends: (params?: any) => http.get<any>('/analysis/trends', { params }),
  overview: (params?: any) => http.get<any>('/analysis/overview', { params }),
}
