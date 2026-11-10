from app.services.graph_metrics import compute_graph_metrics


def test_graph_metrics_find_cycles_fan_counts_and_orphans():
    metrics = compute_graph_metrics(
        ["a.py", "b.py", "c.py", "d.py", "alone.py"],
        [
            {"source": "a.py", "target": "b.py"},
            {"source": "b.py", "target": "a.py"},
            {"source": "b.py", "target": "c.py"},
            {"source": "c.py", "target": "c.py"},
            {"source": "d.py", "target": "a.py"},
        ],
    )

    assert metrics == {
        "cycle_count": 1,
        "cycles": [["a.py", "b.py"]],
        "top_fan_in": [
            {"path": "a.py", "count": 2},
            {"path": "c.py", "count": 2},
            {"path": "b.py", "count": 1},
        ],
        "top_fan_out": [
            {"path": "b.py", "count": 2},
            {"path": "a.py", "count": 1},
            {"path": "c.py", "count": 1},
            {"path": "d.py", "count": 1},
        ],
        "orphan_count": 1,
        "orphans": ["alone.py"],
    }


def test_graph_metrics_find_self_contained_cycle_and_orphan():
    metrics = compute_graph_metrics(
        ["cycle/a.py", "cycle/b.py", "orphan.py"],
        [
            {"source": "cycle/a.py", "target": "cycle/b.py"},
            {"source": "cycle/b.py", "target": "cycle/a.py"},
        ],
    )

    assert metrics["cycle_count"] == 1
    assert metrics["cycles"] == [["cycle/a.py", "cycle/b.py"]]
    assert metrics["orphan_count"] == 1
    assert metrics["orphans"] == ["orphan.py"]


def test_graph_metrics_respect_result_limits():
    nodes = [f"node-{index:02}.py" for index in range(25)]
    edges = [
        {"source": nodes[index], "target": nodes[(index + 1) % len(nodes)]}
        for index in range(len(nodes))
    ]

    metrics = compute_graph_metrics(nodes + ["orphan.py"], edges)

    assert metrics["cycle_count"] == 1
    assert metrics["cycles"] == [nodes]
    assert len(metrics["top_fan_in"]) == 5
    assert len(metrics["top_fan_out"]) == 5
    assert metrics["orphan_count"] == 1
    assert metrics["orphans"] == ["orphan.py"]


def test_graph_metrics_are_iterative_for_deep_graphs():
    nodes = [f"node-{index}.py" for index in range(2000)]
    edges = [
        {"source": nodes[index], "target": nodes[index + 1]}
        for index in range(len(nodes) - 1)
    ]

    metrics = compute_graph_metrics(nodes, edges)

    assert metrics["cycle_count"] == 0
    assert metrics["orphan_count"] == 0
