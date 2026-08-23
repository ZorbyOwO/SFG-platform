import type { FamilyMemberDto, TransactionDto, WalletDto } from "./dto";
import type { FamilyMember, Transaction, Wallet } from "../models/domain";

export function mapWallet(dto: WalletDto): Wallet {
  return {
    id: dto.wallet_id,
    ownerType: dto.owner_type,
    ownerId: dto.owner_id,
    familyMemberId: dto.family_member_id,
    currency: dto.currency,
    availableBalance: Number(dto.available_balance),
  };
}

export function mapTransaction(dto: TransactionDto): Transaction {
  const type = dto.type === "topup" ? "TOP_UP" : dto.type === "purchase" ? "KIOSK_PAYMENT" : dto.type === "reversal" ? "REVERSAL" : "FAMILY_TRANSFER";
  const title = dto.merchant_name || (type === "TOP_UP" ? "Wallet top-up" : type === "FAMILY_TRANSFER" ? "Family transfer" : "Reversal");
  return {
    id: dto.transaction_id,
    reference: dto.reference,
    type,
    status: dto.status.toUpperCase() as Transaction["status"],
    direction: dto.direction,
    amount: Number(dto.amount),
    balanceAfter: Number(dto.balance_after),
    title,
    occurredAt: dto.occurred_at,
    familyMemberId: dto.family_member_id,
  };
}

export function mapFamilyMember(dto: FamilyMemberDto): FamilyMember {
  return {
    id: dto.family_member_id,
    fullName: dto.full_name,
    relationship: dto.relationship,
    icNumberMasked: dto.ic_number_masked,
    enrolmentStatus: dto.enrolment_status,
    wallet: mapWallet(dto.wallet),
  };
}
