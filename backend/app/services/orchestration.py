"""Durable, policy-bound agent workflow runtime."""
import asyncio, re, socket
from datetime import datetime,timedelta,timezone
from sqlalchemy import func,or_,select
from sqlalchemy.exc import IntegrityError

from app.config import get_settings
from app.core.database import _get_sessionmaker
from app.core.llm import complete_chat,llm_is_configured
from app.models.orchestration import AgentMemory,EvaluationDataset,EvaluationRun,ModelRoute,OrchestrationAudit,PromptDefinition,ToolDefinition,ToolPolicy,Workflow,WorkflowApproval,WorkflowRun,WorkflowStepRun,WorkflowTemplate,WorkflowVersion
from app.models.platform import ConnectorInstallation

UTC=timezone.utc
NODE_TYPES={"start","agent","tool","approval","condition","memory_read","memory_write","end"}
TERMINAL={"completed","failed","cancelled","rejected"}

def now():return datetime.now(UTC)

def validate_graph(graph:dict)->dict:
    nodes=graph.get("nodes");edges=graph.get("edges")
    if not isinstance(nodes,list) or not isinstance(edges,list) or not 2<=len(nodes)<=100:raise ValueError("graph requires 2-100 nodes and an edge list")
    ids=[x.get("id") for x in nodes]
    if any(not isinstance(x,str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,79}",x) for x in ids) or len(ids)!=len(set(ids)):raise ValueError("node ids must be unique stable identifiers")
    if sum(x.get("type")=="start" for x in nodes)!=1 or sum(x.get("type")=="end" for x in nodes)<1:raise ValueError("graph requires exactly one start and at least one end")
    if any(x.get("type") not in NODE_TYPES for x in nodes):raise ValueError("unsupported node type")
    known=set(ids);adj={x:[] for x in ids};incoming={x:0 for x in ids}
    for edge in edges:
        source,target=edge.get("source"),edge.get("target")
        if source not in known or target not in known or source==target:raise ValueError("edge references an invalid node")
        adj[source].append(target);incoming[target]+=1
    start=next(x["id"] for x in nodes if x["type"]=="start")
    reached=set();stack=[start]
    while stack:
        item=stack.pop()
        if item in reached:continue
        reached.add(item);stack.extend(adj[item])
    if reached!=known:raise ValueError("all nodes must be reachable from start")
    queue=[x for x in ids if incoming[x]==0];visited=[]
    while queue:
        item=queue.pop();visited.append(item)
        for target in adj[item]:
            incoming[target]-=1
            if incoming[target]==0:queue.append(target)
    if len(visited)!=len(ids):raise ValueError("workflow graph must be acyclic")
    for node in nodes:
        cfg=node.get("config",{})
        if node["type"]=="tool" and not cfg.get("tool_key"):raise ValueError("tool nodes require tool_key")
        if node["type"]=="agent" and not cfg.get("prompt_key"):raise ValueError("agent nodes require prompt_key")
    return {"nodes":nodes,"edges":edges}

def audit(db,org,action,run_id=None,actor_id=None,details=None):db.add(OrchestrationAudit(organization_id=org,run_id=run_id,actor_id=actor_id,action=action,details=details or {}))

async def seed_catalog(db,organization_id):
    builtins=(("memory.read","Read workflow memory","low",None,"memory.read"),("memory.write","Write workflow memory","medium",None,"memory.write"),("connector.notify","Send approved connector notification","high","slack","notify"))
    for key,name,risk,connector,action in builtins:
        if not await db.scalar(select(ToolDefinition.id).where(ToolDefinition.organization_id==organization_id,ToolDefinition.key==key)):db.add(ToolDefinition(organization_id=organization_id,key=key,name=name,risk_level=risk,connector_key=connector,action=action,input_schema={"type":"object"}))
    await db.flush()

def next_node(graph,current,node_output):
    edges=[x for x in graph["edges"] if x["source"]==current]
    if not edges:return None
    selected=[x for x in edges if x.get("condition") in (None,"always")]
    for edge in edges:
        condition=edge.get("condition")
        if condition=="true" and bool(node_output.get("result")):return edge["target"]
        if condition=="false" and not bool(node_output.get("result")):return edge["target"]
    return (selected or edges)[0]["target"]

async def model_output(db,run,node):
    cfg=node.get("config",{});prompt=await db.scalar(select(PromptDefinition).where(PromptDefinition.organization_id==run.organization_id,PromptDefinition.key==cfg["prompt_key"],PromptDefinition.status=="active").order_by(PromptDefinition.version.desc()))
    if not prompt:raise RuntimeError("active prompt not found")
    route=await db.scalar(select(ModelRoute).where(ModelRoute.organization_id==run.organization_id,ModelRoute.workspace_id==run.workspace_id,ModelRoute.task_type==cfg.get("task_type","general"),ModelRoute.enabled.is_(True)))
    if not route:raise RuntimeError("model route not configured")
    estimated=min(route.max_cost_cents,int(cfg.get("estimated_cost_cents",route.max_cost_cents)))
    if run.spent_cents+estimated>run.budget_cents:raise RuntimeError("workflow cost budget exceeded")
    values={**run.input,**run.output};message=str(cfg.get("message","Execute the workflow step."))
    for key,value in values.items():message=message.replace("{{"+key+"}}",str(value))
    selected=route.primary_model
    if llm_is_configured():
        last_error=None
        for candidate in [route.primary_model,*route.fallback_models]:
            try:text=await complete_chat(prompt.system_prompt,message,max_tokens=route.max_tokens,model=candidate);selected=candidate;break
            except Exception as exc:last_error=exc
        else:raise RuntimeError(f"all approved model routes failed: {last_error}")
    else:text=f"Model route {route.primary_model} accepted the step without a configured LLM."
    run.spent_cents+=estimated
    return {"text":text,"model":selected,"prompt":f"{prompt.key}:v{prompt.version}","cost_cents":estimated}

async def tool_guard(db,run,node,step):
    cfg=node.get("config",{});tool=await db.scalar(select(ToolDefinition).where(ToolDefinition.organization_id==run.organization_id,ToolDefinition.key==cfg["tool_key"],ToolDefinition.enabled.is_(True)))
    if not tool:raise RuntimeError("tool is unavailable")
    policy=await db.scalar(select(ToolPolicy).where(ToolPolicy.organization_id==run.organization_id,ToolPolicy.workspace_id==run.workspace_id,ToolPolicy.tool_id==tool.id))
    if not policy or policy.effect!="allow":raise RuntimeError("tool policy denied the action")
    calls=int(await db.scalar(select(func.count()).select_from(WorkflowStepRun).where(WorkflowStepRun.run_id==run.id,WorkflowStepRun.node_type=="tool",WorkflowStepRun.status=="completed")) or 0)
    if calls>=policy.max_calls_per_run:raise RuntimeError("tool call limit exceeded")
    if tool.connector_key:
        install=await db.scalar(select(ConnectorInstallation).where(ConnectorInstallation.organization_id==run.organization_id,ConnectorInstallation.workspace_id==run.workspace_id,ConnectorInstallation.connector_key==tool.connector_key,ConnectorInstallation.status=="approved",ConnectorInstallation.revoked_at.is_(None)))
        if not install:raise RuntimeError("approved connector installation required")
    approval=await db.scalar(select(WorkflowApproval).join(WorkflowStepRun,WorkflowStepRun.id==WorkflowApproval.step_run_id).where(WorkflowApproval.run_id==run.id,WorkflowStepRun.node_id==step.node_id).order_by(WorkflowApproval.created_at.desc()))
    if policy.require_approval or tool.risk_level in {"high","critical"}:
        if not approval:
            approval=WorkflowApproval(organization_id=run.organization_id,run_id=run.id,step_run_id=step.id,risk_summary=f"{tool.risk_level} risk tool: {tool.name}",requested_action={"tool":tool.key,"action":tool.action,"input":cfg.get("input",{})},requested_by=run.user_id);db.add(approval);run.status="waiting_approval";step.status="waiting_approval";audit(db,run.organization_id,"approval.requested",run.id,run.user_id,{"tool":tool.key});return None
        if approval.status=="pending":run.status="waiting_approval";step.status="waiting_approval";return None
        if approval.status!="approved":raise RuntimeError("tool action rejected")
    # External side effects are handed to a connector worker with no credential material in the run log.
    return {"tool":tool.key,"action":tool.action,"dispatch":"queued" if tool.connector_key else "completed","input":cfg.get("input",{})}

async def execute_one(db,run,worker_id="inline"):
    if run.status in TERMINAL or run.status=="waiting_approval":return run
    version=await db.get(WorkflowVersion,run.version_id);graph=version.graph;nodes={x["id"]:x for x in graph["nodes"]}
    if not run.current_node_id:run.current_node_id=next(x["id"] for x in graph["nodes"] if x["type"]=="start")
    node=nodes[run.current_node_id];attempt=int(await db.scalar(select(func.max(WorkflowStepRun.attempt)).where(WorkflowStepRun.run_id==run.id,WorkflowStepRun.node_id==node["id"])) or 0)+1
    step=WorkflowStepRun(organization_id=run.organization_id,run_id=run.id,node_id=node["id"],node_type=node["type"],attempt=attempt,input={"run":run.input,"config":node.get("config",{})});db.add(step);await db.flush()
    run.status="running";run.started_at=run.started_at or now();output={}
    try:
        if node["type"]=="agent":output=await model_output(db,run,node)
        elif node["type"]=="tool":
            output=await tool_guard(db,run,node,step)
            if output is None:return run
        elif node["type"]=="approval":
            prior=await db.scalar(select(WorkflowApproval).join(WorkflowStepRun,WorkflowStepRun.id==WorkflowApproval.step_run_id).where(WorkflowApproval.run_id==run.id,WorkflowStepRun.node_id==node["id"]).order_by(WorkflowApproval.created_at.desc()))
            if prior and prior.status=="approved":output={"approved":True,"approval_id":prior.id}
            else:
                approval=WorkflowApproval(organization_id=run.organization_id,run_id=run.id,step_run_id=step.id,risk_summary=node.get("config",{}).get("summary","Human review required"),requested_action=node.get("config",{}),requested_by=run.user_id);db.add(approval);step.status="waiting_approval";run.status="waiting_approval";return run
        elif node["type"]=="condition":output={"result":bool(run.output.get(node.get("config",{}).get("field")))}
        elif node["type"]=="memory_read":
            cfg=node.get("config",{});memory=await db.scalar(select(AgentMemory).where(AgentMemory.organization_id==run.organization_id,AgentMemory.workspace_id==run.workspace_id,AgentMemory.user_id==run.user_id,AgentMemory.namespace==cfg.get("namespace","workflow"),AgentMemory.key==cfg.get("key"),AgentMemory.deleted_at.is_(None),or_(AgentMemory.expires_at.is_(None),AgentMemory.expires_at>now())))
            output={"value":memory.value if memory else None}
        elif node["type"]=="memory_write":
            cfg=node.get("config",{});key=cfg.get("key",node["id"]);memory=await db.scalar(select(AgentMemory).where(AgentMemory.organization_id==run.organization_id,AgentMemory.workspace_id==run.workspace_id,AgentMemory.user_id==run.user_id,AgentMemory.namespace==cfg.get("namespace","workflow"),AgentMemory.key==key))
            if memory:memory.value=cfg.get("value",run.output);memory.deleted_at=None
            else:db.add(AgentMemory(organization_id=run.organization_id,workspace_id=run.workspace_id,user_id=run.user_id,run_id=run.id,namespace=cfg.get("namespace","workflow"),key=key,value=cfg.get("value",run.output)))
            output={"stored":True,"key":key}
        elif node["type"]=="end":output={"completed":True}
        step.output=output;step.status="completed";step.completed_at=now();run.output={**run.output,node["id"]:output};audit(db,run.organization_id,"step.completed",run.id,None,{"node_id":node["id"],"type":node["type"]})
        following=next_node(graph,node["id"],output)
        if node["type"]=="end" or not following:run.status="completed";run.completed_at=now();run.current_node_id=None;audit(db,run.organization_id,"run.completed",run.id)
        else:run.current_node_id=following;run.status="queued"
    except Exception as exc:
        step.status="failed";step.error=str(exc)[:2000];step.completed_at=now();run.status="failed";run.completed_at=now();audit(db,run.organization_id,"run.failed",run.id,None,{"error":step.error,"node_id":node["id"]})
    finally:run.lease_owner=None;run.lease_until=None
    return run

async def claim_run(db,worker_id):
    at=now();row=await db.scalar(select(WorkflowRun).where(WorkflowRun.status=="queued",or_(WorkflowRun.lease_until.is_(None),WorkflowRun.lease_until<at)).order_by(WorkflowRun.created_at).with_for_update(skip_locked=True))
    if row:row.lease_owner=worker_id;row.lease_until=at+timedelta(minutes=5);await db.flush()
    return row

async def orchestration_worker_loop(stop):
    worker=f"{socket.gethostname()}:{id(stop)}"
    while not stop.is_set():
        async with _get_sessionmaker()() as db:
            run=await claim_run(db,worker)
            if run:await execute_one(db,run,worker);await db.commit()
        try:await asyncio.wait_for(stop.wait(),timeout=2)
        except asyncio.TimeoutError:pass

async def evaluate(db,dataset,version):
    results=[]
    node_tools={x.get("config",{}).get("tool_key") for x in version.graph["nodes"] if x["type"]=="tool"}
    for case in dataset.cases:
        forbidden=set(case.get("forbidden_tools",[]));ok=not bool(forbidden&node_tools);results.append({"name":case["name"],"passed":ok,"checks":{"forbidden_tools":sorted(forbidden&node_tools)}})
    score=sum(x["passed"] for x in results)/len(results);threshold=float(dataset.thresholds.get("minimum_score",.8))
    row=EvaluationRun(organization_id=dataset.organization_id,dataset_id=dataset.id,workflow_version_id=version.id,status="completed",score=score,passed=score>=threshold,results=results,completed_at=now());db.add(row);await db.flush();return row
