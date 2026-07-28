import request from './request'
import{createSSEConnection}from'@/utils/sse'
import{useUserStore}from'@/stores/user'
export const agentApi={list:async()=>(await request.get('/conversations')).data,create:async(data:any)=>(await request.post('/conversations',data)).data,detail:async(id:string)=>(await request.get(`/conversations/${id}`)).data,remove:(id:string)=>request.delete(`/conversations/${id}`),feedback:(cid:string,mid:string,rating:string)=>(request.post(`/conversations/${cid}/messages/${mid}/feedback`,{rating,reason:''})),send:(cid:string,body:any,onEvent:(t:string,d:any)=>void)=>createSSEConnection(`/api/v1/conversations/${cid}/messages`,{body,headers:{Authorization:`Bearer ${useUserStore().token}`},callbacks:{onEvent}})}
