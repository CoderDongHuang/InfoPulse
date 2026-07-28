import request from "./request";
export const knowledgeApi = {
  capabilities: async () => (await request.get("/knowledge/capabilities")).data,
  bases: async () => (await request.get("/knowledge-bases")).data,
  create: async (data: any) =>
    (await request.post("/knowledge-bases", data)).data,
  remove: (id: string) => request.delete(`/knowledge-bases/${id}`),
  documents: async (id: string) =>
    (await request.get(`/knowledge-bases/${id}/documents`)).data,
  document: async (id: string) =>
    (await request.get(`/knowledge-documents/${id}`)).data,
  upload: async (id: string, files: File[]) => {
    const body = new FormData();
    files.forEach((x) => body.append("files", x));
    return (await request.post(`/knowledge-bases/${id}/documents`, body)).data;
  },
  importWeb: async (id: string, url: string) =>
    (await request.post(`/knowledge-bases/${id}/web-imports`, { url })).data,
  reindex: async (id: string) =>
    (await request.post(`/knowledge-documents/${id}/reindex`)).data,
  removeDocument: (id: string) => request.delete(`/knowledge-documents/${id}`),
  search: async (id: string, query: string) =>
    (
      await request.post(`/knowledge-bases/${id}/search-test`, {
        query,
        limit: 8,
      })
    ).data,
};
