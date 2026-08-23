import type { AppServices } from "../types";
import type { EnrollmentSessionDto, FamilyMemberDto, TransactionDto, WalletDto } from "../../contracts/dto";

const latency = (ms = 180) => new Promise((resolve) => window.setTimeout(resolve, ms));

let signedIn = false;
let balance = 2450.8;
let wallet: WalletDto = {
  wallet_id: "mock-wallet-main", owner_type: "main", owner_id: "mock-citizen",
  family_member_id: null, currency: "MYR", available_balance: balance.toFixed(2),
};
let family: FamilyMemberDto[] = [
  {
    family_member_id: "family-1", full_name: "Aisyah Nur", relationship: "Daughter",
    ic_number_masked: "******-**-1208", enrolment_status: "ENROLMENT_COMPLETED",
    consent_status: "CONSENT_GRANTED", profile_state: "active",
    wallet: { wallet_id: "family-wallet-1", owner_type: "family", owner_id: "family-1", family_member_id: "family-1", currency: "MYR", available_balance: "180.00" },
  },
  {
    family_member_id: "family-2", full_name: "Adam Harith", relationship: "Son",
    ic_number_masked: "******-**-4106", enrolment_status: "ENROLMENT_COMPLETED",
    consent_status: "CONSENT_GRANTED", profile_state: "active",
    wallet: { wallet_id: "family-wallet-2", owner_type: "family", owner_id: "family-2", family_member_id: "family-2", currency: "MYR", available_balance: "95.50" },
  },
];
let transactions: TransactionDto[] = [
  {
    transaction_id: "tx-1", reference: "SFG-8837-1022", type: "purchase", status: "completed", direction: "debit",
    amount: "45.60", balance_after: "2450.80", currency: "MYR", merchant_name: "Kuching Central Market",
    kiosk_id: "SFG-KIOSK-001", family_member_id: null, occurred_at: "2026-08-23T09:41:00+08:00",
  },
  {
    transaction_id: "tx-2", reference: "SFG-8836-0447", type: "topup", status: "completed", direction: "credit",
    amount: "100.00", balance_after: "2496.40", currency: "MYR", merchant_name: null,
    kiosk_id: null, family_member_id: null, occurred_at: "2026-08-22T16:22:00+08:00",
  },
];
let enrollment: EnrollmentSessionDto | null = null;

function refreshWallet(): void {
  wallet = { ...wallet, available_balance: balance.toFixed(2) };
}

export const mockServices: AppServices = {
  mode: "mock",
  auth: {
    async register() {
      await latency();
      signedIn = true;
      return { access_token: "simulated", refresh_token: "simulated", citizen_id: "mock-citizen", enrolment_status: "ENROLMENT_STARTED", next_step: "face_enrolment" };
    },
    async login(ic, password) {
      await latency();
      if (ic.replace(/\D/g, "").length !== 12 || password.length < 1) throw new Error("IC number or password is incorrect.");
      signedIn = true;
      return { access_token: "simulated", refresh_token: "simulated", enrolment_status: "ENROLMENT_COMPLETED" };
    },
    async logout() { signedIn = false; await latency(80); },
    hasSession: () => signedIn,
  },
  biometric: {
    async startEnrollment() {
      await latency();
      enrollment = {
        session_id: crypto.randomUUID(), correlation_id: crypto.randomUUID(), nonce: crypto.randomUUID(),
        expires_at: new Date(Date.now() + 90_000).toISOString(), enrolment_status: "ENROLMENT_STARTED",
      };
      return enrollment;
    },
    async capturePosition(session, pose) {
      await latency();
      if (session.session_id !== enrollment?.session_id) throw new Error("The enrolment session expired.");
      const positions = Array.from(new Set([...((enrollment as EnrollmentSessionDto & { positions?: string[] }).positions ?? []), pose]));
      (enrollment as EnrollmentSessionDto & { positions?: string[] }).positions = positions;
      return { capture_status: "CAPTURE_READY", liveness_status: "PAD_LIVE", frame_index: positions.length, templates_accepted: positions.length, positions_complete: positions };
    },
    async completeEnrollment() { await latency(); },
    async setPin(pin, pinConfirm) { await latency(); if (pin !== pinConfirm) throw new Error("The PIN confirmation does not match."); },
    async activate() { await latency(); },
  },
  wallet: {
    async getWallet() { await latency(); return { ...wallet }; },
    async listWallets() { await latency(); return [wallet, ...family.map((item) => item.wallet)]; },
    async createTopUp(amount, idempotencyKey) {
      await latency();
      if (transactions.some((item) => item.reference === idempotencyKey)) return;
      balance += amount; refreshWallet();
      transactions = [{
        transaction_id: crypto.randomUUID(), reference: idempotencyKey, type: "topup", status: "completed", direction: "credit",
        amount: amount.toFixed(2), balance_after: balance.toFixed(2), currency: "MYR", merchant_name: null,
        kiosk_id: null, family_member_id: null, occurred_at: new Date().toISOString(),
      }, ...transactions];
    },
    async transferToFamilyMember(memberId, amount, _pin, idempotencyKey) {
      await latency();
      if (balance < amount) throw new Error("The main wallet has insufficient funds.");
      balance -= amount; refreshWallet();
      family = family.map((member) => member.family_member_id === memberId ? {
        ...member, wallet: { ...member.wallet, available_balance: (Number(member.wallet.available_balance) + amount).toFixed(2) },
      } : member);
      transactions = [{
        transaction_id: crypto.randomUUID(), reference: idempotencyKey, type: "transfer_out", status: "completed", direction: "debit",
        amount: amount.toFixed(2), balance_after: balance.toFixed(2), currency: "MYR", merchant_name: null,
        kiosk_id: null, family_member_id: memberId, occurred_at: new Date().toISOString(),
      }, ...transactions];
    },
  },
  transactions: {
    async listTransactions() { await latency(); return transactions.map((item) => ({ ...item })); },
    async getTransaction(id) { await latency(); const item = transactions.find((row) => row.transaction_id === id); if (!item) throw new Error("Transaction not found."); return { ...item }; },
  },
  family: {
    async listFamilyMembers() { await latency(); return family.map((item) => ({ ...item, wallet: { ...item.wallet } })); },
    async createFamilyMember(input) {
      await latency();
      const member: FamilyMemberDto = {
        family_member_id: crypto.randomUUID(), full_name: input.full_name, relationship: input.relationship,
        ic_number_masked: `******-**-${input.ic.replace(/\D/g, "").slice(-4)}`,
        enrolment_status: "ENROLMENT_STARTED", consent_status: "CONSENT_REQUIRED", profile_state: "pending_face",
        wallet: { wallet_id: crypto.randomUUID(), owner_type: "family", owner_id: "pending", family_member_id: null, currency: "MYR", available_balance: "0.00" },
      };
      member.wallet.owner_id = member.family_member_id; member.wallet.family_member_id = member.family_member_id;
      family = [...family, member]; return member;
    },
  },
  profile: {
    async getProfile() { await latency(); return { citizen_display_name: "Aisyah Rahman", ic_number_masked: "******-**-5423", enrolment_status: "ENROLMENT_COMPLETED", account_status: "active" }; },
  },
};
