import { describe, expect, it } from "vitest";
import { errorMessage, normalizeRepoInput } from "./repoInput";

describe("normalizeRepoInput", () => {
  it.each([
    ["owner/repo", "https://github.com/owner/repo"],
    ["https://github.com/owner/repo", "https://github.com/owner/repo"],
    ["http://github.com/owner/repo", "https://github.com/owner/repo"],
    ["www.github.com/owner/repo", "https://github.com/owner/repo"],
    ["https://www.github.com/owner/repo", "https://github.com/owner/repo"],
    ["github.com/owner/repo", "https://github.com/owner/repo"],
    ["https://github.com/owner/repo/tree/main", "https://github.com/owner/repo"],
    ["owner/repo/tree/main/src", "https://github.com/owner/repo"],
    ["owner/repo.git", "https://github.com/owner/repo"],
    ["https://github.com/owner/repo.git/tree/main", "https://github.com/owner/repo"],
  ])("normalizes %s", (input, url) => {
    expect(normalizeRepoInput(input)).toEqual({ url });
  });

  it.each([
    ["", "Paste a GitHub repository URL or owner/repo to get started."],
    ["https://example.com/owner/repo", "Repository must be hosted on github.com."],
    ["https://github.com/owner", "Enter a GitHub repository as owner/repo."],
    ["owner/.repo", "Enter a valid GitHub repository as owner/repo."],
  ])("rejects %s", (input, error) => {
    expect(normalizeRepoInput(input)).toEqual({ error });
  });
});

describe("errorMessage", () => {
  it("returns a string detail directly", () => {
    expect(errorMessage({ detail: "Repository not found" })).toBe("Repository not found");
  });

  it("joins validation error messages from an array detail", () => {
    expect(errorMessage({
      detail: [
        { loc: ["body", "github_url"], msg: "Invalid URL" },
        { loc: ["body", "force"], msg: "Not a valid boolean" },
      ],
    })).toBe("Invalid URL; Not a valid boolean");
  });
});
