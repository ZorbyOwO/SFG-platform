-- Preset wallet top-ups are MYR 20/50/100/200/500. Citizens may also
-- enter a custom simulated amount from MYR 1.00 to MYR 5,000.00.
create or replace function public.sfg_topup_wallet(
  p_user_id uuid,
  p_amount numeric,
  p_idempotency_key text
)
returns table (transaction_id uuid, balance_after numeric)
language plpgsql
security definer
set search_path = public
as $$
declare
  v_wallet_id uuid;
  v_balance numeric(12,2);
  v_new numeric(12,2);
  v_transaction_id uuid;
  v_reference text;
begin
  if p_idempotency_key is null or length(p_idempotency_key) < 8 then
    raise exception 'invalid_idempotency_key' using errcode = '22023';
  end if;
  select t.id, t.balance_after into v_transaction_id, v_new
  from public.transactions t where t.idempotency_key = p_idempotency_key;
  if found then
    return query select v_transaction_id, v_new;
    return;
  end if;
  if p_amount is null or p_amount < 1.00 or p_amount > 5000.00 or scale(p_amount) > 2 then
    raise exception 'invalid_amount' using errcode = '22023';
  end if;
  if not exists (
    select 1 from public.profiles p where p.id = p_user_id and p.profile_state = 'active'
  ) then
    raise exception 'enrolment_incomplete' using errcode = 'P0001';
  end if;
  select w.id, w.balance into v_wallet_id, v_balance
  from public.wallets w
  where w.user_id = p_user_id and w.family_member_id is null
  for update;
  if not found then
    raise exception 'wallet_not_found' using errcode = 'P0002';
  end if;
  v_new := v_balance + p_amount;
  update public.wallets set balance = v_new, updated_at = now() where id = v_wallet_id;
  v_transaction_id := gen_random_uuid();
  v_reference := 'SFG-' || upper(substr(replace(v_transaction_id::text, '-', ''), 1, 12));
  insert into public.transactions (
    id, user_id, wallet_id, type, status, amount, balance_after,
    auth_method, reference, idempotency_key
  ) values (
    v_transaction_id, p_user_id, v_wallet_id, 'topup', 'completed', p_amount, v_new,
    'app_topup', v_reference, p_idempotency_key
  );
  return query select v_transaction_id, v_new;
end $$;

revoke all on function public.sfg_topup_wallet(uuid,numeric,text) from public, anon, authenticated;
grant execute on function public.sfg_topup_wallet(uuid,numeric,text) to service_role;
