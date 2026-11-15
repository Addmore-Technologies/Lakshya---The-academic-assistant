import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, apiRequest } from "@/lib/api";

describe("API connectivity errors", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("returns an actionable message when the browser cannot reach the API", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));

    await expect(apiRequest("/health", { auth: false })).rejects.toMatchObject({
      name: "ApiError",
      status: 0,
      code: "NETWORK_ERROR",
      message: expect.stringContaining("CORS settings"),
    });
  });

  it("does not misreport an HTTP authentication failure as a network error", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ error: { code: "INVALID_CREDENTIALS", message: "Invalid credentials" } }), {
          status: 401,
          headers: { "content-type": "application/json" },
        }),
      ),
    );

    await expect(apiRequest("/auth/login", { method: "POST", body: {}, auth: false })).rejects.toMatchObject({
      name: "ApiError",
      status: 401,
      code: "INVALID_CREDENTIALS",
      message: "Invalid credentials",
    } satisfies Partial<ApiError>);
  });
});
