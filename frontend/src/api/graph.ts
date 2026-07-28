import request from "./request";
export const graphApi = {
  event: async (id: string) => (await request.get(`/events/${id}`)).data,
  graph: async (id: string) => (await request.get(`/events/${id}/graph`)).data,
  buildGraph: async (id: string) =>
    (await request.post(`/events/${id}/graph/build`, { max_nodes: 80 })).data,
  similar: async (id: string) =>
    (await request.get(`/events/${id}/similar`)).data,
  propagation: async (id: string) =>
    (await request.get(`/events/${id}/propagation`)).data,
  buildPropagation: async (id: string) =>
    (await request.post(`/events/${id}/propagation/build`, { max_nodes: 80 }))
      .data,
  quality: async (id: string) =>
    (await request.get(`/events/${id}/graph/quality`)).data,
  audits: async (id: string) =>
    (await request.get(`/events/${id}/graph/audit-logs`)).data,
  addEntity: (id: string, data: any) =>
    request.post(`/events/${id}/entities`, data),
  mergeEntity: (id: string, data: any) =>
    request.post(`/events/${id}/entities/merge`, data),
  addRelation: (id: string, data: any) =>
    request.post(`/events/${id}/relations`, data),
  correctEdge: (eventId: string, edgeId: string, data: any) =>
    request.patch(`/events/${eventId}/propagation/edges/${edgeId}`, data),
};
