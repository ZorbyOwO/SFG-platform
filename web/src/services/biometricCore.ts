/**
 * Client for the trusted CoreCV enrolment tier.
 *
 * Frames go straight from the live camera to this API and are never stored,
 * rendered back, or kept in component state. Only canonical statuses and
 * progress counters come back; a template never reaches the browser.
 */
import type { CaptureStatus, LivenessStatus } from "../contracts/statuses";

const baseUrl = (import.meta.env.VITE_API_BASE_URL as string | undefined) || "http://127.0.0.1:8000";

export type BiometricPurpose = "enrol" | "reenrol";

export interface BiometricSessionDto {
  session_id: string;
  correlation_id: string;
  nonce: string;
  expires_at: string;
  purpose: BiometricPurpose;
  required_positions: string[];
  positions_complete: string[];
  templates_accepted: number;
}

export interface BiometricCaptureDto {
  capture_status: CaptureStatus;
  liveness_status?: LivenessStatus;
  diagnostic_code?: string;
  positions_complete: string[];
  templates_accepted: number;
  required_positions: string[];
}

export interface BiometricCompleteDto {
  enrolment_status: string;
  template_status: string;
  templates_stored: number;
  purpose: BiometricPurpose;
  next_step: string;
}

export interface BiometricStatusDto {
  templates_stored: number;
  template_status: string | null;
  enrolment_status: string;
  positions_complete: string[];
  required_positions: string[];
}

export class BiometricCoreError extends Error {
  readonly code: string;

  constructor(message: string, code: string) {
    super(message);
    this.name = "BiometricCoreError";
    this.code = code;
  }
}

/**
 * Citizen-facing wording for each canonical outcome.
 *
 * These are guidance, not accusations: a rejected liveness result usually means
 * poor lighting or a reflection, so the copy tells the citizen what to change.
 */
export function captureGuidance(result: BiometricCaptureDto): string {
  switch (result.capture_status) {
    case "NO_FACE":
      return "No face was detected. Move into the guide, make sure the area is well lit, and try again.";
    case "MULTIPLE_FACES":
      return "More than one face is visible. Enrol alone, with nobody else in the camera view.";
    case "INVALID_CAPTURE":
      return "The capture was unclear. Centre your whole face in the guide and hold still.";
    case "CAMERA_ERROR":
      return "The camera could not deliver a usable frame. Check the device camera and try again.";
    case "CAPTURE_READY":
      break;
  }
  switch (result.liveness_status) {
    case "PAD_REJECT":
      return "The liveness check did not pass. Face the camera directly in even lighting, and do not hold up a photo or screen.";
    case "PAD_UNCERTAIN":
      return "The liveness check was inconclusive. Improve the lighting, remove glare or reflections, and try again.";
    case "PAD_ERROR":
      return "The liveness check could not complete. Try again in a moment.";
    default:
      return "This capture was not accepted. Adjust your position and try again.";
  }
}

export function isAccepted(result: BiometricCaptureDto): boolean {
  return result.capture_status === "CAPTURE_READY" && result.liveness_status === "PAD_LIVE";
}

async function call<T>(path: string, token: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");

  let response: Response;
  try {
    response = await fetch(`${baseUrl}${path}`, { ...init, headers });
  } catch {
    throw new BiometricCoreError(
      "The face recognition service could not be reached. Make sure the SFG services are running.",
      "service_unreachable",
    );
  }

  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as { error?: string; message?: string };
    throw new BiometricCoreError(
      body.message || "The face recognition service could not complete the request.",
      body.error || `http_${response.status}`,
    );
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export const biometricCore = {
  async startSession(token: string, purpose: BiometricPurpose): Promise<BiometricSessionDto> {
    return call<BiometricSessionDto>("/biometric/session", token, {
      method: "POST",
      body: JSON.stringify({ purpose }),
    });
  },

  async capture(
    token: string,
    session: BiometricSessionDto,
    pose: string,
    frame: Blob,
  ): Promise<BiometricCaptureDto> {
    const form = new FormData();
    form.set("session_id", session.session_id);
    form.set("nonce", session.nonce);
    form.set("pose", pose);
    form.set("frame", frame, "capture.jpg");
    return call<BiometricCaptureDto>("/biometric/capture", token, { method: "POST", body: form });
  },

  async complete(token: string, session: BiometricSessionDto): Promise<BiometricCompleteDto> {
    return call<BiometricCompleteDto>("/biometric/complete", token, {
      method: "POST",
      body: JSON.stringify({ session_id: session.session_id }),
    });
  },

  async cancel(token: string, session: BiometricSessionDto): Promise<void> {
    await call<void>("/biometric/cancel", token, {
      method: "POST",
      body: JSON.stringify({ session_id: session.session_id }),
    }).catch(() => undefined);
  },

  async status(token: string): Promise<BiometricStatusDto> {
    return call<BiometricStatusDto>("/biometric/status", token);
  },
};
