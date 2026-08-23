-- SFG architecture v0.3 — canonical persistence model.
-- IMPORTANT: searchable pgvector storage is a development architecture profile.
-- Do not claim encrypted-template conformance until the conflict in Appendix C.6 is approved.

create table public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  ic_number text not null unique,
  full_name text not null,
  email text not null,
  pin_hash text,
  enrolment_status text not null default 'ENROLMENT_STARTED'
    check (enrolment_status in ('ENROLMENT_STARTED','ENROLMENT_COMPLETED','ENROLMENT_FAILED','ENROLMENT_CANCELLED')),
  consent_status text not null default 'CONSENT_REQUIRED'
    check (consent_status in ('CONSENT_GRANTED','CONSENT_WITHDRAWN','CONSENT_REQUIRED')),
  profile_state text not null default 'pending_face'
    check (profile_state in ('pending_face','pending_pin','pending_review','active','suspended')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint profiles_ic_is_12_digits check (ic_number ~ '^[0-9]{12}$')
);

create table public.kiosks (
  id text primary key,
  kiosk_name text not null,
  merchant_name text not null,
  merchant_location text,
  api_key_hash text not null,
  is_active boolean not null default true,
  created_at timestamptz not null default now()
);

create table public.family_members (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  ic_number text not null unique,
  full_name text not null,
  relationship text not null,
  enrolment_status text not null default 'ENROLMENT_STARTED'
    check (enrolment_status in ('ENROLMENT_STARTED','ENROLMENT_COMPLETED','ENROLMENT_FAILED','ENROLMENT_CANCELLED')),
  consent_status text not null default 'CONSENT_REQUIRED'
    check (consent_status in ('CONSENT_GRANTED','CONSENT_WITHDRAWN','CONSENT_REQUIRED')),
  profile_state text not null default 'pending_face'
    check (profile_state in ('pending_face','active','suspended','deactivated')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint family_ic_is_12_digits check (ic_number ~ '^[0-9]{12}$'),
  constraint family_owner_pair unique (user_id, id)
);
create index family_members_user_idx on public.family_members(user_id);

create table public.wallets (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  family_member_id uuid unique,
  balance numeric(12,2) not null default 0.00 check (balance >= 0),
  currency text not null default 'MYR' check (currency = 'MYR'),
  updated_at timestamptz not null default now(),
  constraint family_wallet_owner foreign key (user_id, family_member_id)
    references public.family_members(user_id, id) on delete cascade
);
create unique index one_main_wallet_per_user on public.wallets(user_id) where family_member_id is null;
create index wallets_user_idx on public.wallets(user_id);

create table public.face_templates (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  family_member_id uuid,
  embedding vector(128) not null,
  capture_pose text not null check (capture_pose in ('front','right','left')),
  model_version text not null default 'sface_2021dec',
  quality_score real check (quality_score is null or quality_score between 0 and 1),
  template_status text not null default 'TEMPLATE_ACTIVE'
    check (template_status in ('TEMPLATE_ACTIVE','TEMPLATE_REVOKED')),
  created_at timestamptz not null default now(),
  constraint template_family_owner foreign key (user_id, family_member_id)
    references public.family_members(user_id, id) on delete cascade
);
create index face_templates_embedding_idx on public.face_templates using hnsw (embedding vector_cosine_ops);
create index face_templates_user_idx on public.face_templates(user_id);
create index face_templates_family_idx on public.face_templates(family_member_id) where family_member_id is not null;
create index face_templates_active_idx on public.face_templates(user_id, family_member_id)
  where template_status = 'TEMPLATE_ACTIVE';

create table public.transactions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references public.profiles(id) on delete set null,
  wallet_id uuid references public.wallets(id) on delete set null,
  family_member_id uuid references public.family_members(id) on delete set null,
  type text not null check (type in ('topup','purchase','transfer_out','transfer_in','reversal')),
  status text not null default 'completed' check (status in ('pending','completed','failed')),
  amount numeric(12,2) not null check (amount > 0),
  balance_after numeric(12,2),
  merchant_name text,
  kiosk_id text references public.kiosks(id) on delete set null,
  auth_method text not null check (auth_method in ('face_pin','face_only','app_topup','guardian_pin')),
  reference text not null,
  correlation_id uuid,
  reverses_transaction_id uuid references public.transactions(id),
  idempotency_key text unique,
  created_at timestamptz not null default now(),
  constraint completed_transaction_has_balance check (status <> 'completed' or balance_after is not null)
);
create index transactions_user_time_idx on public.transactions(user_id, created_at desc);
create index transactions_wallet_time_idx on public.transactions(wallet_id, created_at desc);
create index transactions_family_time_idx on public.transactions(family_member_id, created_at desc)
  where family_member_id is not null;
create index transactions_pending_idx on public.transactions(created_at)
  where status = 'pending';

create table public.verification_sessions (
  session_id uuid primary key default gen_random_uuid(),
  correlation_id uuid not null unique default gen_random_uuid(),
  nonce text not null unique,
  kiosk_id text references public.kiosks(id) on delete set null,
  purpose text not null check (purpose in ('enrol','family_enrol','pay')),
  amount numeric(12,2),
  status text not null default 'open' check (status in ('open','matched','consumed','expired','failed')),
  capture_status text check (capture_status in ('CAPTURE_READY','NO_FACE','MULTIPLE_FACES','INVALID_CAPTURE','CAMERA_ERROR')),
  liveness_status text check (liveness_status in ('PAD_LIVE','PAD_REJECT','PAD_UNCERTAIN','PAD_ERROR')),
  match_status text check (match_status in ('MATCH_CONFIRMED','NO_MATCH','AMBIGUOUS_MATCH','MATCH_ERROR')),
  identity_confirmation_status text check (identity_confirmation_status in ('IDENTITY_CONFIRMATION_REQUIRED','IDENTITY_CONFIRMED','IDENTITY_REJECTED')),
  pin_status text check (pin_status in ('PIN_ACCEPTED','PIN_REJECTED','PIN_LOCKED')),
  authorization_status text check (authorization_status in ('AUTHORIZATION_GRANTED','AUTHORIZATION_DENIED')),
  service_access_status text check (service_access_status in ('SERVICE_ACCESS_GRANTED','SERVICE_ACCESS_DENIED')),
  matched_user uuid references public.profiles(id) on delete set null,
  matched_family_member uuid,
  pin_attempts smallint not null default 0 check (pin_attempts >= 0),
  verification_completed_at timestamptz,
  created_at timestamptz not null default now(),
  expires_at timestamptz not null default (now() + interval '90 seconds'),
  constraint session_family_owner foreign key (matched_user, matched_family_member)
    references public.family_members(user_id, id) on delete set null,
  constraint payment_does_not_emit_service_access check (purpose <> 'pay' or service_access_status is null),
  constraint authorization_requires_pin check (authorization_status <> 'AUTHORIZATION_GRANTED' or pin_status = 'PIN_ACCEPTED'),
  constraint access_requires_authorization check (service_access_status <> 'SERVICE_ACCESS_GRANTED' or authorization_status = 'AUTHORIZATION_GRANTED')
);
create index verification_sessions_expiry_idx on public.verification_sessions(expires_at)
  where status in ('open','matched');
create index verification_sessions_kiosk_idx on public.verification_sessions(kiosk_id, created_at desc);

create table public.audit_log (
  audit_event_id uuid primary key default gen_random_uuid(),
  -- Exact audit_event_type values are unresolved. Only trusted server/database code may write this field.
  audit_event_type text not null,
  session_id uuid references public.verification_sessions(session_id) on delete set null,
  correlation_id uuid,
  citizen_id uuid references public.profiles(id) on delete set null,
  kiosk_id text references public.kiosks(id) on delete set null,
  verification_completed_at timestamptz,
  authorization_status text check (authorization_status in ('AUTHORIZATION_GRANTED','AUTHORIZATION_DENIED')),
  service_access_status text check (service_access_status in ('SERVICE_ACCESS_GRANTED','SERVICE_ACCESS_DENIED')),
  detail jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  constraint audit_access_requires_authorization check (service_access_status <> 'SERVICE_ACCESS_GRANTED' or authorization_status = 'AUTHORIZATION_GRANTED')
);
create index audit_log_session_idx on public.audit_log(session_id);
create index audit_log_correlation_idx on public.audit_log(correlation_id);
create index audit_log_citizen_time_idx on public.audit_log(citizen_id, created_at desc);

create or replace function public.tg_create_main_wallet() returns trigger
language plpgsql security definer set search_path = public as $$
begin
  insert into public.wallets (user_id) values (new.id);
  return new;
end $$;

create trigger create_main_wallet_on_profile
  after insert on public.profiles for each row execute function public.tg_create_main_wallet();

create or replace function public.tg_create_family_wallet() returns trigger
language plpgsql security definer set search_path = public as $$
begin
  insert into public.wallets (user_id, family_member_id) values (new.user_id, new.id);
  return new;
end $$;

create trigger create_family_wallet_on_member
  after insert on public.family_members for each row execute function public.tg_create_family_wallet();
