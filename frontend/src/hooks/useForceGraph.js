import { useEffect, useMemo, useRef, useCallback } from "react";
import { LANG_COLOR } from "../utils/lang";

export function useForceGraph(
  nodes,
  edges,
  canvasRef,
  selectedNode,
  onSelectNode,
  { visiblePaths, searchQuery, neighborhoodOnly },
  initialSimulation,
) {
  const simRef = useRef(initialSimulation?.nodes || null);
  const simulationSignature = useMemo(
    () => JSON.stringify({
      nodes: nodes.map((node) => [node.id, node.path, node.import_count]),
      edges: edges.map((edge) => [edge.source, edge.target]),
    }),
    [edges, nodes],
  );
  const previousSimulationSignatureRef = useRef(initialSimulation?.signature || null);
  const animRef = useRef(null);
  const alphaRef = useRef(0);
  const restartSimulationRef = useRef(null);
  const filterSignatureRef = useRef(null);
  const themeColorsRef = useRef({});
  const transformRef = useRef({ x: 0, y: 0, scale: 1 });
  const isDraggingRef = useRef(false);
  const dragStartRef = useRef(null);
  const dragNodeRef = useRef(null);
  const hoveredRef = useRef(null);
  const activePointersRef = useRef(new Map());
  const pinchRef = useRef(null);
  const hadPinchRef = useRef(false);
  const suppressClickRef = useRef(false);
  const allowedPaths = useMemo(() => {
    const allowed = new Set(visiblePaths);
    if (!neighborhoodOnly || !selectedNode) return allowed;
    allowed.clear();
    if (visiblePaths.has(selectedNode.path)) allowed.add(selectedNode.path);
    edges.forEach((edge) => {
      if (edge.source === selectedNode.path && visiblePaths.has(edge.target)) {
        allowed.add(edge.target);
      }
      if (edge.target === selectedNode.path && visiblePaths.has(edge.source)) {
        allowed.add(edge.source);
      }
    });
    return allowed;
  }, [edges, neighborhoodOnly, selectedNode, visiblePaths]);
  const viewRef = useRef({ edges, selectedNode, allowedPaths, searchQuery });
  useEffect(() => {
    viewRef.current = { edges, selectedNode, allowedPaths, searchQuery };
  }, [edges, selectedNode, allowedPaths, searchQuery]);

  const isNodeVisible = useCallback((path) => {
    return viewRef.current.allowedPaths.has(path);
  }, []);

  const getSimulation = useCallback(
    () => ({ nodes: simRef.current, signature: simulationSignature }),
    [simulationSignature],
  );

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas || !simRef.current) return;
    const ctx = canvas.getContext("2d");
    const dpr = window.devicePixelRatio || 1;
    const { x, y, scale } = transformRef.current;
    const w = canvas.clientWidth;
    const h = canvas.clientHeight;
    const themeColor = (name) => themeColorsRef.current[name];
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);
    ctx.save();
    ctx.translate(x, y);
    ctx.scale(scale, scale);

    const nodeMap = {};
    simRef.current.forEach((n) => { nodeMap[n.path] = n; });

    const view = viewRef.current;
    const highlightedNodeIds = new Set();
    if (view.selectedNode) {
      highlightedNodeIds.add(view.selectedNode.path);
      view.edges.forEach((e) => {
        if (e.source === view.selectedNode.path) highlightedNodeIds.add(e.target);
        if (e.target === view.selectedNode.path) highlightedNodeIds.add(e.source);
      });
    }
    const isVisible = (path) => view.allowedPaths.has(path);
    const query = view.searchQuery.trim().toLowerCase();

    // Draw edges
    view.edges.forEach((e) => {
      if (!isVisible(e.source) || !isVisible(e.target)) return;
      const s = nodeMap[e.source];
      const t = nodeMap[e.target];
      if (!s || !t) return;
      const isHighlighted =
        view.selectedNode &&
        (e.source === view.selectedNode.path || e.target === view.selectedNode.path);
      ctx.beginPath();
      ctx.moveTo(s.x, s.y);
      ctx.lineTo(t.x, t.y);
      const isSearchMatch =
        !query || e.source.toLowerCase().includes(query) || e.target.toLowerCase().includes(query);
      ctx.strokeStyle = isHighlighted
        ? themeColor("--canvas-edge-highlight")
        : isSearchMatch ? themeColor("--canvas-edge") : themeColor("--canvas-edge-muted");
      ctx.lineWidth = isHighlighted ? 1.5 / scale : 0.8 / scale;
      ctx.stroke();
    });

    // Draw nodes
    simRef.current.forEach((n) => {
      if (!isVisible(n.path)) return;
      const isSelected = view.selectedNode?.path === n.path;
      const isHovered = hoveredRef.current === n.path;
      const isConnected = highlightedNodeIds.has(n.path);
      const isSearchMatch = !query || n.path.toLowerCase().includes(query);
      const isDimmed = (view.selectedNode && !isSelected && !isConnected) || !isSearchMatch;
      const r = Math.max(5, Math.min(13, 5 + (n.import_count || 0) * 1.4));

      ctx.beginPath();
      ctx.arc(n.x, n.y, r / scale, 0, Math.PI * 2);
      const languageVariable = LANG_COLOR[n.language?.toLowerCase()] || LANG_COLOR.default;
      ctx.fillStyle = themeColor(languageVariable);
      ctx.globalAlpha = isDimmed ? 0.12 : isSelected ? 1 : isHovered ? 0.95 : 0.72;
      ctx.fill();
      ctx.globalAlpha = 1;

      if (isSelected || isHovered) {
        ctx.beginPath();
        ctx.arc(n.x, n.y, (r + 4) / scale, 0, Math.PI * 2);
        ctx.strokeStyle = themeColor(languageVariable);
        ctx.lineWidth = 2 / scale;
        ctx.globalAlpha = isSelected ? 1 : 0.5;
        ctx.stroke();
        ctx.globalAlpha = 1;
      }

      if (!isDimmed && (scale > 0.55 || isSelected || isHovered)) {
        const label = n.path.split("/").pop();
        ctx.font = `${isSelected ? "500 " : ""}${11 / scale}px 'DM Mono', monospace`;
        ctx.fillStyle = isSelected ? themeColor("--fg") : isConnected ? themeColor("--fg-dim") : themeColor("--subtle");
        ctx.globalAlpha = isDimmed ? 0.08 : 1;
        ctx.fillText(label, n.x + (r + 4) / scale, n.y + 4 / scale);
        ctx.globalAlpha = 1;
      }
    });

    ctx.restore();
  }, [canvasRef]);

  useEffect(() => {
    const refreshThemeColors = () => {
      const styles = getComputedStyle(document.documentElement);
      const variables = new Set([
        "--canvas-edge-highlight",
        "--canvas-edge",
        "--canvas-edge-muted",
        "--fg",
        "--fg-dim",
        "--subtle",
        ...Object.values(LANG_COLOR),
      ]);
      themeColorsRef.current = Object.fromEntries(
        [...variables].map((name) => [name, styles.getPropertyValue(name).trim()]),
      );
      draw();
    };

    refreshThemeColors();
    const colorScheme = window.matchMedia("(prefers-color-scheme: dark)");
    colorScheme.addEventListener("change", refreshThemeColors);
    return () => colorScheme.removeEventListener("change", refreshThemeColors);
  }, [draw]);

  useEffect(() => {
    if (!nodes.length) {
      if (animRef.current !== null) cancelAnimationFrame(animRef.current);
      animRef.current = null;
      simRef.current = [];
      previousSimulationSignatureRef.current = simulationSignature;
      return;
    }
    const sameSimulation = previousSimulationSignatureRef.current === simulationSignature;
    previousSimulationSignatureRef.current = simulationSignature;
    const W = 1200;
    const H = 900;
    const existingNodes = new Map((simRef.current || []).map((node) => [node.path, node]));
    const sim = nodes.map((node) => {
      const existing = existingNodes.get(node.path);
      if (existing) return Object.assign(existing, node);

      let hash = 2166136261;
      for (let index = 0; index < node.path.length; index++) {
        hash ^= node.path.charCodeAt(index);
        hash = Math.imul(hash, 16777619);
      }
      const xFraction = (hash >>> 0) / 0xffffffff;
      const yFraction = ((hash ^ (hash >>> 16)) >>> 0) / 0xffffffff;
      return {
        ...node,
        x: W / 2 + (xFraction - 0.5) * 400,
        y: H / 2 + (yFraction - 0.5) * 400,
        vx: 0,
        vy: 0,
      };
    });
    simRef.current = sim;
    const nodeMap = {};
    sim.forEach((n) => { nodeMap[n.path] = n; });
    const directoryByPath = new Map(
      sim.map((node) => [node.path, node.path.includes("/") ? node.path.split("/")[0] : "(root)"]),
    );

    const cancelFrame = () => {
      if (animRef.current !== null) {
        cancelAnimationFrame(animRef.current);
        animRef.current = null;
      }
    };
    const step = () => {
      const alpha = alphaRef.current;
      if (alpha < 0.005) {
        animRef.current = null;
        return;
      }
      const cx = W / 2;
      const cy = H / 2;

      sim.forEach((a) => {
        a.vx += (cx - a.x) * 0.0008 * alpha;
        a.vy += (cy - a.y) * 0.0008 * alpha;
        sim.forEach((b) => {
          if (a.id === b.id) return;
          const dx = a.x - b.x;
          const dy = a.y - b.y;
          const d = Math.sqrt(dx * dx + dy * dy) || 1;
          const rep = 700 / (d * d);
          a.vx += dx * rep * alpha;
          a.vy += dy * rep * alpha;
        });
      });

      edges.forEach((e) => {
        const s = nodeMap[e.source];
        const t = nodeMap[e.target];
        if (!s || !t) return;
        const dx = t.x - s.x;
        const dy = t.y - s.y;
        const d = Math.sqrt(dx * dx + dy * dy) || 1;
        const f = (d - 80) * 0.025 * alpha;
        s.vx += (dx / d) * f;
        s.vy += (dy / d) * f;
        t.vx -= (dx / d) * f;
        t.vy -= (dy / d) * f;
      });

      const directoryCenters = new Map();
      sim.forEach((node) => {
        const directory = directoryByPath.get(node.path);
        const center = directoryCenters.get(directory) || { x: 0, y: 0, count: 0 };
        center.x += node.x;
        center.y += node.y;
        center.count += 1;
        directoryCenters.set(directory, center);
      });
      directoryCenters.forEach((center) => {
        center.x /= center.count;
        center.y /= center.count;
      });
      sim.forEach((node) => {
        const center = directoryCenters.get(directoryByPath.get(node.path));
        node.vx += (center.x - node.x) * 0.0015 * alpha;
        node.vy += (center.y - node.y) * 0.0015 * alpha;
      });

      sim.forEach((n) => {
        if (n.fixed) return;
        n.vx *= 0.72;
        n.vy *= 0.72;
        n.x += n.vx;
        n.y += n.vy;
      });

      draw();
      alphaRef.current *= 0.994;
      if (alphaRef.current >= 0.005) {
        animRef.current = requestAnimationFrame(step);
      } else {
        animRef.current = null;
      }
    };

    const restart = () => {
      cancelFrame();
      alphaRef.current = 0.3;
      animRef.current = requestAnimationFrame(step);
    };
    restartSimulationRef.current = restart;
    if (sameSimulation) {
      draw();
    } else {
      restart();
    }
    return () => {
      cancelFrame();
      restartSimulationRef.current = null;
    };
  }, [nodes, edges, draw, simulationSignature]);

  useEffect(() => {
    draw();
    const signature = JSON.stringify([
      searchQuery,
      neighborhoodOnly,
      [...allowedPaths].sort(),
    ]);
    if (filterSignatureRef.current !== null && filterSignatureRef.current !== signature) {
      restartSimulationRef.current?.();
    }
    filterSignatureRef.current = signature;
  }, [allowedPaths, draw, neighborhoodOnly, searchQuery]);

  useEffect(() => () => {
    if (animRef.current !== null) cancelAnimationFrame(animRef.current);
  }, []);

  const getNode = useCallback((ex, ey) => {
    const canvas = canvasRef.current;
    if (!canvas || !simRef.current) return null;
    const rect = canvas.getBoundingClientRect();
    const { x, y, scale } = transformRef.current;
    const wx = (ex - rect.left - x) / scale;
    const wy = (ey - rect.top - y) / scale;
    return (
      simRef.current.find((n) => {
        if (!isNodeVisible(n.path)) return false;
        const r = Math.max(5, Math.min(13, 5 + (n.import_count || 0) * 1.4));
        return Math.hypot(n.x - wx, n.y - wy) <= r / scale + 4;
      }) || null
    );
  }, [canvasRef, isNodeVisible]);

  const onPointerDown = useCallback((e) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    suppressClickRef.current = false;
    if (activePointersRef.current.size === 0) hadPinchRef.current = false;
    canvas.setPointerCapture(e.pointerId);
    activePointersRef.current.set(e.pointerId, { x: e.clientX, y: e.clientY });

    if (activePointersRef.current.size >= 2) {
      hadPinchRef.current = true;
      if (dragNodeRef.current) dragNodeRef.current.fixed = true;
      dragNodeRef.current = null;
      isDraggingRef.current = false;
      const points = [...activePointersRef.current.values()];
      const midpoint = {
        x: ((points[0].x + points[1].x) / 2) - canvas.getBoundingClientRect().left,
        y: ((points[0].y + points[1].y) / 2) - canvas.getBoundingClientRect().top,
      };
      const distance = Math.hypot(points[0].x - points[1].x, points[0].y - points[1].y);
      const transform = transformRef.current;
      pinchRef.current = {
        distance,
        scale: transform.scale,
        worldX: (midpoint.x - transform.x) / transform.scale,
        worldY: (midpoint.y - transform.y) / transform.scale,
      };
      suppressClickRef.current = true;
      return;
    }

    const node = getNode(e.clientX, e.clientY);
    if (node) {
      dragNodeRef.current = node;
      node.fixed = true;
    } else {
      isDraggingRef.current = true;
      dragStartRef.current = {
        x: e.clientX - transformRef.current.x,
        y: e.clientY - transformRef.current.y,
      };
    }
  }, [canvasRef, getNode]);

  const onPointerMove = useCallback((e) => {
    const canvas = canvasRef.current;
    if (activePointersRef.current.has(e.pointerId)) {
      activePointersRef.current.set(e.pointerId, { x: e.clientX, y: e.clientY });
    }
    if (activePointersRef.current.size >= 2 && pinchRef.current && canvas) {
      const points = [...activePointersRef.current.values()];
      const rect = canvas.getBoundingClientRect();
      const midpoint = {
        x: (points[0].x + points[1].x) / 2 - rect.left,
        y: (points[0].y + points[1].y) / 2 - rect.top,
      };
      const distance = Math.hypot(points[0].x - points[1].x, points[0].y - points[1].y);
      const pinch = pinchRef.current;
      const scale = Math.max(0.1, Math.min(4, pinch.scale * distance / (pinch.distance || 1)));
      transformRef.current = {
        x: midpoint.x - pinch.worldX * scale,
        y: midpoint.y - pinch.worldY * scale,
        scale,
      };
      suppressClickRef.current = true;
      draw();
      return;
    }
    if (dragNodeRef.current) {
      const rect = canvas?.getBoundingClientRect();
      if (!rect) return;
      const { x, y, scale } = transformRef.current;
      dragNodeRef.current.x = (e.clientX - rect.left - x) / scale;
      dragNodeRef.current.y = (e.clientY - rect.top - y) / scale;
      draw();
    } else if (isDraggingRef.current) {
      if (activePointersRef.current.has(e.pointerId)) suppressClickRef.current = true;
      transformRef.current.x = e.clientX - dragStartRef.current.x;
      transformRef.current.y = e.clientY - dragStartRef.current.y;
      draw();
    } else {
      const node = getNode(e.clientX, e.clientY);
      if (canvas) canvas.style.cursor = node ? "pointer" : "grab";
      const prev = hoveredRef.current;
      hoveredRef.current = node?.path || null;
      if (prev !== hoveredRef.current) draw();
    }
  }, [canvasRef, draw, getNode]);

  const onPointerUp = useCallback((e) => {
    activePointersRef.current.delete(e.pointerId);
    if (hadPinchRef.current) suppressClickRef.current = true;
    const releasedNode = Boolean(dragNodeRef.current);
    if (dragNodeRef.current) {
      dragNodeRef.current.fixed = true;
      dragNodeRef.current = null;
    }
    isDraggingRef.current = false;
    dragStartRef.current = null;
    if (activePointersRef.current.size < 2) pinchRef.current = null;
    if (activePointersRef.current.size === 1) {
      const remaining = [...activePointersRef.current.values()][0];
      isDraggingRef.current = true;
      dragStartRef.current = {
        x: remaining.x - transformRef.current.x,
        y: remaining.y - transformRef.current.y,
      };
    }
    if (activePointersRef.current.size === 0) hadPinchRef.current = false;
    if (releasedNode) restartSimulationRef.current?.();
  }, []);

  const onWheel = useCallback((e) => {
    e.preventDefault();
    const factor = e.deltaY < 0 ? 1.1 : 0.9;
    const canvas = canvasRef.current;
    const rect = canvas.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    const { x, y, scale } = transformRef.current;
    const newScale = Math.max(0.1, Math.min(4, scale * factor));
    transformRef.current = {
      x: mx - (mx - x) * (newScale / scale),
      y: my - (my - y) * (newScale / scale),
      scale: newScale,
    };
    draw();
  }, [canvasRef, draw]);

  const onClick = useCallback((e) => {
    if (suppressClickRef.current) {
      suppressClickRef.current = false;
      return;
    }
    const node = getNode(e.clientX, e.clientY);
    onSelectNode(node);
  }, [getNode, onSelectNode]);

  const centerNode = useCallback((path) => {
    const node = simRef.current?.find((item) => item.path === path);
    const canvas = canvasRef.current;
    if (!node || !canvas) return;

    const scale = Math.max(0.65, Math.min(1.5, transformRef.current.scale));
    transformRef.current = {
      x: canvas.clientWidth / 2 - node.x * scale,
      y: canvas.clientHeight / 2 - node.y * scale,
      scale,
    };
    draw();
  }, [canvasRef, draw]);

  return {
    onPointerDown,
    onPointerMove,
    onPointerUp,
    onWheel,
    onClick,
    centerNode,
    draw,
    getSimulation,
  };
}
