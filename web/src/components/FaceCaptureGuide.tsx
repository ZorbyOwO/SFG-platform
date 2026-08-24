import { CameraPreview, type CameraController } from "./CameraPreview";

export const REQUIRED_FACE_POSES = [
  { id: "front", label: "Look straight", shortLabel: "Front", instruction: "Face the camera directly and keep both eyes visible." },
  { id: "right", label: "Turn slightly right", shortLabel: "Right", instruction: "Turn your head slightly to your right without moving your shoulders." },
  { id: "left", label: "Turn slightly left", shortLabel: "Left", instruction: "Turn your head slightly to your left and keep your chin level." },
] as const;

interface FaceCaptureGuideProps {
  positions: string[];
  busy: boolean;
  /** True only when no real face processing is connected for this flow. */
  simulation: boolean;
  camera: CameraController;
  /** Wording for the most recent rejected capture, shown as recoverable guidance. */
  guidance?: string;
  onCapture(pose: string): void;
  onComplete(): void;
  completeLabel: string;
}

export function FaceCaptureGuide({ positions, busy, simulation, camera, guidance, onCapture, onComplete, completeLabel }: FaceCaptureGuideProps) {
  const nextPose = REQUIRED_FACE_POSES.find((pose) => !positions.includes(pose.id)) ?? REQUIRED_FACE_POSES[0];
  const allComplete = positions.length >= REQUIRED_FACE_POSES.length;
  const progress = Math.min(100, Math.round((positions.length / REQUIRED_FACE_POSES.length) * 100));

  return <div className="guided-capture">
    <div className="capture-progress" aria-label={`${positions.length} of ${REQUIRED_FACE_POSES.length} face positions ready`}>
      <div><span>Capture progress</span><strong>{positions.length}/{REQUIRED_FACE_POSES.length}</strong></div>
      <div className="progress-track"><span style={{ width: `${progress}%` }} /></div>
    </div>

    <div className={`capture-panel camera-stage pose-${nextPose.id}`}>
      <CameraPreview camera={camera} />
      <div className="camera-stage-header">
        <span className={`camera-status ${camera.status === "active" ? "active" : ""}`}><i />{camera.status === "active" ? "Camera ready" : "Camera permission required"}</span>
        <span>{simulation ? "Preview only · CV not connected" : "Face detection and liveness active"}</span>
      </div>
      <div className="face-guide" aria-hidden="true"><span /></div>
      <div className="capture-instruction">
        <strong>{allComplete ? "All positions captured" : nextPose.label}</strong>
        <p>{allComplete ? "Review each accepted position below before continuing." : nextPose.instruction}</p>
      </div>
      <div className="capture-quality" aria-label="Capture checks">
        <span>Camera on</span><span>Face in guide</span><span>{simulation ? "CV checks later" : "Liveness checked"}</span>
      </div>
    </div>

    {guidance && <div className="capture-guidance" role="status" aria-live="polite">{guidance}</div>}

    {simulation
      ? <p className="capture-disclaimer">The live preview stays on this device. Capture controls currently record only the guided position state; CoreCV analysis and frame upload are not connected.</p>
      : <p className="capture-disclaimer">Each capture is checked for a single live face on the SFG server, converted to an encrypted template, and the photo itself is discarded. No image is stored or shown again.</p>}

    <div className="pose-grid" aria-label="Required face positions">
      {REQUIRED_FACE_POSES.map((pose) => {
        const complete = positions.includes(pose.id);
        const active = !allComplete && pose.id === nextPose.id;
        return <button
          key={pose.id}
          type="button"
          className={`pose-card ${complete ? "complete" : ""} ${active ? "active" : ""}`}
          onClick={() => onCapture(pose.id)}
          disabled={busy || camera.status !== "active"}
          aria-label={`${complete ? "Retake" : "Capture"} ${pose.shortLabel.toLowerCase()} position`}
        >
          <span>{complete ? "✓" : positions.indexOf(pose.id) + 1 || REQUIRED_FACE_POSES.findIndex((item) => item.id === pose.id) + 1}</span>
          <strong>{pose.shortLabel}</strong>
          <small>{complete ? "Accepted · Retake" : active ? "Ready now" : "Required"}</small>
        </button>;
      })}
    </div>

    {!allComplete ? <button className="button primary full capture-primary" type="button" onClick={() => onCapture(nextPose.id)} disabled={busy || camera.status !== "active"}>
      {busy ? (simulation ? "Recording position…" : "Checking face and liveness…") : camera.status !== "active" ? "Enable camera to capture" : `Capture ${nextPose.shortLabel.toLowerCase()} position`}
    </button> : <div className="capture-ready-card" role="status">
      <span aria-hidden="true">✓</span>
      <div><strong>Face capture is ready</strong><p>{simulation ? "Front, right, and left positions were recorded for this development flow." : "Front, right, and left positions passed the face and liveness checks."}</p></div>
      <button className="button primary" type="button" onClick={onComplete} disabled={busy}>{busy ? "Finishing…" : completeLabel}</button>
    </div>}
  </div>;
}
