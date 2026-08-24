-- SFG Supabase Auth and citizen-client integration.
-- IC numbers remain unverified prototype identifiers. Supabase Auth owns passwords and sessions.

create unique index profiles_email_unique_lower on public.profiles ((lower(email)));

alter table public.family_members
  add column idempotency_key text;
create unique index family_members_idempotency_idx
  on public.family_members(user_id, idempotency_key)
  where idempotency_key is not null;

create schema if not exists private;
revoke all on schema private from public, anon, authenticated;

create table private.registration_rate_limits (
  identifier_hash text primary key,
  attempt_count integer not null default 1 check (attempt_count > 0),
  window_started_at timestamptz not null default now()
);
alter table private.registration_rate_limits enable row level security;
revoke all on private.registration_rate_limits from public, anon, authenticated;

create table private.family_enrolment_progress (
  user_id uuid not null references public.profiles(id) on delete cascade,
  family_member_id uuid not null,
  positions text[] not null default '{}'
    check (positions <@ array['front','right','left']::text[]),
  started_at timestamptz not null default now(),
  expires_at timestamptz not null default (now() + interval '15 minutes'),
  primary key (user_id, family_member_id),
  constraint family_enrolment_progress_owner
    foreign key (user_id, family_member_id)
    references public.family_members(user_id, id) on delete cascade
);
alter table private.family_enrolment_progress enable row level security;
revoke all on private.family_enrolment_progress from public, anon, authenticated;

create or replace function public.sfg_registration_rate_limit(p_identifier_hash text)
returns boolean
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_attempt_count integer;
begin
  if p_identifier_hash is null or length(p_identifier_hash) <> 64 then
    return false;
  end if;

  delete from private.registration_rate_limits
  where window_started_at < now() - interval '24 hours';

  insert into private.registration_rate_limits (identifier_hash, attempt_count, window_started_at)
  values (p_identifier_hash, 1, now())
  on conflict (identifier_hash) do update
  set attempt_count = case
        when private.registration_rate_limits.window_started_at < now() - interval '15 minutes' then 1
        else private.registration_rate_limits.attempt_count + 1
      end,
      window_started_at = case
        when private.registration_rate_limits.window_started_at < now() - interval '15 minutes' then now()
        else private.registration_rate_limits.window_started_at
      end
  returning attempt_count into v_attempt_count;

  return v_attempt_count <= 5;
end $$;

create or replace function public.sfg_start_enrolment()
returns void
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_user_id uuid := (select auth.uid());
begin
  if v_user_id is null then
    raise exception 'authentication_required' using errcode = '42501';
  end if;
  update public.profiles
  set consent_status = 'CONSENT_GRANTED', updated_at = now()
  where id = v_user_id and profile_state = 'pending_face';
  if not found then
    raise exception 'profile_not_ready_for_enrolment' using errcode = 'P0001';
  end if;
end $$;

create or replace function public.sfg_complete_dev_enrolment()
returns void
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_user_id uuid := (select auth.uid());
begin
  if v_user_id is null then
    raise exception 'authentication_required' using errcode = '42501';
  end if;
  update public.profiles
  set enrolment_status = 'ENROLMENT_COMPLETED', profile_state = 'pending_pin', updated_at = now()
  where id = v_user_id
    and profile_state = 'pending_face'
    and consent_status = 'CONSENT_GRANTED';
  if not found then
    raise exception 'enrolment_not_ready' using errcode = 'P0001';
  end if;
end $$;

create or replace function public.sfg_set_registration_pin(p_pin text)
returns void
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_user_id uuid := (select auth.uid());
begin
  if v_user_id is null then
    raise exception 'authentication_required' using errcode = '42501';
  end if;
  if p_pin is null or p_pin !~ '^[0-9]{6}$' then
    raise exception 'invalid_pin' using errcode = '22023';
  end if;
  update public.profiles
  set pin_hash = extensions.crypt(p_pin, extensions.gen_salt('bf', 12)),
      profile_state = 'pending_review',
      updated_at = now()
  where id = v_user_id
    and profile_state = 'pending_pin'
    and enrolment_status = 'ENROLMENT_COMPLETED';
  if not found then
    raise exception 'pin_not_ready' using errcode = 'P0001';
  end if;
end $$;

create or replace function public.sfg_activate_profile()
returns void
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_user_id uuid := (select auth.uid());
begin
  if v_user_id is null then
    raise exception 'authentication_required' using errcode = '42501';
  end if;
  update public.profiles
  set profile_state = 'active', updated_at = now()
  where id = v_user_id
    and profile_state = 'pending_review'
    and consent_status = 'CONSENT_GRANTED'
    and enrolment_status = 'ENROLMENT_COMPLETED'
    and pin_hash is not null;
  if not found then
    raise exception 'profile_not_ready' using errcode = 'P0001';
  end if;
end $$;

create or replace function public.sfg_user_topup_wallet(
  p_amount numeric,
  p_idempotency_key text
)
returns table (transaction_id uuid, balance_after numeric)
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_user_id uuid := (select auth.uid());
begin
  if v_user_id is null then
    raise exception 'authentication_required' using errcode = '42501';
  end if;
  return query
    select result.transaction_id, result.balance_after
    from public.sfg_topup_wallet(v_user_id, p_amount, p_idempotency_key) result;
end $$;

create or replace function public.sfg_user_transfer_to_family(
  p_family_member_id uuid,
  p_amount numeric,
  p_pin text,
  p_idempotency_key text
)
returns table (reference text, main_balance numeric, family_balance numeric)
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_user_id uuid := (select auth.uid());
begin
  if v_user_id is null then
    raise exception 'authentication_required' using errcode = '42501';
  end if;
  return query
    select result.reference, result.main_balance, result.family_balance
    from public.sfg_transfer_to_family(
      v_user_id, p_family_member_id, p_amount, p_pin, p_idempotency_key
    ) result;
end $$;

create or replace function public.sfg_create_family_member(
  p_ic text,
  p_full_name text,
  p_relationship text,
  p_idempotency_key text
)
returns uuid
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_user_id uuid := (select auth.uid());
  v_ic text := regexp_replace(coalesce(p_ic, ''), '[^0-9]', '', 'g');
  v_member_id uuid;
begin
  if v_user_id is null then
    raise exception 'authentication_required' using errcode = '42501';
  end if;
  if length(v_ic) <> 12 then
    raise exception 'invalid_ic' using errcode = '22023';
  end if;
  if length(trim(coalesce(p_full_name, ''))) not between 2 and 120
     or length(trim(coalesce(p_relationship, ''))) not between 2 and 60 then
    raise exception 'invalid_profile_details' using errcode = '22023';
  end if;
  if p_idempotency_key is null or length(p_idempotency_key) < 8 then
    raise exception 'invalid_idempotency_key' using errcode = '22023';
  end if;

  select id into v_member_id
  from public.family_members
  where user_id = v_user_id and idempotency_key = p_idempotency_key;
  if found then
    return v_member_id;
  end if;

  if (select count(*) from public.family_members where user_id = v_user_id) >= 10 then
    raise exception 'family_limit_reached' using errcode = 'P0001';
  end if;
  if exists (select 1 from public.profiles where ic_number = v_ic)
     or exists (select 1 from public.family_members where ic_number = v_ic) then
    raise exception 'ic_already_registered' using errcode = '23505';
  end if;

  insert into public.family_members (
    user_id, ic_number, full_name, relationship, idempotency_key
  ) values (
    v_user_id, v_ic, trim(p_full_name), trim(p_relationship), p_idempotency_key
  ) returning id into v_member_id;
  return v_member_id;
end $$;

create or replace function public.sfg_start_family_enrolment(p_family_member_id uuid)
returns void
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_user_id uuid := (select auth.uid());
begin
  if v_user_id is null then
    raise exception 'authentication_required' using errcode = '42501';
  end if;
  update public.family_members
  set consent_status = 'CONSENT_GRANTED',
      enrolment_status = 'ENROLMENT_STARTED',
      profile_state = 'pending_face',
      updated_at = now()
  where id = p_family_member_id
    and user_id = v_user_id
    and profile_state = 'pending_face';
  if not found then
    if exists (
      select 1 from public.family_members
      where id = p_family_member_id and user_id = v_user_id and profile_state = 'active'
    ) then
      raise exception 'family_member_already_enrolled' using errcode = 'P0001';
    end if;
    raise exception 'family_member_not_found' using errcode = 'P0002';
  end if;

  insert into private.family_enrolment_progress (
    user_id, family_member_id, positions, started_at, expires_at
  ) values (
    v_user_id, p_family_member_id, '{}', now(), now() + interval '15 minutes'
  )
  on conflict (user_id, family_member_id) do update
  set positions = '{}',
      started_at = now(),
      expires_at = now() + interval '15 minutes';
end $$;

create or replace function public.sfg_record_dev_family_capture(
  p_family_member_id uuid,
  p_pose text
)
returns text[]
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_user_id uuid := (select auth.uid());
  v_positions text[];
begin
  if v_user_id is null then
    raise exception 'authentication_required' using errcode = '42501';
  end if;
  if p_pose is null or p_pose not in ('front', 'right', 'left') then
    raise exception 'invalid_capture_position' using errcode = '22023';
  end if;

  update private.family_enrolment_progress
  set positions = case
    when p_pose = any(positions) then positions
    else array_append(positions, p_pose)
  end
  where user_id = v_user_id
    and family_member_id = p_family_member_id
    and expires_at > now()
  returning positions into v_positions;

  if not found then
    raise exception 'family_enrolment_session_expired' using errcode = 'P0001';
  end if;
  return v_positions;
end $$;

create or replace function public.sfg_complete_dev_family_enrolment(p_family_member_id uuid)
returns void
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_user_id uuid := (select auth.uid());
  v_positions text[];
begin
  if v_user_id is null then
    raise exception 'authentication_required' using errcode = '42501';
  end if;

  select positions into v_positions
  from private.family_enrolment_progress
  where user_id = v_user_id
    and family_member_id = p_family_member_id
    and expires_at > now()
  for update;

  if not found then
    raise exception 'family_enrolment_session_expired' using errcode = 'P0001';
  end if;
  if not (array['front','right','left']::text[] <@ v_positions) then
    raise exception 'insufficient_family_captures' using errcode = 'P0001';
  end if;

  update public.family_members
  set enrolment_status = 'ENROLMENT_COMPLETED',
      profile_state = 'active',
      updated_at = now()
  where id = p_family_member_id
    and user_id = v_user_id
    and profile_state = 'pending_face'
    and consent_status = 'CONSENT_GRANTED';
  if not found then
    if not exists (
      select 1 from public.family_members where id = p_family_member_id and user_id = v_user_id
    ) then
      raise exception 'family_member_not_found' using errcode = 'P0002';
    end if;
    raise exception 'family_enrolment_not_ready' using errcode = 'P0001';
  end if;

  delete from private.family_enrolment_progress
  where user_id = v_user_id and family_member_id = p_family_member_id;
end $$;

grant usage on schema public to anon, authenticated;
grant select (ic_number) on public.profiles to authenticated;

revoke all on function public.sfg_registration_rate_limit(text) from public, anon, authenticated;
grant execute on function public.sfg_registration_rate_limit(text) to service_role;

revoke all on function public.sfg_start_enrolment() from public, anon;
revoke all on function public.sfg_complete_dev_enrolment() from public, anon;
revoke all on function public.sfg_set_registration_pin(text) from public, anon;
revoke all on function public.sfg_activate_profile() from public, anon;
revoke all on function public.sfg_user_topup_wallet(numeric,text) from public, anon;
revoke all on function public.sfg_user_transfer_to_family(uuid,numeric,text,text) from public, anon;
revoke all on function public.sfg_create_family_member(text,text,text,text) from public, anon;
revoke all on function public.sfg_start_family_enrolment(uuid) from public, anon;
revoke all on function public.sfg_record_dev_family_capture(uuid,text) from public, anon;
revoke all on function public.sfg_complete_dev_family_enrolment(uuid) from public, anon;

grant execute on function public.sfg_start_enrolment() to authenticated;
grant execute on function public.sfg_complete_dev_enrolment() to authenticated;
grant execute on function public.sfg_set_registration_pin(text) to authenticated;
grant execute on function public.sfg_activate_profile() to authenticated;
grant execute on function public.sfg_user_topup_wallet(numeric,text) to authenticated;
grant execute on function public.sfg_user_transfer_to_family(uuid,numeric,text,text) to authenticated;
grant execute on function public.sfg_create_family_member(text,text,text,text) to authenticated;
grant execute on function public.sfg_start_family_enrolment(uuid) to authenticated;
grant execute on function public.sfg_record_dev_family_capture(uuid,text) to authenticated;
grant execute on function public.sfg_complete_dev_family_enrolment(uuid) to authenticated;

revoke all on function public.tg_create_main_wallet() from public, anon, authenticated;
revoke all on function public.tg_create_family_wallet() from public, anon, authenticated;
