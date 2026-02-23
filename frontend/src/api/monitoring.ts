import request from '@/utils/request'

export function getRealtimeMetrics() {
  return request.get('/monitoring/realtime')
}

export function getStatistics(days = 7) {
  return request.get('/monitoring/statistics', { params: { days } })
}

export function exportReport(startDate: string, endDate: string) {
  return request.get('/monitoring/export', {
    params: { start_date: startDate, end_date: endDate },
    responseType: 'blob',
  })
}
