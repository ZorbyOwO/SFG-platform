import type { AppServices } from "../types";
import type { AuthDto, CaptureDto, EnrollmentSessionDto, FamilyMemberDto, RegisterDto, TransactionDto, WalletDto } from "../../contracts/dto";

const baseUrl = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
let accessToken = "";
let refreshToken = "";

interface ApiErrorBody { error?: string; message?: string }

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
  if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
  const response = await fetch(`${baseUrl}${path}`, { ...init, headers });
  if (!response.ok) {
    const body = await response.json().catch(() => ({})) as ApiErrorBody;
    throw new Error(body.message || "The service could not complete the request.");
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

function remember(dto: AuthDto): AuthDto {
  accessToken = dto.access_token;
  refreshToken = dto.refresh_token;
  return dto;
}

function simulationFrame(): Blob {
  // Development adapter input only; this is not a photograph or biometric fixture.
  return new Blob([new Uint8Array([0xff, 0xd8, 0xff, 0xd9])], { type: "image/jpeg" });
}

export const apiServices: AppServices = {
  mode: "api",
  auth: {
    register(payload: RegisterDto) {
      return request<AuthDto>("/auth/register", { method: "POST", body: JSON.stringify(payload) }).then(remember);
    },
    login(ic: string, password: string) {
      return request<AuthDto>("/auth/login", { method: "POST", body: JSON.stringify({ ic, password }) }).then(remember);
    },
    async logout() {
      await request<void>("/auth/logout", { method: "POST", body: "{}" });
      accessToken = ""; refreshToken = "";
    },
    hasSession: () => Boolean(accessToken),
  },
  biometric: {
    startEnrollment() {
      return request<EnrollmentSessionDto>("/enrol/session", { method: "POST", body: "{}" });
    },
    capturePosition(session: EnrollmentSessionDto, pose: string) {
      const form = new FormData();
      form.set("session_id", session.session_id);
      form.set("nonce", session.nonce);
      form.set("pose", pose);
      form.set("frame", simulationFrame(), "development-simulation.jpg");
      return request<CaptureDto>("/enrol/face", { method: "POST", headers: { "X-SFG-Simulation": "success" }, body: form });
    },
    completeEnrollment(sessionId: string) {
      return request<void>("/enrol/complete", { method: "POST", body: JSON.stringify({ session_id: sessionId }) });
    },
    setPin(pin: string, pinConfirm: string) {
      return request<void>("/enrol/pin", { method: "POST", body: JSON.stringify({ pin, pin_confirm: pinConfirm }) });
    },
    activate() {
      return request<void>("/enrol/activate", { method: "POST", body: JSON.stringify({ terms_acknowledged: true, privacy_acknowledged: true }) });
    },
  },
  wallet: {
    getWallet: () => request<WalletDto>("/wallet"),
    async listWallets() { return (await request<{ items: WalletDto[] }>("/wallets")).items; },
    createTopUp(amount, idempotencyKey) {
      return request<void>("/wallet/topup", { method: "POST", body: JSON.stringify({ amount, mock_source: "development simulation", idempotency_key: idempotencyKey }) });
    },
    transferToFamilyMember(familyMemberId, amount, pin, idempotencyKey) {
      return request<void>("/wallet/transfers", { method: "POST", body: JSON.stringify({ family_member_id: familyMemberId, amount, pin, idempotency_key: idempotencyKey }) });
    },
  },
  transactions: {
    async listTransactions() { return (await request<{ items: TransactionDto[] }>("/transactions")).items; },
    getTransaction: (id) => request<TransactionDto>(`/transactions/${encodeURIComponent(id)}`),
  },
  family: {
    async listFamilyMembers() { return (await request<{ items: FamilyMemberDto[] }>("/family-members")).items; },
    createFamilyMember(input) {
      return request<FamilyMemberDto>("/family-members", { method: "POST", body: JSON.stringify(input) });
    },
  },
  profile: {
    getProfile: () => request("/profile"),
  },
};

export function clearApiSession(): void {
  accessToken = "";
  refreshToken = "";
}
