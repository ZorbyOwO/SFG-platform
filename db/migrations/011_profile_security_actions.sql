-- Complete the authenticated Profile security actions used by the citizen web UI.
-- The development face flow records state only; real CoreCV template persistence
-- remains private and is intentionally not introduced by this migration.

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
  set enrolment_status = case when pin_hash is null then 'ENROLMENT_STARTED' else 'ENROLMENT_COMPLETED' end,
      profile_state = case when pin_hash is null then 'pending_pin' else 'active' end,
      updated_at = now()
  where id = v_user_id
    and profile_state = 'pending_face'
    and consent_status = 'CONSENT_GRANTED';
  if not found then
    raise exception 'enrolment_not_ready' using errcode = 'P0001';
  end if;
end $$;

create or replace function public.sfg_start_face_reenrolment()
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
  set enrolment_status = 'ENROLMENT_STARTED',
      consent_status = 'CONSENT_GRANTED',
      profile_state = 'pending_face',
      updated_at = now()
  where id = v_user_id
    and profile_state = 'active'
    and pin_hash is not null;
  if not found then
    raise exception 'profile_not_ready_for_reenrolment' using errcode = 'P0001';
  end if;

  update public.face_templates
  set template_status = 'TEMPLATE_REVOKED'
  where user_id = v_user_id
    and family_member_id is null
    and template_status = 'TEMPLATE_ACTIVE';
end $$;

create or replace function public.sfg_change_pin(
  p_current_pin text,
  p_new_pin text,
  p_new_pin_confirm text
)
returns void
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_user_id uuid := (select auth.uid());
  v_profile public.profiles%rowtype;
begin
  if v_user_id is null then
    raise exception 'authentication_required' using errcode = '42501';
  end if;
  select * into v_profile from public.profiles where id = v_user_id for update;
  if not found or v_profile.profile_state <> 'active' then
    raise exception 'profile_not_active' using errcode = 'P0001';
  end if;
  if v_profile.pin_hash is null or extensions.crypt(p_current_pin, v_profile.pin_hash) <> v_profile.pin_hash then
    raise exception 'wrong_pin' using errcode = '42501';
  end if;
  if p_new_pin is null or p_new_pin !~ '^[0-9]{6}$' then
    raise exception 'invalid_pin' using errcode = '22023';
  end if;
  if p_new_pin <> p_new_pin_confirm then
    raise exception 'pin_mismatch' using errcode = '22023';
  end if;
  if p_new_pin in ('000000','111111','222222','333333','444444','555555','666666','777777','888888','999999','123456','654321','121212','123123')
     or p_new_pin = substring(v_profile.ic_number from 1 for 6)
     or p_new_pin = substring(v_profile.ic_number from 5 for 2) || substring(v_profile.ic_number from 3 for 2) || substring(v_profile.ic_number from 1 for 2) then
    raise exception 'pin_blocklisted' using errcode = '22023';
  end if;
  if extensions.crypt(p_new_pin, v_profile.pin_hash) = v_profile.pin_hash then
    raise exception 'pin_unchanged' using errcode = '22023';
  end if;

  update public.profiles
  set pin_hash = extensions.crypt(p_new_pin, extensions.gen_salt('bf', 12)), updated_at = now()
  where id = v_user_id;
end $$;

revoke all on function public.sfg_start_face_reenrolment() from public, anon;
revoke all on function public.sfg_change_pin(text,text,text) from public, anon;
grant execute on function public.sfg_start_face_reenrolment() to authenticated;
grant execute on function public.sfg_change_pin(text,text,text) to authenticated;
