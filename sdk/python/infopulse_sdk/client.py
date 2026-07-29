import hashlib, hmac, json, time
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

class APIError(Exception):
    def __init__(self, status:int, code:str, message:str, request_id:str|None=None):
        super().__init__(message); self.status=status; self.code=code; self.request_id=request_id

@dataclass(frozen=True)
class Page:
    items:list[dict[str,Any]]; page:int; page_size:int; total:int

class Client:
    def __init__(self, api_key:str, organization_id:str, workspace_id:str|None=None, base_url:str="https://api.infopulse.example/api/v1", timeout:float=15):
        if not api_key.startswith("ipk_live_"): raise ValueError("api_key must be an InfoPulse developer key")
        self.api_key,self.organization_id,self.workspace_id=api_key,organization_id,workspace_id; self.base_url=base_url.rstrip("/"); self.timeout=timeout
    def request(self, method:str, path:str, *, query:dict|None=None, json_body:dict|None=None, idempotency_key:str|None=None)->Any:
        url=self.base_url+"/"+path.lstrip("/")
        if query: url+="?"+urlencode({k:v for k,v in query.items() if v is not None})
        body=json.dumps(json_body).encode() if json_body is not None else None
        headers={"Authorization":f"Bearer {self.api_key}","X-Organization-ID":self.organization_id,"Accept":"application/json"}
        if self.workspace_id: headers["X-Workspace-ID"]=self.workspace_id
        if body is not None: headers["Content-Type"]="application/json"
        if idempotency_key: headers["Idempotency-Key"]=idempotency_key
        try:
            with urlopen(Request(url,data=body,headers=headers,method=method.upper()),timeout=self.timeout) as response: return json.loads(response.read() or b"null")
        except HTTPError as exc:
            payload=json.loads(exc.read() or b"{}"); detail=payload.get("detail",payload)
            code,message=(detail.get("code","api_error"),detail.get("message",str(detail))) if isinstance(detail,dict) else ("api_error",str(detail))
            raise APIError(exc.code,code,message,exc.headers.get("X-Request-ID")) from exc
    def page(self,path:str,*,page:int=1,page_size:int=20,query:dict|None=None)->Page:
        data=self.request("GET",path,query={**(query or {}),"page":page,"page_size":page_size}); return Page(data.get("items",[]),data.get("page",page),data.get("page_size",page_size),data.get("total",0))

def verify_webhook(secret:str,timestamp:str,event_id:str,body:bytes,signature:str,tolerance_seconds:int=300,now:int|None=None)->bool:
    try: sent_at=int(timestamp)
    except ValueError: return False
    if abs((now or int(time.time()))-sent_at)>tolerance_seconds:return False
    expected=hmac.new(secret.encode(),timestamp.encode()+b"."+event_id.encode()+b"."+body,hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected,signature.removeprefix("sha256="))
