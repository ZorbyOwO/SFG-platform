-- sfg_trusted_backend_adapter
-- RECOVERED 2026-08-24 from the live SFG project (ref oxpvsblgjrvfbrbaluxp),
-- applied there originally at 2026-08-23 18:00:30 UTC but never committed to
-- this repository. Function bodies reconstructed from pg_get_functiondef;
-- end state is equivalent to the live schema.
--
-- Purpose: SECURITY DEFINER seam for the trusted FastAPI/kiosk tier. The tier
-- holds no Supabase secret, so a future server-side connection calls these
-- routines through an approved credential instead of touching tables directly.
-- Execute is granted ONLY to postgres and service_role; anon and authenticated
-- have no access. The kiosk child's 1:N search remains unresolved: this adapter
-- loads whole active templates, it does not search.

create or replace function public.sfg_backend_confirm_details(p_citizen_id uuid, p_full_name text, p_ic text)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $function$
begin
  if length(trim(p_full_name)) < 2 or p_ic !~ '^[0-9]{12}$' then
    raise exception 'DETAILS_INVALID';
  end if;
  update public.profiles set full_name = trim(p_full_name), ic_number = p_ic, updated_at = now()
  where id = p_citizen_id;
  if not found then raise exception 'CITIZEN_PROFILE_UNAVAILABLE'; end if;
  return '{}'::jsonb;
end;
$function$;

create or replace function public.sfg_backend_get_kiosk(p_kiosk_id text)
returns jsonb
language sql
security definer
set search_path = ''
as $function$
  select coalesce((
    select jsonb_build_object('kiosk_id', k.id, 'kiosk_name', k.kiosk_name)
    from public.kiosks k where k.id = p_kiosk_id and k.is_active
  ), 'null'::jsonb);
$function$;

create or replace function public.sfg_backend_grant_consent(p_citizen_id uuid)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $function$
begin
  update public.profiles set
    consent_status = 'CONSENT_GRANTED', enrolment_status = 'ENROLMENT_STARTED',
    profile_state = 'pending_face', updated_at = now()
  where id = p_citizen_id;
  if not found then raise exception 'CITIZEN_PROFILE_UNAVAILABLE'; end if;
  return '{}'::jsonb;
end;
$function$;

create or replace function public.sfg_backend_load_templates(p_encryption_version text)
returns jsonb
language sql
security definer
set search_path = ''
as $function$
  select coalesce(jsonb_agg(jsonb_build_object(
    'template_id', t.template_id,
    'citizen_id', t.citizen_id,
    'encrypted_payload', encode(t.encrypted_payload, 'base64'),
    'nonce', encode(t.nonce, 'base64'),
    'compatibility_fingerprint', t.compatibility_fingerprint
  ) order by t.template_id), '[]'::jsonb)
  from private.sfg_biometric_templates t
  join public.profiles p on p.id = t.citizen_id
  where t.template_status = 'TEMPLATE_ACTIVE'
    and t.encryption_version = p_encryption_version
    and p.enrolment_status = 'ENROLMENT_COMPLETED'
    and p.consent_status = 'CONSENT_GRANTED';
$function$;

create or replace function public.sfg_backend_record_audit(p_correlation_id uuid, p_citizen_id uuid, p_kiosk_id text)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $function$
declare v_id uuid; v_completed timestamptz := now();
begin
  insert into public.audit_log (
    audit_event_type, session_id, correlation_id, citizen_id, kiosk_id,
    verification_completed_at, authorization_status, service_access_status, detail
  ) values (
    'SERVICE_ACCESS_DECISION', null, p_correlation_id, p_citizen_id, p_kiosk_id,
    v_completed, 'AUTHORIZATION_GRANTED', 'SERVICE_ACCESS_GRANTED', '{}'::jsonb
  ) returning audit_event_id into v_id;
  return jsonb_build_object('audit_event_id', v_id, 'verification_completed_at', v_completed);
end;
$function$;

create or replace function public.sfg_backend_save_template(p_citizen_id uuid, p_encrypted_payload text, p_nonce text, p_compatibility_fingerprint jsonb, p_encryption_version text)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $function$
declare v_template_id uuid;
begin
  if p_encryption_version <> 'sfg-aesgcm-v1' then raise exception 'ENCRYPTION_VERSION_INVALID'; end if;
  update private.sfg_biometric_templates set template_status = 'TEMPLATE_REVOKED'
    where citizen_id = p_citizen_id and template_status = 'TEMPLATE_ACTIVE';
  insert into private.sfg_biometric_templates (
    citizen_id, encrypted_payload, nonce, compatibility_fingerprint, encryption_version, template_status
  ) values (
    p_citizen_id, decode(p_encrypted_payload, 'base64'), decode(p_nonce, 'base64'),
    p_compatibility_fingerprint, p_encryption_version, 'TEMPLATE_ACTIVE'
  ) returning template_id into v_template_id;
  update public.profiles set profile_state = 'pending_pin', updated_at = now() where id = p_citizen_id;
  if not found then raise exception 'CITIZEN_PROFILE_UNAVAILABLE'; end if;
  return jsonb_build_object('template_id', v_template_id);
end;
$function$;

create or replace function public.sfg_backend_set_pin(p_citizen_id uuid, p_pin text)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $function$
begin
  if p_pin !~ '^[0-9]{6}$' then raise exception 'PIN_INVALID'; end if;
  update public.profiles p set
    pin_hash = extensions.crypt(p_pin, extensions.gen_salt('bf')),
    enrolment_status = 'ENROLMENT_COMPLETED', profile_state = 'active', updated_at = now()
  where p.id = p_citizen_id and p.consent_status = 'CONSENT_GRANTED'
    and exists (
      select 1 from private.sfg_biometric_templates t
      where t.citizen_id = p.id and t.template_status = 'TEMPLATE_ACTIVE'
    );
  if not found then raise exception 'ENROLMENT_NOT_READY'; end if;
  return '{}'::jsonb;
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
    where p.id = p_citizen_id and p.enrolment_status = 'ENROLMENT_COMPLETED'
      and p.consent_status = 'CONSENT_GRANTED' and p.pin_hash is not null
  ), false));
$function$;

revoke all on function
  public.sfg_backend_confirm_details(uuid, text, text),
  public.sfg_backend_get_kiosk(text),
  public.sfg_backend_grant_consent(uuid),
  public.sfg_backend_load_templates(text),
  public.sfg_backend_record_audit(uuid, uuid, text),
  public.sfg_backend_save_template(uuid, text, text, jsonb, text),
  public.sfg_backend_set_pin(uuid, text),
  public.sfg_backend_verify_pin(uuid, text)
from public, anon, authenticated;
