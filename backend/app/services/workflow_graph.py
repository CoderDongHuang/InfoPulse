"""Pure workflow graph validation and branch selection.

This module deliberately has no database, worker or model-provider dependencies.
"""
import re

NODE_TYPES = {"start", "agent", "tool", "approval", "condition", "memory_read", "memory_write", "end"}
EDGE_CONDITIONS = {"always", "default", "true", "false"}


def validate_graph(graph: dict) -> dict:
    if not isinstance(graph, dict):
        raise ValueError("graph must be an object")
    nodes, edges = graph.get("nodes"), graph.get("edges")
    if not isinstance(nodes, list) or not isinstance(edges, list) or not 2 <= len(nodes) <= 100:
        raise ValueError("graph requires 2-100 nodes and an edge list")
    if any(not isinstance(item, dict) for item in nodes + edges):
        raise ValueError("nodes and edges must be objects")
    ids = [node.get("id") for node in nodes]
    if any(not isinstance(key, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,79}", key) for key in ids) or len(ids) != len(set(ids)):
        raise ValueError("node ids must be unique stable identifiers")
    if sum(node.get("type") == "start" for node in nodes) != 1 or not any(node.get("type") == "end" for node in nodes):
        raise ValueError("graph requires exactly one start and at least one end")
    if any(not isinstance(node.get("type"), str) or node["type"] not in NODE_TYPES for node in nodes):
        raise ValueError("unsupported node type")

    known = set(ids)
    adjacency = {key: [] for key in ids}
    incoming = {key: 0 for key in ids}
    outgoing = {key: [] for key in ids}
    for edge in edges:
        source, target = edge.get("source"), edge.get("target")
        if not isinstance(source, str) or not isinstance(target, str) or source not in known or target not in known or source == target:
            raise ValueError("edge references an invalid node")
        adjacency[source].append(target)
        outgoing[source].append(edge)
        incoming[target] += 1

    start = next(node["id"] for node in nodes if node["type"] == "start")
    reached, stack = set(), [start]
    while stack:
        item = stack.pop()
        if item not in reached:
            reached.add(item)
            stack.extend(adjacency[item])
    if reached != known:
        raise ValueError("all nodes must be reachable from start")

    # Kahn's algorithm catches cycles without recursion or mutating the graph.
    queue = [key for key in ids if incoming[key] == 0]
    visited = 0
    while queue:
        item = queue.pop()
        visited += 1
        for target in adjacency[item]:
            incoming[target] -= 1
            if incoming[target] == 0:
                queue.append(target)
    if visited != len(ids):
        raise ValueError("workflow graph must be acyclic")

    for node in nodes:
        config = node.get("config", {})
        if not isinstance(config, dict):
            raise ValueError("node config must be an object")
        branches = outgoing[node["id"]]
        labels = [edge.get("condition", "always") or "always" for edge in branches]
        if any(not isinstance(label, str) or label not in EDGE_CONDITIONS for label in labels):
            raise ValueError("unsupported edge condition")
        if len(labels) != len(set(labels)) or ("always" in labels and len(labels) > 1):
            raise ValueError("ambiguous outgoing edges; parallel execution is not supported")
        if node["type"] == "end" and branches:
            raise ValueError("end nodes cannot have outgoing edges")
        if node["type"] != "end" and not branches:
            raise ValueError("non-end nodes must have outgoing edges")
        if node["type"] == "tool" and not config.get("tool_key"):
            raise ValueError("tool nodes require tool_key")
        if node["type"] == "agent" and not config.get("prompt_key"):
            raise ValueError("agent nodes require prompt_key")
    return {"nodes": nodes, "edges": edges}


def next_node(graph: dict, current: str, node_output: dict):
    edges = [edge for edge in graph["edges"] if edge["source"] == current]
    if not edges:
        return None
    for edge in edges:
        condition = edge.get("condition")
        if condition == "true" and bool(node_output.get("result")):
            return edge["target"]
        if condition == "false" and not bool(node_output.get("result")):
            return edge["target"]
    for edge in edges:
        if edge.get("condition") in (None, "always", "default"):
            return edge["target"]
    raise ValueError("No outgoing condition matched; add an explicit default edge")
