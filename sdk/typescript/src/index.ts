export class APIError extends Error{constructor(public status:number,public code:string,message:string,public requestId?:string){super(message)}}
export interface ClientOptions{apiKey:string;organizationId:string;workspaceId?:string;baseUrl?:string;timeoutMs?:number}
export class InfoPulseClient{
 private baseUrl:string
 constructor(private options:ClientOptions){if(!options.apiKey.startsWith('ipk_live_'))throw new Error('Invalid InfoPulse API key');this.baseUrl=(options.baseUrl??'https://api.infopulse.example/api/v1').replace(/\/$/,'')}
 async request<T>(method:string,path:string,{query,body,idempotencyKey}:{query?:Record<string,string|number|boolean|undefined>;body?:unknown;idempotencyKey?:string}={}):Promise<T>{
  const url=new URL(this.baseUrl+'/'+path.replace(/^\//,''));Object.entries(query??{}).forEach(([k,v])=>{if(v!==undefined)url.searchParams.set(k,String(v))});const headers:Record<string,string>={Authorization:`Bearer ${this.options.apiKey}`,'X-Organization-ID':this.options.organizationId,Accept:'application/json'}
  if(this.options.workspaceId)headers['X-Workspace-ID']=this.options.workspaceId;if(body!==undefined)headers['Content-Type']='application/json';if(idempotencyKey)headers['Idempotency-Key']=idempotencyKey
  const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),this.options.timeoutMs??15000)
  try{const response=await fetch(url,{method,headers,body:body===undefined?undefined:JSON.stringify(body),signal:controller.signal}),data=await response.json().catch(()=>({}));if(!response.ok){const detail=data.detail??data;throw new APIError(response.status,detail.code??'api_error',detail.message??String(detail),response.headers.get('X-Request-ID')??undefined)}return data as T}finally{clearTimeout(timer)}
 }
 page<T>(path:string,page=1,pageSize=20,query:Record<string,string|number|boolean|undefined>={}){return this.request<{items:T[];page:number;page_size:number;total:number}>('GET',path,{query:{...query,page,page_size:pageSize}})}
}
const encoder=new TextEncoder();function hex(buffer:ArrayBuffer){return[...new Uint8Array(buffer)].map(x=>x.toString(16).padStart(2,'0')).join('')}
export async function verifyWebhook(secret:string,timestamp:string,eventId:string,body:string|Uint8Array,signature:string,toleranceSeconds=300,now=Math.floor(Date.now()/1000)){
 const sent=Number(timestamp);if(!Number.isInteger(sent)||Math.abs(now-sent)>toleranceSeconds)return false;const key=await crypto.subtle.importKey('raw',encoder.encode(secret),{name:'HMAC',hash:'SHA-256'},false,['sign']),bytes=typeof body==='string'?encoder.encode(body):body,prefix=encoder.encode(`${timestamp}.${eventId}.`),payload=new Uint8Array(prefix.length+bytes.length);payload.set(prefix);payload.set(bytes,prefix.length)
 const expected=hex(await crypto.subtle.sign('HMAC',key,payload)),actual=signature.replace(/^sha256=/,'');if(expected.length!==actual.length)return false;let diff=0;for(let i=0;i<expected.length;i++)diff|=expected.charCodeAt(i)^actual.charCodeAt(i);return diff===0
}
