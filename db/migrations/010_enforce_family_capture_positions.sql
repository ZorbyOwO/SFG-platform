-- Authenticated main-account holders may enrol only Family Members they own.
-- Development capture progress is persisted, but no face image or biometric template is stored.
create table if not exists private.family_enrolment_progress (
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
revoke all on table private.family_enrolment_progress from public, anon, authenticated;

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

revoke all on function public.sfg_start_family_enrolment(uuid) from public, anon, authenticated;
revoke all on function public.sfg_record_dev_family_capture(uuid,text) from public, anon, authenticated;
revoke all on function public.sfg_complete_dev_family_enrolment(uuid) from public, anon, authenticated;
grant execute on function public.sfg_start_family_enrolment(uuid) to authenticated;
grant execute on function public.sfg_record_dev_family_capture(uuid,text) to authenticated;
grant execute on function public.sfg_complete_dev_family_enrolment(uuid) to authenticated;
