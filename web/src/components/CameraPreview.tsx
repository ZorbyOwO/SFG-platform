import { useCallback, useEffect, useRef, useState, type RefObject } from "react";

export type CameraStatus = "idle" | "requesting" | "active" | "denied" | "unavailable" | "error";

export interface CameraController {
  status: CameraStatus;
  stream: MediaStream | null;
  error: string;
  videoRef: RefObject<HTMLVideoElement | null>;
  startCamera(): Promise<boolean>;
  stopCamera(): void;
  captureFrame(): Promise<Blob | null>;
}

/** Longest edge sent to the trusted tier. Keeps uploads small without starving detection. */
const CAPTURE_MAX_EDGE = 960;
const CAPTURE_QUALITY = 0.92;

export function cameraErrorMessage(reason: unknown): { status: Exclude<CameraStatus, "idle" | "requesting" | "active">; message: string } {
  const name = reason instanceof DOMException ? reason.name : "";
  if (name === "NotAllowedError" || name === "SecurityError") {
    return { status: "denied", message: "Camera access was blocked. Allow camera access for this site in your browser settings, then try again." };
  }
  if (name === "NotFoundError" || name === "OverconstrainedError") {
    return { status: "unavailable", message: "No suitable front-facing camera was found on this device." };
  }
  if (name === "NotReadableError" || name === "AbortError") {
    return { status: "error", message: "The camera is already in use or could not start. Close other camera apps and try again." };
  }
  return { status: "error", message: "The camera could not start. Check the device camera and browser permissions, then try again." };
}

export function useCameraPreview(): CameraController {
  const [status, setStatus] = useState<CameraStatus>("idle");
  const [stream, setStream] = useState<MediaStream | null>(null);
  const [error, setError] = useState("");
  const streamRef = useRef<MediaStream | null>(null);
  const requestIdRef = useRef(0);
  const videoRef = useRef<HTMLVideoElement | null>(null);

  /**
   * Grab one frame for the trusted tier.
   *
   * The preview is mirrored for the citizen with a CSS transform only, so the
   * pixels drawn here keep the camera's true orientation. The scratch canvas is
   * cleared and collapsed immediately: the frame exists only long enough to be
   * uploaded, and is never rendered back to the page or stored.
   */
  const captureFrame = useCallback(async (): Promise<Blob | null> => {
    const video = videoRef.current;
    if (!video || video.readyState < 2) return null;
    const sourceWidth = video.videoWidth;
    const sourceHeight = video.videoHeight;
    if (!sourceWidth || !sourceHeight) return null;

    const scale = Math.min(1, CAPTURE_MAX_EDGE / Math.max(sourceWidth, sourceHeight));
    const width = Math.round(sourceWidth * scale);
    const height = Math.round(sourceHeight * scale);

    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    const context = canvas.getContext("2d", { willReadFrequently: false });
    if (!context) return null;
    try {
      context.drawImage(video, 0, 0, width, height);
      return await new Promise<Blob | null>((resolve) => {
        canvas.toBlob((blob) => resolve(blob), "image/jpeg", CAPTURE_QUALITY);
      });
    } finally {
      context.clearRect(0, 0, width, height);
      canvas.width = 0;
      canvas.height = 0;
    }
  }, []);

  const stopCamera = useCallback(() => {
    requestIdRef.current += 1;
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    setStream(null);
    setStatus("idle");
    setError("");
  }, []);

  const startCamera = useCallback(async (): Promise<boolean> => {
    if (streamRef.current?.getVideoTracks().some((track) => track.readyState === "live")) {
      setStatus("active");
      return true;
    }
    const mediaDevices = navigator.mediaDevices;
    if (!window.isSecureContext || !mediaDevices?.getUserMedia) {
      setStatus("unavailable");
      setError("Camera preview requires HTTPS or a trusted localhost address in a supported browser.");
      return false;
    }

    const requestId = requestIdRef.current + 1;
    requestIdRef.current = requestId;
    setStatus("requesting");
    setError("");
    try {
      const nextStream = await mediaDevices.getUserMedia({
        audio: false,
        video: {
          facingMode: "user",
          width: { ideal: 1280 },
          height: { ideal: 720 },
        },
      });
      if (requestIdRef.current !== requestId) {
        nextStream.getTracks().forEach((track) => track.stop());
        return false;
      }
      streamRef.current?.getTracks().forEach((track) => track.stop());
      streamRef.current = nextStream;
      setStream(nextStream);
      setStatus("active");
      const videoTrack = nextStream.getVideoTracks()[0];
      videoTrack?.addEventListener("ended", () => {
        if (streamRef.current === nextStream) {
          streamRef.current = null;
          setStream(null);
          setStatus("error");
          setError("The camera stopped. Enable it again to continue.");
        }
      }, { once: true });
      return true;
    } catch (reason) {
      if (requestIdRef.current !== requestId) return false;
      const cameraError = cameraErrorMessage(reason);
      setStatus(cameraError.status);
      setError(cameraError.message);
      return false;
    }
  }, []);

  useEffect(() => () => {
    requestIdRef.current += 1;
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
  }, []);

  return { status, stream, error, videoRef, startCamera, stopCamera, captureFrame };
}

interface CameraPreviewProps {
  camera: CameraController;
  disabled?: boolean;
  compact?: boolean;
}

export function CameraPreview({ camera, disabled = false, compact = false }: CameraPreviewProps) {
  const videoRef = camera.videoRef;

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;
    video.srcObject = camera.stream;
    if (camera.stream) void video.play().catch(() => undefined);
    return () => { video.srcObject = null; };
  }, [camera.stream, videoRef]);

  const active = camera.status === "active" && Boolean(camera.stream);
  return <div className={`camera-preview ${compact ? "compact" : ""} ${active ? "active" : ""}`} data-camera-status={camera.status}>
    <video ref={videoRef} autoPlay muted playsInline aria-label="Live front camera preview" />
    {!active && <div className="camera-permission-state" role="status" aria-live="polite">
      <span className={`camera-permission-icon ${camera.status}`} aria-hidden="true">{camera.status === "requesting" ? "…" : "◉"}</span>
      <strong>{camera.status === "requesting" ? "Waiting for camera permission" : camera.status === "idle" ? "Camera preview is off" : "Camera access needed"}</strong>
      <p>{camera.error || (disabled ? "Confirm consent before enabling the camera." : "Your browser will ask permission to use this device’s front camera.")}</p>
      {camera.status !== "requesting" && <button className="button secondary camera-enable" type="button" onClick={() => void camera.startCamera()} disabled={disabled}>
        {camera.status === "idle" ? "Enable camera preview" : "Try camera again"}
      </button>}
    </div>}
    {active && <div className="camera-live-badge" role="status"><i />Live preview</div>}
    {active && <button className="camera-stop" type="button" onClick={camera.stopCamera}>Turn off camera</button>}
  </div>;
}
