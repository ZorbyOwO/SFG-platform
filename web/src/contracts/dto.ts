import type { AuthorizationStatus, CaptureStatus, ConsentStatus, EnrolmentStatus, LivenessStatus, MatchStatus, PinStatus, TemplateStatus } from "./statuses";

export interface RegisterDto {
  ic: string;
  full_name: string;
  email: string;
  password: string;
  password_confirm: string;
}

export interface AuthDto {
  access_token: string;
  refresh_token: string;
  enrolment_status: EnrolmentStatus;
  citizen_id?: string;
  next_step?: string;
}

export interface EnrollmentSessionDto {
  session_id: string;
  correlation_id: string;
  nonce: string;
  expires_at: string;
  enrolment_status: EnrolmentStatus;
}

export interface CaptureDto {
  capture_status: CaptureStatus;
  liveness_status?: LivenessStatus;
  frame_index?: number;
  templates_accepted: number;
  positions_complete: string[];
}

export interface WalletDto {
  wallet_id: string;
  owner_type: "main" | "family";
  owner_id: string;
  family_member_id: string | null;
  currency: "MYR";
  available_balance: string;
}

export interface TransactionDto {
  transaction_id: string;
  reference: string;
  type: "topup" | "purchase" | "transfer_out" | "transfer_in" | "reversal";
  status: "pending" | "completed" | "failed";
  direction: "credit" | "debit";
  amount: string;
  balance_after: string;
  currency: "MYR";
  merchant_name: string | null;
  kiosk_id: string | null;
  family_member_id: string | null;
  occurred_at: string;
}

export interface FamilyMemberDto {
  family_member_id: string;
  full_name: string;
  relationship: string;
  ic_number_masked: string;
  enrolment_status: EnrolmentStatus;
  consent_status: ConsentStatus;
  profile_state: string;
  wallet: WalletDto;
}

export interface PaymentResultDto {
  pin_status: PinStatus;
  authorization_status: AuthorizationStatus;
  verification_completed_at: string;
  transaction_id: string;
  reference: string;
  amount: string;
  merchant_name: string;
  balance_after: string;
}

export interface IdentificationDto {
  capture_status: CaptureStatus;
  liveness_status: LivenessStatus;
  match_status: MatchStatus;
  citizen_display_name?: string;
  masked_ic?: string;
  amount: string;
}

export interface EnrolCompleteDto {
  enrolment_status: EnrolmentStatus;
  template_status: TemplateStatus;
  templates_stored: number;
  next_step: string;
}
