"""Tool-call dependency DAG construction, cycle detection, and critical path analysis."""

from collections import defaultdict
from typing import Dict, List, Set, Tuple
from app.models.schemas import DAGEdge, DAGNode, TraceDAGResponse


class DAGBuilder:
    """Builds and analyzes the directed execution graph of agent steps and tool calls."""

    @classmethod
    def build_dag(cls, trace_id: str, spans: List[Dict[str, any]]) -> TraceDAGResponse:
        """Construct full execution DAG with cycle detection and critical path metrics."""
        nodes: List[DAGNode] = []
        edges: List[DAGEdge] = []
        span_by_id: Dict[str, Dict[str, any]] = {}
        children_map: Dict[str, List[str]] = defaultdict(list)
        parent_map: Dict[str, str] = {}
        in_degree: Dict[str, int] = defaultdict(int)
        out_degree: Dict[str, int] = defaultdict(int)

        for s in spans:
            s_id = str(s.get("span_id"))
            span_by_id[s_id] = s

        # 1. Create Nodes
        for s in spans:
            s_id = str(s.get("span_id"))
            parent_id = str(s.get("parent_span_id")) if s.get("parent_span_id") else None

            node = DAGNode(
                id=s_id,
                label=s.get("span_name", "step"),
                span_type=str(s.get("span_type", "agent_step")),
                status=str(s.get("status", "success")),
                step_index=int(s.get("step_index", 0)),
                latency_ms=float(s.get("latency_ms", 0.0)),
                cost_usd=float(s.get("cost_usd", 0.0)),
                error_message=s.get("error_message") or None,
                is_root=parent_id is None or parent_id not in span_by_id,
                is_leaf=True  # updated later
            )
            nodes.append(node)

        def add_edge(src: str, tgt: str, rel: str):
            edges.append(DAGEdge(source=src, target=tgt, relationship=rel))
            children_map[src].append(tgt)
            in_degree[tgt] += 1
            out_degree[src] += 1

        for s in spans:
            s_id = str(s.get("span_id"))
            parent_id = str(s.get("parent_span_id")) if s.get("parent_span_id") else None
            if parent_id and parent_id in span_by_id:
                add_edge(parent_id, s_id, "parent_child")
                parent_map[s_id] = parent_id

        sorted_spans = sorted(spans, key=lambda x: (x.get("step_index", 0), x.get("start_time", 0.0)))
        for i in range(len(sorted_spans) - 1):
            curr_id = str(sorted_spans[i].get("span_id"))
            next_id = str(sorted_spans[i + 1].get("span_id"))
            curr_parent = str(sorted_spans[i].get("parent_span_id")) if sorted_spans[i].get("parent_span_id") else None
            next_parent = str(sorted_spans[i + 1].get("parent_span_id")) if sorted_spans[i + 1].get("parent_span_id") else None
            if curr_parent == next_parent and curr_id != next_id:
                if not any(e.source == curr_id and e.target == next_id for e in edges):
                    add_edge(curr_id, next_id, "sequential")

        for node in nodes:
            node.is_leaf = out_degree[node.id] == 0

        retry_loops_count = 0
        cycle_nodes_set: Set[str] = set()
        visited: Dict[str, int] = {}

        def dfs_cycle(curr: str, path: List[str]) -> None:
            visited[curr] = 1
            path.append(curr)
            for nxt in children_map[curr]:
                if visited.get(nxt) == 1:
                    idx = path.index(nxt)
                    for n in path[idx:]: cycle_nodes_set.add(n)
                elif visited.get(nxt, 0) == 0:
                    dfs_cycle(nxt, path)
            path.pop()
            visited[curr] = 2

        for node in nodes:
            if visited.get(node.id, 0) == 0:
                dfs_cycle(node.id, [])

        tool_call_history: List[Tuple[str, str, str]] = [
            (str(s.get("span_id")), str(s.get("span_name")), str(s.get("status")))
            for s in sorted_spans if s.get("span_type") == "tool_call"
        ]

        for i in range(len(tool_call_history) - 1):
            s1_id, name1, st1 = tool_call_history[i]
            s2_id, name2, st2 = tool_call_history[i + 1]
            if name1 == name2 and (st1 in ("error", "retrying") or st2 in ("error", "retrying")):
                retry_loops_count += 1
                cycle_nodes_set.add(s1_id)
                cycle_nodes_set.add(s2_id)
                if not any(e.source == s1_id and e.target == s2_id for e in edges):
                    add_edge(s1_id, s2_id, "retry_loop")

        fan_outs = sum(1 for ch in children_map.values() if len(ch) > 1)
        critical_path, critical_latency = cls._compute_critical_path(nodes, children_map, in_degree)

        return TraceDAGResponse(
            trace_id=trace_id, nodes=nodes, edges=edges,
            has_cycles=len(cycle_nodes_set) > 0, cycle_nodes=list(cycle_nodes_set),
            critical_path=critical_path, critical_path_latency_ms=round(critical_latency, 2),
            parallel_fan_outs=fan_outs, retry_loops_detected=retry_loops_count
        )

    @classmethod
    def _compute_critical_path(
        cls, nodes: List[DAGNode], children_map: Dict[str, List[str]], in_degree: Dict[str, int]
    ) -> Tuple[List[str], float]:
        """Compute the longest latency execution path."""
        if not nodes:
            return [], 0.0

        latency_by_id = {n.id: n.latency_ms for n in nodes}
        root_nodes = [n.id for n in nodes if n.is_root or in_degree[n.id] == 0] or [nodes[0].id]
        memo: Dict[str, Tuple[float, List[str]]] = {}

        def get_longest(curr: str, visited_path: Set[str]) -> Tuple[float, List[str]]:
            if curr in memo:
                return memo[curr]
            if curr in visited_path:
                return latency_by_id.get(curr, 0.0), [curr]

            visited_path.add(curr)
            curr_lat = latency_by_id.get(curr, 0.0)
            max_child_lat = 0.0
            best_subpath: List[str] = []

            for child in children_map.get(curr, []):
                child_lat, child_path = get_longest(child, visited_path)
                if child_lat > max_child_lat:
                    max_child_lat, best_subpath = child_lat, child_path

            visited_path.remove(curr)
            res = (curr_lat + max_child_lat, [curr] + best_subpath)
            memo[curr] = res
            return res

        best_total = 0.0
        best_path: List[str] = []
        for r in root_nodes:
            tot, path = get_longest(r, set())
            if tot > best_total:
                best_total, best_path = tot, path

        return best_path, best_total


dag_builder = DAGBuilder()
