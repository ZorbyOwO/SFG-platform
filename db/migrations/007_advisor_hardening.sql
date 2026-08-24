-- Follow-up from Supabase security and performance advisors.

do $$
begin
  if exists (
    select 1
    from pg_extension extension_record
    join pg_namespace extension_schema on extension_schema.oid = extension_record.extnamespace
    where extension_record.extname = 'vector' and extension_schema.nspname <> 'extensions'
  ) then
    execute 'alter extension vector set schema extensions';
  end if;
end $$;

create index audit_log_kiosk_idx on public.audit_log(kiosk_id)
  where kiosk_id is not null;
create index transactions_kiosk_idx on public.transactions(kiosk_id)
  where kiosk_id is not null;
create index transactions_reversal_idx on public.transactions(reverses_transaction_id)
  where reverses_transaction_id is not null;
create index verification_sessions_matched_owner_idx
  on public.verification_sessions(matched_user, matched_family_member)
  where matched_user is not null;
create index wallets_family_owner_idx
  on public.wallets(user_id, family_member_id)
  where family_member_id is not null;
