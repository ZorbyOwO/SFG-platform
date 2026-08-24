import { type FormEvent, useEffect, useState } from "react";
import type { EnrollmentSessionDto } from "../contracts/dto";
import type { FamilyMember } from "../models/domain";
import { services } from "../services";
import { CameraPreview, useCameraPreview } from "./CameraPreview";
import { FaceCaptureGuide, REQUIRED_FACE_POSES } from "./FaceCaptureGuide";

interface FamilyEnrollmentModalProps {
  member: FamilyMember;
  onClose: () => void;
  onComplete: () => Promise<void>;
}

export function FamilyEnrollmentModal({ member, onClose, onComplete }: FamilyEnrollmentModalProps) {
  const [consent, setConsent] = useState(false);
  const [session, setSession] = useState<EnrollmentSessionDto | null>(null);
  const [positions, setPositions] = useState<string[]>([]);
  const [completed, setCompleted] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const camera = useCameraPreview();

  useEffect(() => {
    const previousOverflow = document.body.style.overflow;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !busy) { camera.stopCamera(); onClose(); }
    };
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", closeOnEscape);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", closeOnEscape);
    };
  }, [busy, onClose, camera.stopCamera]);

  const closeModal = () => { camera.stopCamera(); onClose(); };

  const start = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!consent) return;
    setError("");
    const cameraReady = camera.status === "active" || await camera.startCamera();
    if (!cameraReady) return;
    setBusy(true);
    setError("");
    try {
      setSession(await services.family.startEnrollment(member.id));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to start face enrolment.");
    } finally {
      setBusy(false);
    }
  };

  const capture = async (pose: string) => {
    if (!session) return;
    if (camera.status !== "active") { setError("Enable the camera preview before recording a position."); return; }
    setBusy(true);
    setError("");
    try {
      const result = await services.family.capturePosition(member.id, session, pose);
      if (result.capture_status !== "CAPTURE_READY" || result.liveness_status !== "PAD_LIVE") {
        throw new Error("The development capture did not pass. Try again.");
      }
      setPositions(result.positions_complete);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to capture this position.");
    } finally {
      setBusy(false);
    }
  };

  const finish = async () => {
    if (!session || positions.length < REQUIRED_FACE_POSES.length) return;
    setBusy(true);
    setError("");
    try {
      await services.family.completeEnrollment(member.id, session.session_id);
      await onComplete();
      camera.stopCamera();
      setCompleted(true);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to complete face enrolment.");
    } finally {
      setBusy(false);
    }
  };

  return <div className="modal-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget && !busy) closeModal(); }}>
    <section className="modal-card family-enrolment-modal" role="dialog" aria-modal="true" aria-labelledby="family-enrolment-title">
      <div className="topup-modal-header">
        <div>
          <p className="eyebrow">Family Member enrolment</p>
          <h2 id="family-enrolment-title">{completed ? "Face enrolment complete" : `Capture ${member.fullName}'s face`}</h2>
        </div>
        <button className="modal-close" type="button" onClick={closeModal} disabled={busy} aria-label="Close face enrolment">×</button>
      </div>

      {completed ? <div className="enrolment-complete" role="status">
        <span aria-hidden="true">✓</span>
        <h3>{member.fullName} is ready</h3>
        <p>The Family Member profile is active and can now receive wallet transfers.</p>
        <button className="button primary full" type="button" onClick={closeModal}>Done</button>
      </div> : !session ? <form className="enrolment-consent" onSubmit={start}>
        <div className="enrolment-step"><span>Step 2 of 2</span><strong>Face capture</strong></div>
        <p>Face enrolment is required before this Family Member can receive transfers.</p>
        <CameraPreview camera={camera} compact disabled={!consent} />
        <div className="notice-card">
          <strong>Live preview with development capture</strong>
          <p>The camera preview is real and remains on this device. The prototype records only the three completed position states; CoreCV analysis and frame upload are not connected.</p>
        </div>
        <label className="check-row">
          <input type="checkbox" checked={consent} onChange={(event) => setConsent(event.target.checked)} />
          I confirm this Family Member, or their guardian where required, has agreed to face enrolment for this prototype.
        </label>
        {error && <div className="form-error" role="alert">{error}</div>}
        <button className="button primary full" disabled={!consent || busy || camera.status === "requesting"}>{busy ? "Starting…" : camera.status === "requesting" ? "Waiting for camera permission…" : "Enable camera and start capture"}</button>
      </form> : <div className="family-capture-flow">
        <div className="enrolment-step"><span>Step 2 of 2</span><strong>{positions.length} of {REQUIRED_FACE_POSES.length} positions captured</strong></div>
        <FaceCaptureGuide positions={positions} busy={busy} simulation camera={camera} onCapture={(pose) => void capture(pose)} onComplete={() => void finish()} completeLabel="Complete face enrolment" />
        {error && <div className="form-error" role="alert">{error}</div>}
      </div>}
    </section>
  </div>;
}
