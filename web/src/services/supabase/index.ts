import { createClient, type AuthError, type PostgrestError } from "@supabase/supabase-js";
import type {
  AuthDto,
  CaptureDto,
  EnrollmentSessionDto,
  FamilyMemberDto,
  RegisterDto,
  TransactionDto,
  WalletDto,
} from "../../contracts/dto";
import type { Database } from "../../contracts/database.types";
import type { AppServices } from "../types";

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL as string | undefined;
const supabasePublishableKey = import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY as string | undefined;
const sessionFlag = "sfg:supabase-session";

if (!supabaseUrl || !supabasePublishableKey) {
  console.warn("Supabase mode requires VITE_SUPABASE_URL and VITE_SUPABASE_PUBLISHABLE_KEY.");
}

const supabase = createClient<Database>(supabaseUrl ?? "https://invalid.supabase.co", supabasePublishableKey ?? "missing", {
  auth: {
    persistSession: true,
    autoRefreshToken: true,
    detectSessionInUrl: true,
  },
});

interface ProfileRow {
  id: string;
  ic_number: string;
  full_name: string;
  email: string;
  enrolment_status: string;
  consent_status: string;
  profile_state: string;
}

interface WalletRow {
  id: string;
  user_id: string;
  family_member_id: string | null;
  balance: number | string;
  currency: "MYR";
}

interface TransactionRow {
  id: string;
  reference: string;
  type: TransactionDto["type"];
  status: TransactionDto["status"];
  amount: number | string;
  balance_after: number | string;
  merchant_name: string | null;
  kiosk_id: string | null;
  family_member_id: string | null;
  created_at: string;
}

interface FamilyRow {
  id: string;
  ic_number: string;
  full_name: string;
  relationship: string;
  enrolment_status: FamilyMemberDto["enrolment_status"];
  consent_status: FamilyMemberDto["consent_status"];
  profile_state: string;
}

let activeEnrollment: (EnrollmentSessionDto & { positions: string[] }) | null = null;
let activeFamilyEnrollment: (EnrollmentSessionDto & { familyMemberId: string; positions: string[] }) | null = null;

function assertConfigured(): void {
  if (!supabaseUrl || !supabasePublishableKey) {
    throw new Error("Supabase is not configured. Restart SFG after adding the project settings.");
  }
}

function internalIdentityEmail(ic: string): string {
  return `ic-${normalizeIc(ic)}@login.sfg.example`;
}

function normalizeIc(ic: string): string {
  const normalized = ic.replace(/\D/g, "");
  if (normalized.length !== 12) throw new Error("Enter a valid 12-digit IC number.");
  return normalized;
}

function maskIc(ic: string): string {
  return `******-**-${ic.replace(/\D/g, "").slice(-4)}`;
}

function money(value: number | string): string {
  return Number(value).toFixed(2);
}

function readableError(error: AuthError | PostgrestError | Error | null, fallback: string): Error {
  const message = error?.message ?? fallback;
  const normalized = message.toLowerCase();
  if (normalized.includes("invalid login credentials")) return new Error("IC number or password is incorrect.");
  if (normalized.includes("email not confirmed")) return new Error("This account is not ready for login.");
  if (normalized.includes("enrolment_incomplete")) return new Error("Finish registration before using the wallet.");
  if (normalized.includes("insufficient_funds")) return new Error("The main wallet has insufficient funds.");
  if (normalized.includes("wrong_pin")) return new Error("The PIN was not accepted.");
  if (normalized.includes("ic_already_registered")) return new Error("That IC number is already registered.");
  if (normalized.includes("family_limit_reached")) return new Error("The Family Member limit has been reached.");
  return new Error(message || fallback);
}

async function requireUserId(): Promise<string> {
  assertConfigured();
  const { data, error } = await supabase.auth.getUser();
  if (error || !data.user) {
    window.localStorage.removeItem(sessionFlag);
    throw new Error("Your session has expired. Log in again.");
  }
  return data.user.id;
}

async function getProfileRow(): Promise<ProfileRow> {
  const userId = await requireUserId();
  const { data, error } = await supabase
    .from("profiles")
    .select("id,ic_number,full_name,email,enrolment_status,consent_status,profile_state")
    .eq("id", userId)
    .single();
  if (error || !data) throw readableError(error, "Unable to load your profile.");
  return data as ProfileRow;
}

function authDto(profile: ProfileRow, accessToken: string, refreshToken: string): AuthDto {
  return {
    access_token: accessToken,
    refresh_token: refreshToken,
    citizen_id: profile.id,
    enrolment_status: profile.enrolment_status as AuthDto["enrolment_status"],
    next_step: profile.profile_state === "active" ? "dashboard" : profile.profile_state,
  };
}

async function signIn(ic: string, password: string): Promise<AuthDto> {
  assertConfigured();
  const { data, error } = await supabase.auth.signInWithPassword({
    email: internalIdentityEmail(ic),
    password,
  });
  if (error || !data.session) throw readableError(error, "Unable to log in.");
  window.localStorage.setItem(sessionFlag, "1");
  try {
    const profile = await getProfileRow();
    return authDto(profile, data.session.access_token, data.session.refresh_token);
  } catch (error) {
    await supabase.auth.signOut();
    window.localStorage.removeItem(sessionFlag);
    throw error;
  }
}

async function registrationError(error: Error): Promise<Error> {
  const context = (error as Error & { context?: unknown }).context;
  if (context instanceof Response) {
    const payload = await context.clone().json().catch(() => null) as { message?: string } | null;
    if (payload?.message) return new Error(payload.message);
  }
  return readableError(error, "Unable to register right now.");
}

function mapWalletRow(row: WalletRow): WalletDto {
  const familyMemberId = row.family_member_id;
  return {
    wallet_id: row.id,
    owner_type: familyMemberId ? "family" : "main",
    owner_id: familyMemberId ?? row.user_id,
    family_member_id: familyMemberId,
    currency: "MYR",
    available_balance: money(row.balance),
  };
}

function mapTransactionRow(row: TransactionRow): TransactionDto {
  const credit = row.type === "topup" || row.type === "transfer_in" || row.type === "reversal";
  return {
    transaction_id: row.id,
    reference: row.reference,
    type: row.type,
    status: row.status,
    direction: credit ? "credit" : "debit",
    amount: money(row.amount),
    balance_after: money(row.balance_after),
    currency: "MYR",
    merchant_name: row.merchant_name,
    kiosk_id: row.kiosk_id,
    family_member_id: row.family_member_id,
    occurred_at: row.created_at,
  };
}

async function listWalletRows(): Promise<WalletRow[]> {
  await requireUserId();
  const { data, error } = await supabase
    .from("wallets")
    .select("id,user_id,family_member_id,balance,currency")
    .order("updated_at", { ascending: false });
  if (error) throw readableError(error, "Unable to load wallets.");
  return (data ?? []) as WalletRow[];
}

async function listFamilyDtos(): Promise<FamilyMemberDto[]> {
  await requireUserId();
  const [{ data: members, error: memberError }, wallets] = await Promise.all([
    supabase
      .from("family_members")
      .select("id,ic_number,full_name,relationship,enrolment_status,consent_status,profile_state")
      .order("created_at", { ascending: true }),
    listWalletRows(),
  ]);
  if (memberError) throw readableError(memberError, "Unable to load Family Members.");
  const walletByMember = new Map(wallets.filter((row) => row.family_member_id).map((row) => [row.family_member_id, row]));
  return ((members ?? []) as FamilyRow[]).map((member) => {
    const wallet = walletByMember.get(member.id);
    if (!wallet) throw new Error(`Wallet data is missing for ${member.full_name}.`);
    return {
      family_member_id: member.id,
      full_name: member.full_name,
      relationship: member.relationship,
      ic_number_masked: maskIc(member.ic_number),
      enrolment_status: member.enrolment_status,
      consent_status: member.consent_status,
      profile_state: member.profile_state,
      wallet: mapWalletRow(wallet),
    };
  });
}

export const supabaseServices: AppServices = {
  mode: "supabase",
  auth: {
    async register(payload: RegisterDto) {
      assertConfigured();
      normalizeIc(payload.ic);
      const { error } = await supabase.functions.invoke("register-citizen", { body: payload });
      if (error) throw await registrationError(error);
      return signIn(payload.ic, payload.password);
    },
    login: signIn,
    async logout() {
      const { error } = await supabase.auth.signOut();
      window.localStorage.removeItem(sessionFlag);
      if (error) throw readableError(error, "Unable to log out.");
    },
    hasSession: () => window.localStorage.getItem(sessionFlag) === "1",
    async restoreSession() {
      if (window.localStorage.getItem(sessionFlag) !== "1") return false;
      const { data, error } = await supabase.auth.getUser();
      const valid = !error && Boolean(data.user);
      if (!valid) window.localStorage.removeItem(sessionFlag);
      return valid;
    },
    // The trusted tier re-verifies this token with Supabase before reading a frame.
    async getAccessToken() {
      const { data, error } = await supabase.auth.getSession();
      if (error || !data.session) return null;
      return data.session.access_token;
    },
  },
  biometric: {
    async startEnrollment() {
      await requireUserId();
      const { error } = await supabase.rpc("sfg_start_enrolment");
      if (error) throw readableError(error, "Unable to start enrolment.");
      activeEnrollment = {
        session_id: crypto.randomUUID(),
        correlation_id: crypto.randomUUID(),
        nonce: crypto.randomUUID(),
        expires_at: new Date(Date.now() + 15 * 60_000).toISOString(),
        enrolment_status: "ENROLMENT_STARTED",
        positions: [],
      };
      return activeEnrollment;
    },
    async capturePosition(session: EnrollmentSessionDto, pose: string): Promise<CaptureDto> {
      if (!activeEnrollment || session.session_id !== activeEnrollment.session_id) {
        throw new Error("The enrolment session expired. Start again.");
      }
      if (Date.now() >= new Date(activeEnrollment.expires_at).getTime()) {
        activeEnrollment = null;
        throw new Error("The enrolment session expired. Start again.");
      }
      activeEnrollment.positions = Array.from(new Set([...activeEnrollment.positions, pose]));
      return {
        capture_status: "CAPTURE_READY",
        liveness_status: "PAD_LIVE",
        frame_index: activeEnrollment.positions.length,
        templates_accepted: activeEnrollment.positions.length,
        positions_complete: [...activeEnrollment.positions],
      };
    },
    async completeEnrollment(sessionId: string) {
      if (!activeEnrollment || activeEnrollment.session_id !== sessionId || activeEnrollment.positions.length < 3) {
        throw new Error("Capture all three positions before continuing.");
      }
      const { error } = await supabase.rpc("sfg_complete_dev_enrolment");
      if (error) throw readableError(error, "Unable to complete enrolment.");
      activeEnrollment = null;
    },
    async setPin(pin: string, pinConfirm: string) {
      if (pin !== pinConfirm) throw new Error("The PIN confirmation does not match.");
      if (!/^\d{6}$/.test(pin)) throw new Error("Enter a six-digit PIN.");
      const { error } = await supabase.rpc("sfg_set_registration_pin", { p_pin: pin });
      if (error) throw readableError(error, "Unable to save the PIN.");
    },
    async activate() {
      const { error } = await supabase.rpc("sfg_activate_profile");
      if (error) throw readableError(error, "Unable to activate the profile.");
    },
  },
  wallet: {
    async getWallet() {
      const wallets = await listWalletRows();
      const main = wallets.find((wallet) => wallet.family_member_id === null);
      if (!main) throw new Error("Your main wallet is not available.");
      return mapWalletRow(main);
    },
    async listWallets() {
      return (await listWalletRows()).map(mapWalletRow);
    },
    async createTopUp(amount, idempotencyKey) {
      await requireUserId();
      const { error } = await supabase.rpc("sfg_user_topup_wallet", {
        p_amount: amount,
        p_idempotency_key: idempotencyKey,
      });
      if (error) throw readableError(error, "Top-up failed.");
    },
    async transferToFamilyMember(familyMemberId, amount, pin, idempotencyKey) {
      await requireUserId();
      const { error } = await supabase.rpc("sfg_user_transfer_to_family", {
        p_family_member_id: familyMemberId,
        p_amount: amount,
        p_pin: pin,
        p_idempotency_key: idempotencyKey,
      });
      if (error) throw readableError(error, "Unable to transfer funds.");
    },
  },
  transactions: {
    async listTransactions() {
      await requireUserId();
      const { data, error } = await supabase
        .from("transactions")
        .select("id,reference,type,status,amount,balance_after,merchant_name,kiosk_id,family_member_id,created_at")
        .order("created_at", { ascending: false });
      if (error) throw readableError(error, "Unable to load transaction history.");
      return ((data ?? []) as TransactionRow[]).map(mapTransactionRow);
    },
    async getTransaction(id) {
      await requireUserId();
      const { data, error } = await supabase
        .from("transactions")
        .select("id,reference,type,status,amount,balance_after,merchant_name,kiosk_id,family_member_id,created_at")
        .eq("id", id)
        .single();
      if (error || !data) throw readableError(error, "Transaction not found.");
      return mapTransactionRow(data as TransactionRow);
    },
  },
  family: {
    listFamilyMembers: listFamilyDtos,
    async createFamilyMember(input) {
      await requireUserId();
      const { data: memberId, error } = await supabase.rpc("sfg_create_family_member", {
        p_ic: input.ic,
        p_full_name: input.full_name,
        p_relationship: input.relationship,
        p_idempotency_key: input.idempotency_key,
      });
      if (error) throw readableError(error, "Unable to create the Family Member.");
      const members = await listFamilyDtos();
      const created = members.find((member) => member.family_member_id === memberId);
      if (!created) throw new Error("The Family Member was created but could not be loaded.");
      return created;
    },
    async startEnrollment(familyMemberId) {
      await requireUserId();
      const { error } = await supabase.rpc("sfg_start_family_enrolment", {
        p_family_member_id: familyMemberId,
      });
      if (error) throw readableError(error, "Unable to start Family Member enrolment.");
      activeFamilyEnrollment = {
        familyMemberId,
        session_id: crypto.randomUUID(),
        correlation_id: crypto.randomUUID(),
        nonce: crypto.randomUUID(),
        expires_at: new Date(Date.now() + 15 * 60_000).toISOString(),
        enrolment_status: "ENROLMENT_STARTED",
        positions: [],
      };
      return activeFamilyEnrollment;
    },
    async capturePosition(familyMemberId, session, pose) {
      if (!activeFamilyEnrollment
        || activeFamilyEnrollment.familyMemberId !== familyMemberId
        || activeFamilyEnrollment.session_id !== session.session_id) {
        throw new Error("The Family Member enrolment session expired. Start again.");
      }
      if (Date.now() >= new Date(activeFamilyEnrollment.expires_at).getTime()) {
        activeFamilyEnrollment = null;
        throw new Error("The Family Member enrolment session expired. Start again.");
      }
      if (!["front", "right", "left"].includes(pose)) {
        throw new Error("Use one of the required capture positions.");
      }
      const { data: positions, error } = await supabase.rpc("sfg_record_dev_family_capture", {
        p_family_member_id: familyMemberId,
        p_pose: pose,
      });
      if (error) throw readableError(error, "Unable to record this Family Member capture.");
      activeFamilyEnrollment.positions = positions;
      return {
        capture_status: "CAPTURE_READY",
        liveness_status: "PAD_LIVE",
        frame_index: activeFamilyEnrollment.positions.length,
        templates_accepted: activeFamilyEnrollment.positions.length,
        positions_complete: [...activeFamilyEnrollment.positions],
      };
    },
    async completeEnrollment(familyMemberId, sessionId) {
      if (!activeFamilyEnrollment
        || activeFamilyEnrollment.familyMemberId !== familyMemberId
        || activeFamilyEnrollment.session_id !== sessionId
        || activeFamilyEnrollment.positions.length < 3) {
        throw new Error("Capture front, right, and left positions first.");
      }
      const { error } = await supabase.rpc("sfg_complete_dev_family_enrolment", {
        p_family_member_id: familyMemberId,
      });
      if (error) throw readableError(error, "Unable to complete Family Member enrolment.");
      activeFamilyEnrollment = null;
    },
  },
  profile: {
    async getProfile() {
      const profile = await getProfileRow();
      return {
        citizen_display_name: profile.full_name,
        ic_number_masked: maskIc(profile.ic_number),
        enrolment_status: profile.enrolment_status,
        account_status: profile.profile_state,
      };
    },
    async changePassword(currentPassword, newPassword, newPasswordConfirm) {
      if (newPassword !== newPasswordConfirm) throw new Error("The password confirmation does not match.");
      const profile = await getProfileRow();
      const { error: verifyError } = await supabase.auth.signInWithPassword({
        email: internalIdentityEmail(profile.ic_number),
        password: currentPassword,
      });
      if (verifyError) throw new Error("The current password was not accepted.");
      const { error } = await supabase.auth.updateUser({ password: newPassword });
      if (error) throw readableError(error, "Unable to change the password.");
    },
    async changePin(currentPin, newPin, newPinConfirm) {
      await requireUserId();
      const { error } = await supabase.rpc("sfg_change_pin", {
        p_current_pin: currentPin,
        p_new_pin: newPin,
        p_new_pin_confirm: newPinConfirm,
      });
      if (error) throw readableError(error, "Unable to change the PIN.");
    },
    async startFaceReenrollment() {
      await requireUserId();
      const { error } = await supabase.rpc("sfg_start_face_reenrolment");
      if (error) throw readableError(error, "Unable to start face re-enrolment.");
      activeEnrollment = {
        session_id: crypto.randomUUID(),
        correlation_id: crypto.randomUUID(),
        nonce: crypto.randomUUID(),
        expires_at: new Date(Date.now() + 15 * 60_000).toISOString(),
        enrolment_status: "ENROLMENT_STARTED",
        positions: [],
      };
      return activeEnrollment;
    },
    async completeFaceReenrollment(sessionId) {
      if (!activeEnrollment || activeEnrollment.session_id !== sessionId || activeEnrollment.positions.length < 3) {
        throw new Error("Capture front, right, and left positions first.");
      }
      const { error } = await supabase.rpc("sfg_complete_dev_enrolment");
      if (error) throw readableError(error, "Unable to complete face re-enrolment.");
      activeEnrollment = null;
    },
  },
};
