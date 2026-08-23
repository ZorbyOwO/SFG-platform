import { describe, expect, it } from "vitest";
import { mapWallet } from "./mappers";
import { isCanonicalStatus, statusFamilies } from "./statuses";

describe("canonical status contract", () => {
  it("contains all 32 exact uppercase values", () => {
    const values = Object.values(statusFamilies).flat();
    expect(values).toHaveLength(32);
    expect(values.every((value) => value === value.toUpperCase())).toBe(true);
    expect(isCanonicalStatus("liveness_status", "PAD_LIVE")).toBe(true);
    expect(isCanonicalStatus("liveness_status", "pad_live")).toBe(false);
  });

  it("maps snake_case API DTOs behind an explicit domain boundary", () => {
    expect(mapWallet({
      wallet_id: "w1", owner_type: "main", owner_id: "u1", family_member_id: null,
      currency: "MYR", available_balance: "2450.80",
    })).toEqual({
      id: "w1", ownerType: "main", ownerId: "u1", familyMemberId: null,
      currency: "MYR", availableBalance: 2450.8,
    });
  });
});
