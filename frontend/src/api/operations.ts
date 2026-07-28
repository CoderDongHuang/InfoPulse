import request from './request'

export const operationsApi = {
  track: (event_name:string, route:string, properties:Record<string,string|number|boolean>={}) => request.post('/product-events',{event_name,route,properties}),
  feedback: (data:{category:string;rating:number;message:string}) => request.post('/feedback',data),
  analytics: async () => (await request.get('/admin/analytics/summary')).data,
  feedbackQueue: async () => (await request.get('/admin/feedback')).data,
  releases: async () => (await request.get('/admin/releases')).data,
  createRelease: (data:any) => request.post('/admin/releases',data),
}
