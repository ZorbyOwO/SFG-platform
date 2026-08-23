-- Registry seed only. It is inactive and contains no usable credential.
-- Provision a real hash through the approved local secret mechanism before activation.
insert into public.kiosks (id, kiosk_name, merchant_name, api_key_hash, is_active)
values ('SFG-KIOSK-001', 'Kiosk UTC', 'Sarawak Mart Kuching', 'PROVISION_BEFORE_ACTIVATION', false)
on conflict (id) do nothing;
