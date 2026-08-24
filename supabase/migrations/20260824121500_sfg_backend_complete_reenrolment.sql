-- sfg_backend_complete_reenrolment
-- Companion to sfg_backend_save_template (migration 20260823180030) for the
-- CoreCV platform child. Identical storage contract -- revoke the previous
-- generation, insert the replacement as TEMPLATE_ACTIVE -- minus the profile
-- demotion to 'pending_pin'. Re-enrolment must leave an active citizen active;
-- PIN setup ordering stays owned by the citizen-facing routines.
--
-- Callable ONLY by postgres/service_role (trusted FastAPI tier through an
-- approved server-side secret). anon/authenticated have no execute grant.
-- The caller supplies the sealed bundle produced by the trusted tier; the raw
-- frame never reaches the database.

create or replace function public.sfg_backend_complete_reenrolment(
  p_citizen_id uuid,
  p_encrypted_payload text,
  p_nonce text,
  p_compatibility_fingerprint jsonb,
  p_encryption_version text
)
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
  return jsonb_build_object('template_id', v_template_id);
end;
$function$;

revoke all on function public.sfg_backend_complete_reenrolment(uuid, text, text, jsonb, text)
  from public, anon, authenticated;
