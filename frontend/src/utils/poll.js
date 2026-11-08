import { apiFetch } from "./api";

const POLL_INTERVAL_MS = 3000;
const MAX_POLL_DURATION_MS = 3 * 60 * 1000;
const MAX_CONSECUTIVE_FAILURES = 5;

export function pollRepoStatus(id, { onStatus, onReady, onError }) {
  let stopped = false;
  let inFlight = false;
  let consecutiveFailures = 0;
  let intervalId;
  let timeoutId;

  const stop = () => {
    if (stopped) return;
    stopped = true;
    clearInterval(intervalId);
    clearTimeout(timeoutId);
  };

  timeoutId = setTimeout(() => {
    stop();
    onError("Taking too long");
  }, MAX_POLL_DURATION_MS);

  intervalId = setInterval(async () => {
    if (stopped || inFlight) return;
    inFlight = true;
    try {
      const response = await apiFetch(`/repos/${id}/status`);
      if (stopped) return;
      if (!response.ok) throw new Error("Status request failed");
      const result = await response.json();
      if (stopped) return;
      consecutiveFailures = 0;
      onStatus(result.status);
      if (result.status === "ready") {
        stop();
        await onReady();
      } else if (result.status === "failed") {
        stop();
        onError(result.error || "Analysis failed");
      }
    } catch {
      if (stopped) return;
      consecutiveFailures += 1;
      if (consecutiveFailures >= MAX_CONSECUTIVE_FAILURES) {
        stop();
        onError("Unable to check analysis status. Please try again.");
      }
    } finally {
      inFlight = false;
    }
  }, POLL_INTERVAL_MS);

  return stop;
}
