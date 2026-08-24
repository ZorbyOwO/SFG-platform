-- SFG architecture v0.3 — all wallet mutations are short, locked, idempotent transactions.

create or replace function public.sfg_charge_wallet(
  p_wallet_id uuid,
  p_amount numeric,
  p_kiosk_id text,
  p_merchant_name text,
  p_auth_method text,
  p_idempotency_key text
)
returns table (transaction_id uuid, balance_after numeric)
language plpgsql
security definer
set search_path = public, extensions
as $$
declare
  v_balance numeric(12,2);
  v_new numeric(12,2);
  v_transaction_id uuid;
  v_user_id uuid;
  v_family_member_id uuid;
  v_reference text;
begin
  if p_idempotency_key is null or length(p_idempotency_key) < 8 then
    raise exception 'invalid_idempotency_key' using errcode = '22023';
  end if;

  select t.id, t.balance_after into v_transaction_id, v_new
  from public.transactions t
  where t.idempotency_key = p_idempotency_key;
  if found then
    return query select v_transaction_id, v_new;
    return;
  end if;

  if p_amount is null or p_amount <= 0 or scale(p_amount) > 2 then
    raise exception 'invalid_amount' using errcode = '22023';
  end if;
  if p_auth_method not in ('face_pin','face_only') then
    raise exception 'invalid_auth_method' using errcode = '22023';
  end if;
  if not exists (select 1 from public.kiosks k where k.id = p_kiosk_id and k.is_active) then
    raise exception 'kiosk_unavailable' using errcode = 'P0002';
  end if;

  select w.balance, w.user_id, w.family_member_id
    into v_balance, v_user_id, v_family_member_id
  from public.wallets w
  where w.id = p_wallet_id
  for update;
  if not found then
    raise exception 'wallet_not_found' using errcode = 'P0002';
  end if;
  if not exists (
    select 1 from public.profiles p
    where p.id = v_user_id and p.profile_state = 'active' and p.consent_status = 'CONSENT_GRANTED'
  ) then
    raise exception 'account_unavailable' using errcode = 'P0001';
  end if;
  if v_family_member_id is not null and not exists (
    select 1 from public.family_members fm
    where fm.id = v_family_member_id and fm.user_id = v_user_id and fm.profile_state = 'active'
      and fm.consent_status = 'CONSENT_GRANTED'
  ) then
    raise exception 'managed_profile_unavailable' using errcode = 'P0001';
  end if;
  if v_balance < p_amount then
    raise exception 'insufficient_funds' using errcode = 'P0001';
  end if;

  v_new := v_balance - p_amount;
  update public.wallets set balance = v_new, updated_at = now() where id = p_wallet_id;
  v_transaction_id := gen_random_uuid();
  v_reference := 'SFG-' || upper(substr(replace(v_transaction_id::text, '-', ''), 1, 12));
  insert into public.transactions (
    id, user_id, wallet_id, family_member_id, type, status, amount, balance_after,
    merchant_name, kiosk_id, auth_method, reference, idempotency_key
  ) values (
    v_transaction_id, v_user_id, p_wallet_id, v_family_member_id, 'purchase', 'completed',
    p_amount, v_new, p_merchant_name, p_kiosk_id, p_auth_method, v_reference, p_idempotency_key
  );
  return query select v_transaction_id, v_new;
end $$;

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

create or replace function public.sfg_transfer_to_family(
  p_user_id uuid,
  p_family_member_id uuid,
  p_amount numeric,
  p_pin text,
  p_idempotency_key text
)
returns table (reference text, main_balance numeric, family_balance numeric)
language plpgsql
security definer
set search_path = public, extensions
as $$
declare
  v_main_wallet uuid;
  v_family_wallet uuid;
  v_main_balance numeric(12,2);
  v_family_balance numeric(12,2);
  v_correlation uuid;
  v_reference text;
begin
  if p_idempotency_key is null or length(p_idempotency_key) < 8 then
    raise exception 'invalid_idempotency_key' using errcode = '22023';
  end if;

  select t.reference, t.correlation_id, t.balance_after
    into v_reference, v_correlation, v_main_balance
  from public.transactions t
  where t.idempotency_key = p_idempotency_key and t.type = 'transfer_out';
  if found then
    select t.balance_after into v_family_balance
    from public.transactions t
    where t.correlation_id = v_correlation and t.type = 'transfer_in';
    return query select v_reference, v_main_balance, v_family_balance;
    return;
  end if;

  if p_amount is null or p_amount < 1.00 or p_amount > 1000.00 or scale(p_amount) > 2 then
    raise exception 'invalid_amount' using errcode = '22023';
  end if;
  if p_pin is null or p_pin !~ '^[0-9]{6}$' then
    raise exception 'wrong_pin' using errcode = 'P0001';
  end if;
  if not exists (
    select 1 from public.profiles p
    where p.id = p_user_id and p.profile_state = 'active'
      and extensions.crypt(p_pin, p.pin_hash) = p.pin_hash
  ) then
    raise exception 'wrong_pin' using errcode = 'P0001';
  end if;

  select w.id into v_main_wallet
  from public.wallets w
  where w.user_id = p_user_id and w.family_member_id is null;
  select w.id into v_family_wallet
  from public.wallets w
  join public.family_members fm on fm.id = w.family_member_id and fm.user_id = w.user_id
  where fm.id = p_family_member_id and fm.user_id = p_user_id and fm.profile_state = 'active';
  if v_main_wallet is null or v_family_wallet is null then
    raise exception 'wallet_not_found' using errcode = 'P0002';
  end if;

  -- Lock both rows in deterministic ID order before reading either balance.
  perform 1 from public.wallets w
  where w.id in (v_main_wallet, v_family_wallet)
  order by w.id
  for update;

  select w.balance into v_main_balance from public.wallets w where w.id = v_main_wallet;
  select w.balance into v_family_balance from public.wallets w where w.id = v_family_wallet;
  if v_main_balance < p_amount then
    raise exception 'insufficient_funds' using errcode = 'P0001';
  end if;

  v_main_balance := v_main_balance - p_amount;
  v_family_balance := v_family_balance + p_amount;
  v_correlation := gen_random_uuid();
  v_reference := 'SFG-T-' || upper(substr(replace(v_correlation::text, '-', ''), 1, 10));
  update public.wallets set balance = v_main_balance, updated_at = now() where id = v_main_wallet;
  update public.wallets set balance = v_family_balance, updated_at = now() where id = v_family_wallet;
  insert into public.transactions (
    user_id, wallet_id, type, status, amount, balance_after, auth_method,
    reference, correlation_id, idempotency_key
  ) values (
    p_user_id, v_main_wallet, 'transfer_out', 'completed', p_amount, v_main_balance,
    'guardian_pin', v_reference, v_correlation, p_idempotency_key
  );
  insert into public.transactions (
    user_id, wallet_id, family_member_id, type, status, amount, balance_after,
    auth_method, reference, correlation_id
  ) values (
    p_user_id, v_family_wallet, p_family_member_id, 'transfer_in', 'completed', p_amount,
    v_family_balance, 'guardian_pin', v_reference, v_correlation
  );
  return query select v_reference, v_main_balance, v_family_balance;
end $$;

revoke all on function public.sfg_charge_wallet(uuid,numeric,text,text,text,text) from public, anon, authenticated;
revoke all on function public.sfg_topup_wallet(uuid,numeric,text) from public, anon, authenticated;
revoke all on function public.sfg_transfer_to_family(uuid,uuid,numeric,text,text) from public, anon, authenticated;
grant execute on function public.sfg_charge_wallet(uuid,numeric,text,text,text,text) to service_role;
grant execute on function public.sfg_topup_wallet(uuid,numeric,text) to service_role;
grant execute on function public.sfg_transfer_to_family(uuid,uuid,numeric,text,text) to service_role;
