from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request

from ..contracts import PinStatus, TopUpRequest, TransferRequest
from ..dependencies import current_user, get_store
from ..models import User
from ..serializers import transaction_dto, wallet_dto


router = APIRouter(tags=["wallet"])


@router.get("/wallet")
async def get_wallet(request: Request, user: User = Depends(current_user)) -> dict[str, object]:
    return wallet_dto(get_store(request).main_wallet(user.citizen_id))


@router.get("/wallets")
async def get_wallets(request: Request, user: User = Depends(current_user)) -> dict[str, object]:
    return {"items": [wallet_dto(item) for item in get_store(request).list_wallets(user.citizen_id)]}


@router.post("/wallet/topup")
async def top_up(payload: TopUpRequest, request: Request, user: User = Depends(current_user)) -> dict[str, object]:
    transaction = await get_store(request).top_up(user, payload.amount, payload.idempotency_key)
    return {
        "transaction_id": transaction.id,
        "reference": transaction.reference,
        "balance_after": f"{transaction.balance_after:.2f}",
    }


@router.post("/wallet/transfers")
async def transfer(payload: TransferRequest, request: Request, user: User = Depends(current_user)) -> dict[str, object]:
    request.app.state.rate_limiter.check(f"transfer:{user.citizen_id}", limit=10, window_seconds=60)
    store = get_store(request)
    member = store.get_family(user.citizen_id, payload.family_member_id)
    transaction, main, managed = await store.transfer(
        user, member, payload.amount, payload.pin, payload.idempotency_key
    )
    return {
        "transaction_id": transaction.id,
        "reference": transaction.reference,
        "pin_status": PinStatus.ACCEPTED.value,
        "main_balance": f"{main.balance:.2f}",
        "family_balance": f"{managed.balance:.2f}",
    }


@router.get("/transactions")
async def list_transactions(
    request: Request,
    search: str = "",
    type: str = "",
    status: str = "",
    limit: int = Query(default=50, ge=1, le=100),
    before: str = "",
    user: User = Depends(current_user),
) -> dict[str, object]:
    rows = get_store(request).list_transactions(user.citizen_id)
    if search:
        needle = search.casefold()
        rows = [item for item in rows if needle in " ".join(filter(None, [item.reference, item.merchant_name])).casefold()]
    if type:
        rows = [item for item in rows if item.type == type]
    if status:
        rows = [item for item in rows if item.status == status]
    if before:
        try:
            cutoff = datetime.fromisoformat(before)
            rows = [item for item in rows if item.created_at < cutoff]
        except ValueError:
            rows = []
    selected = rows[:limit]
    return {
        "items": [transaction_dto(item) for item in selected],
        "next_before": selected[-1].created_at.isoformat() if len(rows) > limit and selected else None,
    }


@router.get("/transactions/{transaction_id}")
async def get_transaction(transaction_id: str, request: Request, user: User = Depends(current_user)) -> dict[str, object]:
    return transaction_dto(get_store(request).get_transaction(user.citizen_id, transaction_id))
