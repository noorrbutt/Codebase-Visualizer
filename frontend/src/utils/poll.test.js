import { afterEach, describe, expect, it, vi } from "vitest";
import { pollRepoStatus } from "./poll";
import { apiFetch } from "./api";

vi.mock("./api", () => ({ apiFetch: vi.fn() }));

function response(payload, ok = true) {
  return { ok, json: vi.fn().mockResolvedValue(payload) };
}

describe("pollRepoStatus", () => {
  afterEach(() => {
    vi.useRealTimers();
    vi.clearAllMocks();
  });

  it("reports status and stops polling after the repository is ready", async () => {
    vi.useFakeTimers();
    apiFetch.mockResolvedValue(response({ status: "ready", stage: "complete" }));
    const onStatus = vi.fn();
    const onReady = vi.fn();
    const onError = vi.fn();

    pollRepoStatus(17, { onStatus, onReady, onError });
    await vi.advanceTimersByTimeAsync(3000);
    await vi.advanceTimersByTimeAsync(6000);

    expect(apiFetch).toHaveBeenCalledTimes(1);
    expect(apiFetch).toHaveBeenCalledWith("/repos/17/status");
    expect(onStatus).toHaveBeenCalledWith("ready", "complete");
    expect(onReady).toHaveBeenCalledOnce();
    expect(onError).not.toHaveBeenCalled();
  });

  it("reports a failed analysis from the status response", async () => {
    vi.useFakeTimers();
    apiFetch.mockResolvedValue(response({ status: "failed", error: "Repository unavailable" }));
    const onError = vi.fn();
    const stop = pollRepoStatus(8, { onStatus: vi.fn(), onReady: vi.fn(), onError });

    await vi.advanceTimersByTimeAsync(3000);
    await vi.advanceTimersByTimeAsync(6000);

    expect(onError).toHaveBeenCalledWith("Repository unavailable");
    expect(apiFetch).toHaveBeenCalledTimes(1);
    stop();
  });

  it("stops and reports an error after five consecutive request failures", async () => {
    vi.useFakeTimers();
    apiFetch.mockRejectedValue(new Error("network error"));
    const onError = vi.fn();

    pollRepoStatus(9, { onStatus: vi.fn(), onReady: vi.fn(), onError });
    await vi.advanceTimersByTimeAsync(15_000);
    await vi.advanceTimersByTimeAsync(6000);

    expect(apiFetch).toHaveBeenCalledTimes(5);
    expect(onError).toHaveBeenCalledWith("Unable to check analysis status. Please try again.");
  });

  it("does not poll after the returned stop function is called", async () => {
    vi.useFakeTimers();
    const stop = pollRepoStatus(11, {
      onStatus: vi.fn(),
      onReady: vi.fn(),
      onError: vi.fn(),
    });

    stop();
    await vi.advanceTimersByTimeAsync(6000);

    expect(apiFetch).not.toHaveBeenCalled();
  });
});
