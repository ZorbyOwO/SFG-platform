-- sfg_protected_biometric_templates
-- RECOVERED 2026-08-24 from the live SFG project (ref oxpvsblgjrvfbrbaluxp),
-- applied there originally at 2026-08-23 17:40:47 UTC but never committed to
-- this repository. Reconstructed from pg catalog introspection; end state is
-- byte-equivalent to the live schema. Zero rows existed at recovery time.

create schema if not exists private;

create table private.sfg_biometric_templates (
  template_id uuid primary key default gen_random_uuid(),
  citizen_id uuid not null references public.profiles(id) on delete cascade,
  encrypted_payload bytea not null,
  nonce bytea not null,
  compatibility_fingerprint jsonb not null,
  encryption_version text not null,
  template_status text not null default 'TEMPLATE_ACTIVE',
  created_at timestamptz not null default now(),
  constraint sfg_biometric_templates_encrypted_payload_check
    check (octet_length(encrypted_payload) > 512),
  constraint sfg_biometric_templates_nonce_check
    check (octet_length(nonce) = 12),
  constraint sfg_biometric_templates_compatibility_fingerprint_check
    check (jsonb_typeof(compatibility_fingerprint) = 'object'),
  constraint sfg_biometric_templates_encryption_version_check
    check (encryption_version = 'sfg-aesgcm-v1'),
  constraint sfg_biometric_templates_template_status_check
    check (template_status in ('TEMPLATE_ACTIVE','TEMPLATE_REVOKED'))
);

create index sfg_biometric_templates_citizen_id_idx
  on private.sfg_biometric_templates(citizen_id);

create unique index sfg_one_active_template_per_citizen_idx
  on private.sfg_biometric_templates(citizen_id)
  where template_status = 'TEMPLATE_ACTIVE';

-- Deny-all posture: RLS enabled with no policies; no grants to anon,
-- authenticated, or service_role on the table itself.
alter table private.sfg_biometric_templates enable row level security;
