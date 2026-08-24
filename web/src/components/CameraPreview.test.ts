import { describe, expect, it } from "vitest";
import { cameraErrorMessage } from "./CameraPreview";

describe("cameraErrorMessage", () => {
  it("explains permission denial with a recoverable action", () => {
    const result = cameraErrorMessage(new DOMException("blocked", "NotAllowedError"));
    expect(result.status).toBe("denied");
    expect(result.message).toContain("Allow camera access");
  });

  it("distinguishes a missing camera from a busy camera", () => {
    expect(cameraErrorMessage(new DOMException("missing", "NotFoundError")).status).toBe("unavailable");
    expect(cameraErrorMessage(new DOMException("busy", "NotReadableError")).message).toContain("already in use");
  });
});
