-- Expose the verified solar total needed by the green-credit frontend while
-- retaining integer microcredits as the source of truth for balances.
create or replace view green_credit_wallets with (security_invoker = true) as
select
  account.id as account_id,
  account.user_id,
  account.status,
  coalesce(sum(entry.amount_microcredits), 0)::bigint as available_microcredits,
  coalesce(sum(entry.amount_microcredits) filter (where entry.amount_microcredits > 0), 0)::bigint
    as lifetime_earned_microcredits,
  coalesce(sum(-entry.amount_microcredits) filter (where entry.entry_type = 'allocate'), 0)::bigint
    as lifetime_allocated_microcredits,
  coalesce(sum(entry.source_solar_kwh) filter (where entry.entry_type = 'earn'), 0)::numeric
    as verified_solar_kwh,
  account.created_at,
  account.updated_at
from green_credit_accounts account
left join green_credit_ledger_entries entry on entry.account_id = account.id
group by account.id;

grant select on green_credit_wallets to authenticated;
