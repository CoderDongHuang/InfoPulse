import request from './request'

export const adaptiveOsApi = {
  overview: async () => (await request.get('/adaptive-os/overview')).data,
  rollout: async (data: any) => (await request.post('/adaptive-os/protocol-rollouts', data)).data,
  synthesizePolicy: async (data: any) => (await request.post('/adaptive-os/policy-syntheses', data)).data,
  runTwin: async (data: any) => (await request.post('/adaptive-os/digital-twins', data)).data,
  route: async (data: any) => (await request.post('/adaptive-os/sovereign-routes', data)).data,
}
