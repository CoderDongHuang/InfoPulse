import request from './request'

export const globalCoordinationApi = {
  overview: async () => (await request.get('/global-coordination/overview')).data,
  createNode: async (data: any) => (await request.post('/global-coordination/nodes', data)).data,
  verifyProof: async (data: any) => (await request.post('/global-coordination/proofs', data)).data,
  createRisk: async (data: any) => (await request.post('/global-coordination/risks', data)).data,
  observeControl: async (data: any) => (await request.post('/global-coordination/controls/observe', data)).data,
  createRoom: async (data: any) => (await request.post('/global-coordination/crisis-rooms', data)).data,
}
