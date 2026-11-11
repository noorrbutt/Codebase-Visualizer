function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 0);
}

function safeFilename(value) {
  return value.replace(/[^a-z0-9._-]+/gi, "-").replace(/^-+|-+$/g, "") || "repository";
}

export function exportGraphPng(canvas, filename) {
  if (!canvas) throw new Error("Open the graph view before exporting a PNG.");

  const output = document.createElement("canvas");
  output.width = canvas.width;
  output.height = canvas.height;
  const context = output.getContext("2d");
  if (!context) throw new Error("Could not prepare the graph image.");
  context.fillStyle = getComputedStyle(document.documentElement)
    .getPropertyValue("--export-background")
    .trim();
  context.fillRect(0, 0, output.width, output.height);
  context.drawImage(canvas, 0, 0);
  return new Promise((resolve, reject) => {
    output.toBlob((blob) => {
      if (!blob) {
        reject(new Error("Could not encode graph canvas as PNG."));
        return;
      }
      downloadBlob(blob, `${safeFilename(filename)}.png`);
      resolve();
    }, "image/png");
  });
}

export function exportGraphJson(repo, nodes, edges, filename) {
  const contents = JSON.stringify({ repo, nodes, edges }, null, 2);
  downloadBlob(
    new Blob([contents], { type: "application/json" }),
    `${safeFilename(filename)}.json`,
  );
}

export function createMermaidGraph(nodes, edges) {
  const degree = new Map(nodes.map((node) => [node.path, 0]));
  edges.forEach((edge) => {
    if (degree.has(edge.source)) degree.set(edge.source, degree.get(edge.source) + 1);
    if (degree.has(edge.target)) degree.set(edge.target, degree.get(edge.target) + 1);
  });

  const selectedNodes = [...nodes]
    .sort((a, b) => (degree.get(b.path) - degree.get(a.path)) || a.path.localeCompare(b.path))
    .slice(0, 40);
  const ids = new Map(selectedNodes.map((node, index) => [node.path, `n${index}`]));
  const lines = ["graph LR"];

  selectedNodes.forEach((node) => {
    const label = node.path.split("/").pop().replace(/"/g, "#quot;");
    lines.push(`  ${ids.get(node.path)}["${label}"]`);
  });
  edges.forEach((edge) => {
    const sourceId = ids.get(edge.source);
    const targetId = ids.get(edge.target);
    if (sourceId && targetId) lines.push(`  ${sourceId} --> ${targetId}`);
  });

  return lines.join("\n");
}

export async function copyMermaidGraph(nodes, edges) {
  await navigator.clipboard.writeText(createMermaidGraph(nodes, edges));
}
