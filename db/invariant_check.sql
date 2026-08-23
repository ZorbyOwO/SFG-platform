-- Must return zero rows after every wallet operation.
select
  w.id as wallet_id,
  w.user_id,
  w.family_member_id,
  w.balance as wallet_balance,
  coalesce(sum(
    case t.type
      when 'topup' then t.amount
      when 'transfer_in' then t.amount
      when 'reversal' then t.amount
      when 'purchase' then -t.amount
      when 'transfer_out' then -t.amount
    end
  ), 0) as ledger_balance
from public.wallets w
left join public.transactions t on t.wallet_id = w.id and t.status = 'completed'
group by w.id, w.user_id, w.family_member_id, w.balance
having w.balance <> coalesce(sum(
  case t.type
    when 'topup' then t.amount
    when 'transfer_in' then t.amount
    when 'reversal' then t.amount
    when 'purchase' then -t.amount
    when 'transfer_out' then -t.amount
  end
), 0);
