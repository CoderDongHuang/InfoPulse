import request from './request'
const tenantKey='infopulse-enterprise-context'
function config(){let v:any={};try{v=JSON.parse(sessionStorage.getItem(tenantKey)||'{}')}catch{}return{headers:{...(v.organizationId?{'X-Organization-ID':v.organizationId}:{}),...(v.workspaceId?{'X-Workspace-ID':v.workspaceId}:{})}}}
export const platformApi={
 overview:async()=>(await request.get('/platform/overview',config())).data,
 keys:async()=>(await request.get('/platform/api-keys',config())).data,createKey:async(data:any)=>(await request.post('/platform/api-keys',data,config())).data,revokeKey:(id:string)=>request.delete(`/platform/api-keys/${id}`,config()),
 apps:async()=>(await request.get('/platform/oauth/apps',config())).data,createApp:async(data:any)=>(await request.post('/platform/oauth/apps',data,config())).data,reviewApp:(id:string,data:any)=>request.post(`/platform/oauth/apps/${id}/review`,data,config()),revokeApp:(id:string)=>request.delete(`/platform/oauth/apps/${id}`,config()),
 webhooks:async()=>(await request.get('/platform/webhooks',config())).data,createWebhook:async(data:any)=>(await request.post('/platform/webhooks',data,config())).data,testWebhook:async(id:string)=>(await request.post(`/platform/webhooks/${id}/test`,{},config())).data,deliveries:async()=>(await request.get('/platform/webhooks/deliveries',config())).data,replay:(id:string)=>request.post(`/platform/webhooks/deliveries/${id}/replay`,{},config()),
 marketplace:async()=>(await request.get('/platform/marketplace',config())).data,installations:async()=>(await request.get('/platform/installations',config())).data,install:async(data:any)=>(await request.post('/platform/installations',data,config())).data,reviewInstall:(id:string,data:any)=>request.post(`/platform/installations/${id}/review`,data,config()),revokeInstall:(id:string)=>request.delete(`/platform/installations/${id}`,config()),
 usage:async()=>(await request.get('/platform/usage',config())).data,sandbox:async(data:any)=>(await request.post('/platform/sandbox',data,config())).data,
}
