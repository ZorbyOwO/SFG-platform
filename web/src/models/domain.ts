export interface Wallet {
  id: string;
  ownerType: "main" | "family";
  ownerId: string;
  familyMemberId: string | null;
  currency: "MYR";
  availableBalance: number;
}

export interface Transaction {
  id: string;
  reference: string;
  type: "TOP_UP" | "KIOSK_PAYMENT" | "FAMILY_TRANSFER" | "REVERSAL";
  status: "COMPLETED" | "PENDING" | "FAILED" | "REVERSED";
  direction: "credit" | "debit";
  amount: number;
  balanceAfter: number;
  title: string;
  occurredAt: string;
  familyMemberId: string | null;
}

export interface FamilyMember {
  id: string;
  fullName: string;
  relationship: string;
  icNumberMasked: string;
  enrolmentStatus: string;
  wallet: Wallet;
}
