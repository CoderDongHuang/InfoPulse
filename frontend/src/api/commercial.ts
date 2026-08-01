import request from './request'
export const commercialApi={
 overview:async()=>(await request.get('/commercial/overview')).data,
 templates:async()=>(await request.get('/commercial/templates')).data,
 createTemplate:async(data:any)=>(await request.post('/commercial/templates',data)).data,
 versions:async(id:string)=>(await request.get(`/commercial/templates/${id}/versions`)).data,
 rollback:async(id:string,version:number)=>(await request.post(`/commercial/templates/${id}/rollback/${version}`)).data,
 flows:async()=>(await request.get('/commercial/approval-flows')).data,
 createFlow:async(data:any)=>(await request.post('/commercial/approval-flows',data)).data,
 costReport:async()=>(await request.get('/commercial/cost-report')).data,
 saveSla:async(data:any)=>(await request.post('/commercial/sla-policies',data)).data,
 saveEntitlement:async(data:any)=>(await request.put('/commercial/entitlement',data)).data,
}
