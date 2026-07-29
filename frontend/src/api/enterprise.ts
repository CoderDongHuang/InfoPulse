import request from './request'

export type TenantContext = {organization:{id:string;name:string;slug:string;data_region:string};membership:{role_key:string};permissions:string[];workspaces:Array<{id:string;name:string;slug:string;status:string}>}
const key='infopulse-enterprise-context'
export function selectTenant(organizationId:string,workspaceId?:string){sessionStorage.setItem(key,JSON.stringify({organizationId,workspaceId}))}
function config(){let value:any={};try{value=JSON.parse(sessionStorage.getItem(key)||'{}')}catch{}return{headers:{...(value.organizationId?{'X-Organization-ID':value.organizationId}:{}),...(value.workspaceId?{'X-Workspace-ID':value.workspaceId}:{})}}}

export const enterpriseApi={
 context:async()=>(await request.get('/enterprise/context',config())).data as TenantContext,
 members:async()=>(await request.get('/enterprise/members',config())).data,addMember:(data:any)=>request.post('/enterprise/members',data,config()),
 roles:async()=>(await request.get('/enterprise/roles',config())).data,createRole:(data:any)=>request.post('/enterprise/roles',data,config()),createTeam:(data:any)=>request.post('/enterprise/teams',data,config()),
 providers:async()=>(await request.get('/enterprise/identity-providers',config())).data,createProvider:(data:any)=>request.post('/enterprise/identity-providers',data,config()),rotateScim:async(id:string)=>(await request.post(`/enterprise/identity-providers/${id}/scim-token`,{},config())).data,
 approvals:async()=>(await request.get('/enterprise/approvals',config())).data,requestApproval:(data:any)=>request.post('/enterprise/approvals',data,config()),decide:(id:string,data:any)=>request.post(`/enterprise/approvals/${id}/decision`,data,config()),
 policy:async()=>(await request.get('/enterprise/policy',config())).data,updatePolicy:(data:any)=>request.put('/enterprise/policy',data,config()),
 quota:async()=>(await request.get('/enterprise/quota',config())).data,updateQuota:(data:any)=>request.put('/enterprise/quota',data,config()),operations:async()=>(await request.get('/enterprise/operations',config())).data,
 createLegalHold:(data:any)=>request.post('/enterprise/legal-holds',data,config()),
 auditExport:async()=>{const response=await request.get('/enterprise/audit-export',{...config(),responseType:'blob'});const url=URL.createObjectURL(response.data);const anchor=document.createElement('a');anchor.href=url;anchor.download='tenant-audit.json';anchor.click();URL.revokeObjectURL(url)},
}
