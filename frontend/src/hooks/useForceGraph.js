import { useEffect, useRef, useCallback } from "react";
import { getLangColor } from "../utils/lang";

export function useForceGraph(nodes, edges, canvasRef, selectedNode, onSelectNode) {
  const simRef = useRef(null);
  const animRef = useRef(null);
  const transformRef = useRef({ x: 0, y: 0, scale: 1 });
  const isDraggingRef = useRef(false);
  const dragStartRef = useRef(null);
  const dragNodeRef = useRef(null);
  const hoveredRef = useRef(null);

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas || !simRef.current) return;
    const ctx = canvas.getContext("2d");
    const { x, y, scale } = transformRef.current;
    const w = canvas.width;
    const h = canvas.height;
    ctx.clearRect(0, 0, w, h);
    ctx.save();
    ctx.translate(x, y);
    ctx.scale(scale, scale);
    ctx.fillStyle = "#F8F9FA";
    ctx.fillRect(0, 0, w, h);

    const nodeMap = {};
    simRef.current.forEach((n) => { nodeMap[n.id] = n; });

    const highlightedNodeIds = new Set();
    if (selectedNode) {
      highlightedNodeIds.add(selectedNode.id);
      edges.forEach((e) => {
        if (e.source === selectedNode.id || e.source === selectedNode.path) highlightedNodeIds.add(e.target);
        if (e.target === selectedNode.id || e.target === selectedNode.path) highlightedNodeIds.add(e.source);
      });
    }

    // Draw edges
    edges.forEach((e) => {
      const s = nodeMap[e.source];
      const t = nodeMap[e.target];
      if (!s || !t) return;
      const isHighlighted =
        selectedNode &&
        (e.source === selectedNode.id || e.source === selectedNode.path ||
          e.target === selectedNode.id || e.target === selectedNode.path);
      ctx.beginPath();
      ctx.moveTo(s.x, s.y);
      ctx.lineTo(t.x, t.y);
      ctx.strokeStyle = isHighlighted ? "rgba(99,102,241,0.55)" : "rgba(0,0,0,0.06)";
      ctx.lineWidth = isHighlighted ? 1.5 / scale : 0.8 / scale;
      ctx.stroke();
    });

    // Draw nodes
    simRef.current.forEach((n) => {
      const isSelected = selectedNode?.id === n.id;
      const isHovered = hoveredRef.current === n.id;
      const isConnected = highlightedNodeIds.has(n.id) || highlightedNodeIds.has(n.path);
      const isDimmed = selectedNode && !isSelected && !isConnected;
      const r = Math.max(5, Math.min(13, 5 + (n.import_count || 0) * 1.4));

      ctx.beginPath();
      ctx.arc(n.x, n.y, r / scale, 0, Math.PI * 2);
      ctx.fillStyle = getLangColor(n.language);
      ctx.globalAlpha = isDimmed ? 0.12 : isSelected ? 1 : isHovered ? 0.95 : 0.72;
      ctx.fill();
      ctx.globalAlpha = 1;

      if (isSelected || isHovered) {
        ctx.beginPath();
        ctx.arc(n.x, n.y, (r + 4) / scale, 0, Math.PI * 2);
        ctx.strokeStyle = getLangColor(n.language);
        ctx.lineWidth = 2 / scale;
        ctx.globalAlpha = isSelected ? 1 : 0.5;
        ctx.stroke();
        ctx.globalAlpha = 1;
      }

      if (!isDimmed && (scale > 0.55 || isSelected || isHovered)) {
        const label = n.path.split("/").pop();
        ctx.font = `${isSelected ? "500 " : ""}${11 / scale}px 'DM Mono', monospace`;
        ctx.fillStyle = isSelected ? "#111827" : isConnected ? "#374151" : "#9CA3AF";
        ctx.globalAlpha = isDimmed ? 0.08 : 1;
        ctx.fillText(label, n.x + (r + 4) / scale, n.y + 4 / scale);
        ctx.globalAlpha = 1;
      }
    });

    ctx.restore();
  }, [canvasRef, edges, selectedNode]);

  useEffect(() => {
    if (!nodes.length) return;
    const W = 1200;
    const H = 900;
    const sim = nodes.map((n) => ({
      ...n,
      x: W / 2 + (Math.random() - 0.5) * 400,
      y: H / 2 + (Math.random() - 0.5) * 400,
      vx: 0,
      vy: 0,
    }));
    simRef.current = sim;
    const nodeMap = {};
    sim.forEach((n) => { nodeMap[n.id] = n; });

    let tick = 0;
    const step = () => {
      tick++;
      const alpha = Math.max(0.001, 0.3 * Math.pow(0.994, tick));
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

      sim.forEach((n) => {
        if (n.fixed) return;
        n.vx *= 0.72;
        n.vy *= 0.72;
        n.x += n.vx;
        n.y += n.vy;
      });

      draw();
      animRef.current = requestAnimationFrame(step);
    };

    animRef.current = requestAnimationFrame(step);
    return () => cancelAnimationFrame(animRef.current);
  }, [nodes, edges, draw]);

  useEffect(() => { draw(); }, [selectedNode, draw]);

  const getNode = useCallback((ex, ey) => {
    const canvas = canvasRef.current;
    if (!canvas || !simRef.current) return null;
    const rect = canvas.getBoundingClientRect();
    const { x, y, scale } = transformRef.current;
    const wx = (ex - rect.left - x) / scale;
    const wy = (ey - rect.top - y) / scale;
    return (
      simRef.current.find((n) => {
        const r = Math.max(5, Math.min(13, 5 + (n.import_count || 0) * 1.4));
        return Math.hypot(n.x - wx, n.y - wy) <= r / scale + 4;
      }) || null
    );
  }, [canvasRef]);

  const onMouseDown = useCallback((e) => {
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
  }, [getNode]);

  const onMouseMove = useCallback((e) => {
    if (dragNodeRef.current) {
      const canvas = canvasRef.current;
      const rect = canvas.getBoundingClientRect();
      const { x, y, scale } = transformRef.current;
      dragNodeRef.current.x = (e.clientX - rect.left - x) / scale;
      dragNodeRef.current.y = (e.clientY - rect.top - y) / scale;
      draw();
    } else if (isDraggingRef.current) {
      transformRef.current.x = e.clientX - dragStartRef.current.x;
      transformRef.current.y = e.clientY - dragStartRef.current.y;
      draw();
    } else {
      const node = getNode(e.clientX, e.clientY);
      const canvas = canvasRef.current;
      if (canvas) canvas.style.cursor = node ? "pointer" : "grab";
      const prev = hoveredRef.current;
      hoveredRef.current = node?.id || null;
      if (prev !== hoveredRef.current) draw();
    }
  }, [canvasRef, draw, getNode]);

  const onMouseUp = useCallback(() => {
    if (dragNodeRef.current) {
      dragNodeRef.current.fixed = true;
      dragNodeRef.current = null;
    }
    isDraggingRef.current = false;
    dragStartRef.current = null;
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
    const node = getNode(e.clientX, e.clientY);
    onSelectNode(node);
  }, [getNode, onSelectNode]);

  return { onMouseDown, onMouseMove, onMouseUp, onWheel, onClick };
}
