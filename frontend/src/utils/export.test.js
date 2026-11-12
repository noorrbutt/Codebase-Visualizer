import { afterEach, describe, expect, it, vi } from "vitest";
import { createMermaidGraph, exportGraphJson } from "./export";

describe("graph exports", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("creates a Mermaid graph with stable ids, escaped quotes, and selected edges", () => {
    const nodes = [
      { path: "src/first.js" },
      { path: 'src/quo"ted.js' },
      { path: "src/isolated.js" },
    ];
    const edges = [
      { source: "src/first.js", target: 'src/quo"ted.js' },
      { source: "src/missing.js", target: "src/isolated.js" },
    ];

    expect(createMermaidGraph(nodes, edges)).toBe([
      "graph LR",
      '  n0["first.js"]',
      '  n1["isolated.js"]',
      '  n2["quo#quot;ted.js"]',
      "  n0 --> n2",
    ].join("\n"));
  });

  it("exports the repository, nodes, and edges as JSON with a safe filename", async () => {
    vi.useFakeTimers();
    const click = vi.fn();
    const revokeObjectURL = vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => {});
    const createObjectURL = vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:test");
    const anchor = { click, download: "", href: "" };
    vi.stubGlobal("document", { createElement: vi.fn().mockReturnValue(anchor) });
    const repo = { id: 2, owner: "owner", name: "repo" };
    const nodes = [{ path: "src/main.js" }];
    const edges = [{ source: "src/main.js", target: "src/util.js" }];

    exportGraphJson(repo, nodes, edges, "owner/repo");

    expect(anchor.download).toBe("owner-repo.json");
    expect(createObjectURL).toHaveBeenCalledOnce();
    const blob = createObjectURL.mock.calls[0][0];
    expect(blob.type).toBe("application/json");
    expect(JSON.parse(await blob.text())).toEqual({ repo, nodes, edges });
    expect(click).toHaveBeenCalledOnce();
    await vi.runOnlyPendingTimersAsync();
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:test");
  });
});
