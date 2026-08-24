-- Fix the first-time PIN chain broken by migration 011.
--
-- 011's sfg_complete_dev_enrolment keeps first-time enrolees at
-- enrolment_status='ENROLMENT_STARTED' with profile_state='pending_pin'
-- (COMPLETED is reserved until activation). The 006-era
-- sfg_set_registration_pin and sfg_activate_profile still required
-- enrolment_status='ENROLMENT_COMPLETED' in their WHERE clauses, which a
-- first-time user never reaches before activation. Result: every first-time
-- registration failed at the PIN step with 'pin_not_ready' (and would have
-- failed at review with 'profile_not_ready').
--
-- Fix: the PIN step now gates on profile_state='pending_pin' alone (the
-- state that face enrolment completion guarantees). Activation now promotes
-- the profile to 'active' AND sets enrolment_status='ENROLMENT_COMPLETED',
-- matching the API's in-memory flow and keeping 'ENROLMENT_COMPLETED'
-- meaningful as "activated" for the backend PIN verification gate.

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
    and profile_state = 'pending_pin';
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
  set profile_state = 'active',
      enrolment_status = 'ENROLMENT_COMPLETED',
      updated_at = now()
  where id = v_user_id
    and profile_state = 'pending_review'
    and consent_status = 'CONSENT_GRANTED'
    and pin_hash is not null;
  if not found then
    raise exception 'profile_not_ready' using errcode = 'P0001';
  end if;
end $$;
