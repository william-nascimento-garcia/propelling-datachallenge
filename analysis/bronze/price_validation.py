import sys
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
sys.path.append(r'C:\Users\William Ordiales\OneDrive\Documentos\propelling_datachellenge\_modules')
from snowflake_client import SnowflakeClient

pd.set_option('display.width', 200)
pd.set_option('display.max_columns', 30)
pd.set_option('display.float_format', lambda v: f'{v:,.2f}')

sf = SnowflakeClient(target="prod", layer="bronze")
sf.connect()

source = 'SNOWFLAKE_SAMPLE_DATA.TPCH_SF1'
expected_copies = 2          # 1 if prod was built with --vars "{simulate_duplicates: false}"

# table, business key in the source, price column in source/Bronze, price column in Silver
tables = [
    {'table': 'lineitem', 'keys': ['l_orderkey', 'l_linenumber'], 'price': 'l_extendedprice', 'silver_price': 'extended_price'},
    {'table': 'orders',   'keys': ['o_orderkey'],                 'price': 'o_totalprice',    'silver_price': 'order_total_price'},
    {'table': 'part',     'keys': ['p_partkey'],                  'price': 'p_retailprice',   'silver_price': 'retail_price'},
    {'table': 'partsupp', 'keys': ['ps_partkey', 'ps_suppkey'],   'price': 'ps_supplycost',   'silver_price': 'supply_cost'},
    {'table': 'customer', 'keys': ['c_custkey'],                  'price': 'c_acctbal',       'silver_price': 'account_balance'},
    {'table': 'supplier', 'keys': ['s_suppkey'],                  'price': 's_acctbal',       'silver_price': 'account_balance'},
]


# ---------------------------------------------------------------------------
# 1. Totals: rows and price sums, source vs Bronze (total, original copy, replay copy) vs Silver
# ---------------------------------------------------------------------------
totals = []
for t in tables:
    sql = f"""
        with src as (
            select count(*) as row_count, sum({t['price']}) as price_sum
            from {source}.{t['table']}
        ),
        brz as (
            select
                count(*)                                                        as row_count,
                sum({t['price']})                                               as price_sum,
                count(distinct _batch_id)                                       as batches,
                sum(iff(endswith(_batch_id, '-replay'), 0, {t['price']}))       as original_price_sum,
                sum(iff(endswith(_batch_id, '-replay'), {t['price']}, 0))       as replay_price_sum
            from {{bronze}}.brz_{t['table']}
        ),
        slv as (
            select count(*) as row_count, sum({t['silver_price']}) as price_sum
            from {{silver}}.slv_{t['table']}
        )
        select
            '{t['table']}'                                          as table_name,
            src.row_count                                           as source_rows,
            brz.row_count                                           as bronze_rows,
            slv.row_count                                           as silver_rows,
            div0(brz.row_count, src.row_count)                      as bronze_row_ratio,
            src.price_sum                                           as source_price,
            brz.price_sum                                           as bronze_price,
            slv.price_sum                                           as silver_price,
            div0(brz.price_sum, src.price_sum)                      as bronze_price_ratio,
            brz.batches                                             as bronze_batches,
            brz.row_count = src.row_count * {expected_copies}
                and brz.price_sum = src.price_sum * {expected_copies}   as bronze_is_{expected_copies}x,
            brz.original_price_sum = src.price_sum
                and (brz.replay_price_sum = src.price_sum or {expected_copies} = 1)  as each_copy_matches,
            slv.row_count = src.row_count
                and slv.price_sum = src.price_sum                   as silver_matches_source
        from src, brz, slv
    """
    totals.append(sf.query_df(sql))

totals = pd.concat(totals, ignore_index=True)
print('\n=== 1. Totals: source vs Bronze vs Silver ===')
print(totals[['table_name', 'source_rows', 'bronze_rows', 'silver_rows', 'bronze_row_ratio', 'bronze_batches']])
print()
print(totals[['table_name', 'source_price', 'bronze_price', 'silver_price', 'bronze_price_ratio']])
print()
print(totals[['table_name', f'bronze_is_{expected_copies}x', 'each_copy_matches', 'silver_matches_source']])


# ---------------------------------------------------------------------------
# 2. Per key: every source key must appear exactly N times in Bronze with the source price
#    full outer join -> also catches keys that exist only in Bronze
# ---------------------------------------------------------------------------
per_key = []
for t in tables:
    keys = ', '.join(t['keys'])
    join_on = ' and '.join(f's.{k} = b.{k}' for k in t['keys'])
    first_key = t['keys'][0]
    sql = f"""
        with brz as (
            select
                {keys},
                count(*)            as copies,
                min({t['price']})   as min_price,
                max({t['price']})   as max_price
            from {{bronze}}.brz_{t['table']}
            group by {keys}
        )
        select
            '{t['table']}'                                                      as table_name,
            count_if(s.{first_key} is not null)                                 as source_keys,
            count_if(b.copies = {expected_copies})                              as keys_ok,
            count_if(s.{first_key} is not null and b.{first_key} is null)       as missing_in_bronze,
            count_if(s.{first_key} is null and b.{first_key} is not null)       as only_in_bronze,
            count_if(b.copies <> {expected_copies})                             as wrong_copy_count,
            count_if(b.min_price <> s.{t['price']} or b.max_price <> s.{t['price']}) as price_mismatch
        from {source}.{t['table']} s
        full outer join brz b on {join_on}
    """
    per_key.append(sf.query_df(sql))

per_key = pd.concat(per_key, ignore_index=True)
per_key['all_keys_ok'] = (
    (per_key['keys_ok'] == per_key['source_keys'])
    & (per_key[['missing_in_bronze', 'only_in_bronze', 'wrong_copy_count', 'price_mismatch']].sum(axis=1) == 0)
)
print('\n=== 2. Per key: copies and price of each source key in Bronze ===')
print(per_key)

# Example of the duplication on one order: the 2 Bronze rows next to the source row
example = sf.query_df(f"""
    select 'source' as origin, o_orderkey, o_totalprice, null as _batch_id, null as _loaded_at
    from {source}.orders where o_orderkey = 1
    union all
    select 'bronze', o_orderkey, o_totalprice, _batch_id, _loaded_at
    from {{bronze}}.brz_orders where o_orderkey = 1
    order by origin desc, _loaded_at
""")
print('\n=== Example: order 1 in the source and in Bronze ===')
print(example)

sf.close()


# ---------------------------------------------------------------------------
# 3. Verdict
# ---------------------------------------------------------------------------
checks = totals[['table_name', f'bronze_is_{expected_copies}x', 'each_copy_matches', 'silver_matches_source']].merge(
    per_key[['table_name', 'all_keys_ok']], on='table_name'
)
checks['passed'] = checks.drop(columns='table_name').all(axis=1)
print('\n=== 3. Verdict ===')
print(checks)
if checks['passed'].all():
    print(f'\nOK: Bronze holds exactly {expected_copies} identical copies of every source row (same prices), '
          f'and Silver is back to 1 copy matching the source.')
else:
    print('\nFAILED in:', ', '.join(checks.loc[~checks['passed'], 'table_name']))


# ---------------------------------------------------------------------------
# 4. Chart: price sum of Bronze and Silver as a multiple of the source
# ---------------------------------------------------------------------------
charts_dir = Path(r'C:\Users\William Ordiales\OneDrive\Documentos\propelling_datachellenge\analysis\charts')
charts_dir.mkdir(parents=True, exist_ok=True)

blue, orange, text_secondary, grid_color = '#2a78d6', '#eb6834', '#52514e', '#e4e3df'
ratio = totals.set_index('table_name')
ratio['silver_price_ratio'] = ratio['silver_price'] / ratio['source_price']

fig, ax = plt.subplots(figsize=(16, 9))
x = range(len(ratio))
width = 0.38
bars_brz = ax.bar([i - width / 2 for i in x], ratio['bronze_price_ratio'], width, color=orange, label='Bronze / origen')
bars_slv = ax.bar([i + width / 2 for i in x], ratio['silver_price_ratio'], width, color=blue, label='Silver / origen')
for bars in (bars_brz, bars_slv):
    ax.bar_label(bars, labels=[f'{v:.2f}x'.replace('.', ',') for v in bars.datavalues], padding=4, fontsize=14)
ax.axhline(expected_copies, color=orange, linestyle='--', linewidth=1)
ax.axhline(1, color=blue, linestyle='--', linewidth=1)
ax.set_xticks(list(x), [f'brz_{t}' for t in ratio.index], fontsize=14)
ax.set_ylim(0, expected_copies * 1.2)
ax.set_ylabel('Suma de precios / suma en el origen', color=text_secondary, fontsize=15)
ax.set_title('La duplicación en Bronze es exacta: 2x el origen, y Silver vuelve a 1x',
             loc='left', fontsize=22, fontweight='bold', pad=18)
ax.spines[['top', 'right']].set_visible(False)
ax.grid(axis='y', color=grid_color)
ax.set_axisbelow(True)
ax.legend(frameon=False, fontsize=14, loc='upper right')
fig.tight_layout()
fig.savefig(charts_dir / '08_bronze_duplication_check.png', dpi=150)
plt.show()
