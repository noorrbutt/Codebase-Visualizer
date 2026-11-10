from __future__ import annotations

from collections.abc import Iterable
from typing import TypedDict


class GraphEdge(TypedDict):
    source: str
    target: str


class MetricNode(TypedDict):
    path: str
    count: int


def compute_graph_metrics(
    node_paths: Iterable[str], edges: Iterable[GraphEdge]
) -> dict[str, object]:
    paths = sorted(set(node_paths))
    path_set = set(paths)
    adjacency = {path: [] for path in paths}
    fan_in = dict.fromkeys(paths, 0)
    fan_out = dict.fromkeys(paths, 0)

    for edge in edges:
        source = edge["source"]
        target = edge["target"]
        if source in path_set:
            fan_out[source] += 1
        if target in path_set:
            fan_in[target] += 1
        if source in path_set and target in path_set:
            adjacency[source].append(target)

    for targets in adjacency.values():
        targets.sort()

    indices: dict[str, int] = {}
    lowlinks: dict[str, int] = {}
    component_stack: list[str] = []
    on_stack: set[str] = set()
    components: list[list[str]] = []
    next_index = 0

    for root in paths:
        if root in indices:
            continue

        indices[root] = next_index
        lowlinks[root] = next_index
        next_index += 1
        component_stack.append(root)
        on_stack.add(root)
        frames: list[tuple[str, int]] = [(root, 0)]

        while frames:
            node, child_index = frames[-1]
            neighbors = adjacency[node]
            if child_index < len(neighbors):
                neighbor = neighbors[child_index]
                frames[-1] = (node, child_index + 1)

                if neighbor not in indices:
                    indices[neighbor] = next_index
                    lowlinks[neighbor] = next_index
                    next_index += 1
                    component_stack.append(neighbor)
                    on_stack.add(neighbor)
                    frames.append((neighbor, 0))
                elif neighbor in on_stack:
                    lowlinks[node] = min(lowlinks[node], indices[neighbor])
                continue

            frames.pop()
            if frames:
                parent = frames[-1][0]
                lowlinks[parent] = min(lowlinks[parent], lowlinks[node])

            if lowlinks[node] == indices[node]:
                component: list[str] = []
                while True:
                    member = component_stack.pop()
                    on_stack.remove(member)
                    component.append(member)
                    if member == node:
                        break
                if len(component) > 1:
                    components.append(sorted(component))

    components.sort(key=lambda component: component[0])

    def top_nodes(degrees: dict[str, int]) -> list[MetricNode]:
        ranked = sorted(
            ((path, count) for path, count in degrees.items() if count > 0),
            key=lambda item: (-item[1], item[0]),
        )
        return [{"path": path, "count": count} for path, count in ranked[:5]]

    orphans = [
        path for path in paths if fan_in[path] == 0 and fan_out[path] == 0
    ]
    return {
        "cycle_count": len(components),
        "cycles": components[:10],
        "top_fan_in": top_nodes(fan_in),
        "top_fan_out": top_nodes(fan_out),
        "orphan_count": len(orphans),
        "orphans": orphans[:20],
    }
