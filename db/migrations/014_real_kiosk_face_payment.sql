-- Real kiosk face payment: atomic biometric generations and trusted charging.
--
-- The previous hosted RPC revoked the current template and inserted one row per
-- call. Calling it three times for front/right/left therefore retained only the
-- last pose. This migration makes one generation the database transaction unit.
-- Legacy rows without pose/generation metadata are revoked because their AES-GCM
-- additional authenticated data cannot be reconstructed safely for matching.

alter table private.sfg_biometric_templates
  add column if not exists capture_pose text,
  add column if not exists generation_id uuid;

drop index if exists private.sfg_one_active_template_per_citizen_idx;

update private.sfg_biometric_templates
set template_status = 'TEMPLATE_REVOKED'
where template_status = 'TEMPLATE_ACTIVE'
  and (capture_pose is null or generation_id is null);

alter table private.sfg_biometric_templates
  drop constraint if exists sfg_biometric_templates_capture_pose_check,
  drop constraint if exists sfg_biometric_templates_active_generation_check;

alter table private.sfg_biometric_templates
  add constraint sfg_biometric_templates_capture_pose_check
    check (capture_pose is null or capture_pose in ('front', 'right', 'left')),
  add constraint sfg_biometric_templates_active_generation_check
    check (
      template_status = 'TEMPLATE_REVOKED'
      or (capture_pose is not null and generation_id is not null)
    );

create unique index if not exists sfg_one_active_template_per_citizen_pose_idx
  on private.sfg_biometric_templates(citizen_id, capture_pose)
  where template_status = 'TEMPLATE_ACTIVE';

create index if not exists sfg_biometric_templates_generation_idx
  on private.sfg_biometric_templates(citizen_id, generation_id);

create or replace function public.sfg_backend_replace_template_generation(
  p_citizen_id uuid,
  p_generation_id uuid,
  p_bundles jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $function$
declare
  v_bundle jsonb;
  v_template_id uuid;
  v_template_ids jsonb := '[]'::jsonb;
  v_row_count integer;
  v_pose_count integer;
  v_fingerprint_count integer;
begin
  if p_generation_id is null then
    raise exception 'GENERATION_ID_INVALID' using errcode = '22023';
  end if;
  if jsonb_typeof(p_bundles) <> 'array' or jsonb_array_length(p_bundles) <> 3 then
    raise exception 'BIOMETRIC_GENERATION_INCOMPLETE' using errcode = '22023';
  end if;

  select
    count(*),
    count(distinct item ->> 'capture_pose'),
    count(distinct item #>> '{compatibility_fingerprint,fingerprint}')
  into v_row_count, v_pose_count, v_fingerprint_count
  from jsonb_array_elements(p_bundles) as entries(item)
  where jsonb_typeof(item) = 'object'
    and item ->> 'capture_pose' in ('front', 'right', 'left')
    and item ->> 'encryption_version' = 'sfg-aesgcm-v1'
    and jsonb_typeof(item -> 'compatibility_fingerprint') = 'object'
    and coalesce(length(item #>> '{compatibility_fingerprint,fingerprint}'), 0) > 0
    and coalesce(length(item ->> 'encrypted_payload'), 0) > 0
    and coalesce(length(item ->> 'nonce'), 0) > 0;

  if v_row_count <> 3 or v_pose_count <> 3 or v_fingerprint_count <> 1 then
    raise exception 'BIOMETRIC_GENERATION_INVALID' using errcode = '22023';
  end if;
  if not exists (
    select 1
    from public.profiles p
    where p.id = p_citizen_id
      and p.consent_status = 'CONSENT_GRANTED'
  ) then
    raise exception 'CITIZEN_PROFILE_UNAVAILABLE' using errcode = 'P0002';
  end if;

  -- Decode and validate every bundle before revoking the old generation. Any
  -- exception rolls back the entire function call.
  for v_bundle in
    select item
    from jsonb_array_elements(p_bundles) as entries(item)
    order by case item ->> 'capture_pose'
      when 'front' then 1 when 'right' then 2 else 3 end
  loop
    if octet_length(decode(v_bundle ->> 'encrypted_payload', 'base64')) <= 512
       or octet_length(decode(v_bundle ->> 'nonce', 'base64')) <> 12 then
      raise exception 'BIOMETRIC_BUNDLE_INVALID' using errcode = '22023';
    end if;
  end loop;

  update private.sfg_biometric_templates
  set template_status = 'TEMPLATE_REVOKED'
  where citizen_id = p_citizen_id
    and template_status = 'TEMPLATE_ACTIVE';

  for v_bundle in
    select item
    from jsonb_array_elements(p_bundles) as entries(item)
    order by case item ->> 'capture_pose'
      when 'front' then 1 when 'right' then 2 else 3 end
  loop
    insert into private.sfg_biometric_templates (
      citizen_id,
      encrypted_payload,
      nonce,
      compatibility_fingerprint,
      encryption_version,
      template_status,
      capture_pose,
      generation_id
    ) values (
      p_citizen_id,
      decode(v_bundle ->> 'encrypted_payload', 'base64'),
      decode(v_bundle ->> 'nonce', 'base64'),
      v_bundle -> 'compatibility_fingerprint',
      'sfg-aesgcm-v1',
      'TEMPLATE_ACTIVE',
      v_bundle ->> 'capture_pose',
      p_generation_id
    )
    returning template_id into v_template_id;
    v_template_ids := v_template_ids || jsonb_build_array(v_template_id::text);
  end loop;

  return jsonb_build_object('template_ids', v_template_ids);
end;
$function$;

create or replace function public.sfg_backend_load_identification_gallery(p_encryption_version text)
returns jsonb
language sql
security definer
set search_path = ''
as $function$
  select coalesce(jsonb_agg(jsonb_build_object(
    'template_id', t.template_id,
    'citizen_id', t.citizen_id,
    'capture_pose', t.capture_pose,
    'generation_id', t.generation_id,
    'encrypted_payload', encode(t.encrypted_payload, 'base64'),
    'nonce', encode(t.nonce, 'base64'),
    'compatibility_fingerprint', t.compatibility_fingerprint
  ) order by t.citizen_id, t.capture_pose), '[]'::jsonb)
  from private.sfg_biometric_templates t
  join public.profiles p on p.id = t.citizen_id
  where t.template_status = 'TEMPLATE_ACTIVE'
    and t.encryption_version = p_encryption_version
    and t.capture_pose = 'front'
    and t.generation_id is not null
    and p.profile_state = 'active'
    and p.enrolment_status = 'ENROLMENT_COMPLETED'
    and p.consent_status = 'CONSENT_GRANTED';
$function$;

revoke all on function public.sfg_backend_replace_template_generation(uuid, uuid, jsonb)
  from public, anon, authenticated;
revoke all on function public.sfg_backend_load_identification_gallery(text)
  from public, anon, authenticated;
grant execute on function public.sfg_backend_replace_template_generation(uuid, uuid, jsonb)
  to service_role;
grant execute on function public.sfg_backend_load_identification_gallery(text)
  to service_role;

-- Disable the unsafe one-row replacement path for the trusted runtime. Its
-- definitions remain for migration-history compatibility, but service_role can
-- no longer call either one.
do $block$
begin
  if to_regprocedure(
    'public.sfg_backend_complete_reenrolment(uuid,text,text,jsonb,text)'
  ) is not null then
    execute 'revoke execute on function public.sfg_backend_complete_reenrolment(uuid, text, text, jsonb, text) from service_role';
  end if;
end;
$block$;
revoke execute on function public.sfg_backend_save_template(uuid, text, text, jsonb, text)
  from service_role;

-- Trusted matched-profile lookup, PIN verification, and atomic main-wallet charge.

create or replace function public.sfg_backend_profile_identity(p_citizen_id uuid)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $function$
declare
  v_identity jsonb;
begin
  select jsonb_build_object(
    'citizen_id', p.id,
    'full_name', p.full_name,
    'ic_number', p.ic_number
  )
  into v_identity
  from public.profiles p
  where p.id = p_citizen_id
    and p.profile_state = 'active'
    and p.enrolment_status = 'ENROLMENT_COMPLETED'
    and p.consent_status = 'CONSENT_GRANTED';

  if v_identity is null then
    raise exception 'ACCOUNT_UNAVAILABLE' using errcode = 'P0001';
  end if;
  return v_identity;
end;
$function$;

create or replace function public.sfg_backend_verify_pin(p_citizen_id uuid, p_pin text)
returns jsonb
language sql
security definer
set search_path = ''
as $function$
  select jsonb_build_object('accepted', coalesce((
    select extensions.crypt(p_pin, p.pin_hash) = p.pin_hash
    from public.profiles p
    where p.id = p_citizen_id
      and p.profile_state = 'active'
      and p.enrolment_status = 'ENROLMENT_COMPLETED'
      and p.consent_status = 'CONSENT_GRANTED'
      and p.pin_hash is not null
  ), false));
$function$;

create or replace function public.sfg_backend_charge_profile_wallet(
  p_citizen_id uuid,
  p_amount numeric,
  p_kiosk_id text,
  p_idempotency_key text
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $function$
declare
  v_wallet_id uuid;
  v_merchant_name text;
  v_transaction_id uuid;
  v_balance_after numeric(12,2);
  v_reference text;
  v_recorded_amount numeric(12,2);
begin
  if p_idempotency_key is null or length(p_idempotency_key) < 8 then
    raise exception 'invalid_idempotency_key' using errcode = '22023';
  end if;

  select w.id
  into v_wallet_id
  from public.wallets w
  join public.profiles p on p.id = w.user_id
  where w.user_id = p_citizen_id
    and w.family_member_id is null
    and p.profile_state = 'active'
    and p.enrolment_status = 'ENROLMENT_COMPLETED'
    and p.consent_status = 'CONSENT_GRANTED';

  if v_wallet_id is null then
    raise exception 'account_unavailable' using errcode = 'P0001';
  end if;

  select k.merchant_name
  into v_merchant_name
  from public.kiosks k
  where k.id = p_kiosk_id
    and k.is_active;

  if v_merchant_name is null then
    raise exception 'kiosk_unavailable' using errcode = 'P0002';
  end if;

  select charged.transaction_id, charged.balance_after
  into v_transaction_id, v_balance_after
  from public.sfg_charge_wallet(
    v_wallet_id,
    p_amount,
    p_kiosk_id,
    v_merchant_name,
    'face_pin',
    p_idempotency_key
  ) charged;

  select t.reference, t.amount, t.balance_after
  into v_reference, v_recorded_amount, v_balance_after
  from public.transactions t
  where t.id = v_transaction_id
    and t.user_id = p_citizen_id
    and t.wallet_id = v_wallet_id
    and t.family_member_id is null
    and t.kiosk_id = p_kiosk_id
    and t.auth_method = 'face_pin'
    and t.idempotency_key = p_idempotency_key
    and t.amount = p_amount
    and t.status = 'completed';

  if v_reference is null then
    raise exception 'idempotency_conflict' using errcode = '23505';
  end if;

  return jsonb_build_object(
    'transaction_id', v_transaction_id,
    'reference', v_reference,
    'amount', v_recorded_amount,
    'merchant_name', v_merchant_name,
    'balance_after', v_balance_after
  );
end;
$function$;

revoke all on function public.sfg_backend_profile_identity(uuid)
  from public, anon, authenticated;
revoke all on function public.sfg_backend_verify_pin(uuid, text)
  from public, anon, authenticated;
revoke all on function public.sfg_backend_charge_profile_wallet(uuid, numeric, text, text)
  from public, anon, authenticated;
grant execute on function public.sfg_backend_profile_identity(uuid)
  to service_role;
grant execute on function public.sfg_backend_verify_pin(uuid, text)
  to service_role;
grant execute on function public.sfg_backend_charge_profile_wallet(uuid, numeric, text, text)
  to service_role;
