-- SFG architecture v0.3 — least privilege and row-level security.

alter table public.profiles enable row level security;
alter table public.family_members enable row level security;
alter table public.wallets enable row level security;
alter table public.face_templates enable row level security;
alter table public.transactions enable row level security;
alter table public.verification_sessions enable row level security;
alter table public.kiosks enable row level security;
alter table public.audit_log enable row level security;

create policy profiles_select_own on public.profiles for select to authenticated
  using ((select auth.uid()) = id);
create policy profiles_update_own on public.profiles for update to authenticated
  using ((select auth.uid()) = id) with check ((select auth.uid()) = id);
create policy family_members_select_own on public.family_members for select to authenticated
  using ((select auth.uid()) = user_id);
create policy wallets_select_own on public.wallets for select to authenticated
  using ((select auth.uid()) = user_id);
create policy transactions_select_own on public.transactions for select to authenticated
  using ((select auth.uid()) = user_id);

-- Deliberately NO policies on face_templates, verification_sessions, kiosks or audit_log.
-- RLS deny-by-default keeps these tables invisible to anon/authenticated users.

revoke all on public.profiles from anon, authenticated;
revoke all on public.family_members from anon, authenticated;
revoke all on public.wallets from anon, authenticated;
revoke all on public.face_templates from anon, authenticated;
revoke all on public.transactions from anon, authenticated;
revoke all on public.verification_sessions from anon, authenticated;
revoke all on public.kiosks from anon, authenticated;
revoke all on public.audit_log from anon, authenticated;

grant select (id, full_name, email, enrolment_status, consent_status, profile_state, created_at, updated_at)
  on public.profiles to authenticated;
grant update (full_name) on public.profiles to authenticated;
grant select on public.family_members to authenticated;
grant select on public.wallets to authenticated;
grant select on public.transactions to authenticated;
