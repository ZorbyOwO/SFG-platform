import type { AuthDto, CaptureDto, EnrollmentSessionDto, FamilyMemberDto, RegisterDto, TransactionDto, WalletDto } from "../contracts/dto";

export interface AuthService {
  register(payload: RegisterDto): Promise<AuthDto>;
  login(ic: string, password: string): Promise<AuthDto>;
  logout(): Promise<void>;
  hasSession(): boolean;
}

export interface BiometricService {
  startEnrollment(): Promise<EnrollmentSessionDto>;
  capturePosition(session: EnrollmentSessionDto, pose: string): Promise<CaptureDto>;
  completeEnrollment(sessionId: string): Promise<void>;
  setPin(pin: string, pinConfirm: string): Promise<void>;
  activate(): Promise<void>;
}

export interface WalletService {
  getWallet(): Promise<WalletDto>;
  listWallets(): Promise<WalletDto[]>;
  createTopUp(amount: number, idempotencyKey: string): Promise<void>;
  transferToFamilyMember(familyMemberId: string, amount: number, pin: string, idempotencyKey: string): Promise<void>;
}

export interface TransactionService {
  listTransactions(): Promise<TransactionDto[]>;
  getTransaction(id: string): Promise<TransactionDto>;
}

export interface FamilyService {
  listFamilyMembers(): Promise<FamilyMemberDto[]>;
  createFamilyMember(input: { ic: string; full_name: string; relationship: string; idempotency_key: string }): Promise<FamilyMemberDto>;
}

export interface ProfileService {
  getProfile(): Promise<{ citizen_display_name: string; ic_number_masked: string; enrolment_status: string; account_status: string }>;
}

export interface AppServices {
  mode: "mock" | "api";
  auth: AuthService;
  biometric: BiometricService;
  wallet: WalletService;
  transactions: TransactionService;
  family: FamilyService;
  profile: ProfileService;
}
