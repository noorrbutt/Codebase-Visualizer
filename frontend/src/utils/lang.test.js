import { describe, expect, it } from "vitest";
import { COMPLEXITY_COLOR, getLangColor } from "./lang";

describe("getLangColor", () => {
  const styles = {
    getPropertyValue: (name) => `value:${name}`,
  };

  it.each([
    ["Python", "--lang-python"],
    ["JAVASCRIPT", "--lang-javascript"],
    ["tsx", "--lang-typescript"],
    ["unknown", "--lang-default"],
    [undefined, "--lang-default"],
  ])("maps %s to its theme token", (language, token) => {
    expect(getLangColor(language, styles)).toBe(`value:${token}`);
  });

  it("exposes theme tokens for known complexity levels", () => {
    expect(COMPLEXITY_COLOR).toEqual({
      low: "var(--accent-green)",
      medium: "var(--accent-amber)",
      high: "var(--accent-red)",
    });
  });
});
