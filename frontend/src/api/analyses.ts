import { createSSEConnection } from "@/utils/sse";
import { useUserStore } from "@/stores/user";
import request from "./request";
export const analysisApi = {
  stream: (body: any, callbacks: any) =>
    createSSEConnection("/api/v1/analyses/stream", {
      body,
      headers: { Authorization: `Bearer ${useUserStore().token}` },
      callbacks,
    }),
  detail: async (id: string) => (await request.get(`/analyses/${id}`)).data,
  regenerate: async (id: string, instruction = "") =>
    (await request.post(`/analyses/${id}/regenerate`, { instruction })).data,
};
