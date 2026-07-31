import request from './request'
const cfg=()=>({headers:{}})
export const actionLoopApi={dashboard:async()=>(await request.get('/action-dashboard',cfg())).data,list:async()=>(await request.get('/actions',cfg())).data,create:async(data:any)=>(await request.post('/actions',data,cfg())).data,detail:async(id:string)=>(await request.get(`/actions/${id}`,cfg())).data,approve:async(id:string)=>(await request.post(`/actions/${id}/approve`,{},cfg())).data,start:async(id:string,key:string)=>(await request.post(`/actions/${id}/start`,null,{...cfg(),params:{idempotency_key:key}})).data}
