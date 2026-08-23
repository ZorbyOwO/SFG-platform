export const statusFamilies = {
  enrolment_status: ["ENROLMENT_STARTED", "ENROLMENT_COMPLETED", "ENROLMENT_FAILED", "ENROLMENT_CANCELLED"],
  consent_status: ["CONSENT_GRANTED", "CONSENT_WITHDRAWN", "CONSENT_REQUIRED"],
  template_status: ["TEMPLATE_ACTIVE", "TEMPLATE_REVOKED"],
  capture_status: ["CAPTURE_READY", "NO_FACE", "MULTIPLE_FACES", "INVALID_CAPTURE", "CAMERA_ERROR"],
  liveness_status: ["PAD_LIVE", "PAD_REJECT", "PAD_UNCERTAIN", "PAD_ERROR"],
  match_status: ["MATCH_CONFIRMED", "NO_MATCH", "AMBIGUOUS_MATCH", "MATCH_ERROR"],
  identity_confirmation_status: ["IDENTITY_CONFIRMATION_REQUIRED", "IDENTITY_CONFIRMED", "IDENTITY_REJECTED"],
  pin_status: ["PIN_ACCEPTED", "PIN_REJECTED", "PIN_LOCKED"],
  authorization_status: ["AUTHORIZATION_GRANTED", "AUTHORIZATION_DENIED"],
  service_access_status: ["SERVICE_ACCESS_GRANTED", "SERVICE_ACCESS_DENIED"],
} as const;

export type StatusFamily = keyof typeof statusFamilies;
export type EnrolmentStatus = (typeof statusFamilies.enrolment_status)[number];
export type ConsentStatus = (typeof statusFamilies.consent_status)[number];
export type TemplateStatus = (typeof statusFamilies.template_status)[number];
export type CaptureStatus = (typeof statusFamilies.capture_status)[number];
export type LivenessStatus = (typeof statusFamilies.liveness_status)[number];
export type MatchStatus = (typeof statusFamilies.match_status)[number];
export type PinStatus = (typeof statusFamilies.pin_status)[number];
export type AuthorizationStatus = (typeof statusFamilies.authorization_status)[number];

export function isCanonicalStatus(family: StatusFamily, value: string): boolean {
  return (statusFamilies[family] as readonly string[]).includes(value);
}
