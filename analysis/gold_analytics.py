import sys
from pathlib import Path
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter, PercentFormatter
sys.path.append(r'C:\Users\William Ordiales\OneDrive\Documentos\propelling_datachellenge\_modules')
from snowflake_client import SnowflakeClient

sf = SnowflakeClient(target="prod", layer="gold")
sf.connect()

charts_dir = Path(r'C:\Users\William Ordiales\OneDrive\Documentos\propelling_datachellenge\analysis\charts')
charts_dir.mkdir(parents=True, exist_ok=True)

# Validated categorical palette (fixed order, colorblind-safe for adjacent series)
blue, orange, aqua, yellow, magenta = '#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4'
text_primary, text_secondary, grid_color, surface = '#0b0b0b', '#52514e', '#e4e3df', '#ffffff'

plt.rcParams.update({
    'figure.figsize': (16, 9),
    'figure.dpi': 100,
    'savefig.dpi': 150,
    'figure.facecolor': surface,
    'axes.facecolor': surface,
    'font.size': 16,
    'axes.titlesize': 24,
    'axes.titleweight': 'bold',
    'axes.titlelocation': 'left',
    'axes.titlepad': 18,
    'axes.labelsize': 16,
    'axes.labelcolor': text_secondary,
    'axes.edgecolor': grid_color,
    'axes.spines.top': False,
    'axes.spines.right': False,
    'axes.grid': True,
    'grid.color': grid_color,
    'grid.linewidth': 1,
    'xtick.color': text_secondary,
    'ytick.color': text_secondary,
    'text.color': text_primary,
    'legend.frameon': False,
    'lines.linewidth': 2.5,
})

# Spanish number format: decimal comma, thousands dot. Amounts shown in millions of dollars (M$)
es = lambda text: text.replace(',', '§').replace('.', ',').replace('§', '.')
musd = lambda v: es(f'{v / 1e6:,.0f}') + ' M$'
pct = lambda v, d=1: es(f'{v * 100:.{d}f}') + '%'
billions = FuncFormatter(lambda v, _: musd(v))
region_es = {'Africa': 'África', 'America': 'América', 'Asia': 'Asia', 'Europe': 'Europa', 'Middle East': 'Oriente Medio'}

kpis = sf.to_pandas(sf.query("""
    select
        count(*)                                        as order_lines,
        count(distinct order_id)                        as orders,
        count(distinct customer_sk)                     as active_customers,
        sum(gross_sales_amount)                         as gross_sales,
        sum(discount_amount)                            as discount_given,
        sum(net_revenue)                                as net_revenue,
        sum(gross_margin)                               as gross_margin,
        div0(sum(gross_margin), sum(net_revenue))       as gross_margin_pct,
        div0(count_if(is_received and is_late_delivery), count_if(is_received)) as late_delivery_rate
    from fct_order_lines
"""))
print(kpis.T)


# ---------------------------------------------------------------------------
# 1. Revenue and margin over time (monthly)
#    1998 is a partial year: TPC-H orders stop in August 1998.
# ---------------------------------------------------------------------------
monthly = sf.to_pandas(sf.query("""
    select
        d.month_start_date,
        sum(f.net_revenue)   as net_revenue,
        sum(f.gross_margin)  as gross_margin
    from fct_order_lines f
    left join dim_date d on f.order_date_key = d.date_key
    group by all
    order by d.month_start_date
"""))
monthly = monthly[monthly['month_start_date'] < monthly['month_start_date'].max()]   # drop the incomplete last month

fig, ax = plt.subplots()
ax.plot(monthly['month_start_date'], monthly['net_revenue'], color=blue, label='Ingresos netos')
ax.plot(monthly['month_start_date'], monthly['gross_margin'], color=orange, label='Margen bruto')
ax.yaxis.set_major_formatter(billions)
ax.set_ylim(bottom=0)
ax.grid(axis='x', visible=False)
ax.set_title('Ingresos netos y margen bruto mensuales')
ax.set_xlabel('Mes del pedido')
for col, color, name in [('net_revenue', blue, 'Ingresos netos'), ('gross_margin', orange, 'Margen bruto')]:
    last = monthly.iloc[-1]
    ax.annotate(name, (last['month_start_date'], last[col]), xytext=(10, 0), textcoords='offset points',
                va='center', color=text_primary, fontsize=15)
ax.legend(loc='lower left')
fig.tight_layout()
fig.savefig(charts_dir / '01_monthly_revenue_margin.png')
plt.show()


# ---------------------------------------------------------------------------
# 2. Net revenue by customer region (full years only: 1992-1997)
# ---------------------------------------------------------------------------
region_year = sf.to_pandas(sf.query("""
    select
        d.year_number,
        c.region_name,
        sum(f.net_revenue)                                as net_revenue,
        sum(f.gross_margin)                               as gross_margin,
        div0(sum(f.gross_margin), sum(f.net_revenue))     as gross_margin_pct
    from fct_order_lines f
    left join dim_customer c on f.customer_sk = c.customer_sk
    left join dim_date d     on f.order_date_key = d.date_key
    where d.year_number <= 1997
    group by all
    order by d.year_number, c.region_name
"""))
print(region_year.pivot(index='year_number', columns='region_name', values='net_revenue'))

by_region = (region_year.groupby('region_name', as_index=False)
             .agg(net_revenue=('net_revenue', 'sum'), gross_margin=('gross_margin', 'sum')))
by_region['share'] = by_region['net_revenue'] / by_region['net_revenue'].sum()
by_region['gross_margin_pct'] = by_region['gross_margin'] / by_region['net_revenue']
by_region = by_region.sort_values('net_revenue')
by_region['region_es'] = by_region['region_name'].map(region_es)
print(by_region)

fig, ax = plt.subplots()
bars = ax.barh(by_region['region_es'], by_region['net_revenue'], color=blue, height=0.6)
ax.bar_label(bars, labels=[f'{musd(v)}  ·  {pct(s)} del total  ·  margen {pct(m)}'
                           for v, s, m in zip(by_region['net_revenue'], by_region['share'], by_region['gross_margin_pct'])],
             padding=8, fontsize=14, color=text_primary)
ax.xaxis.set_major_formatter(billions)
ax.set_xlim(0, by_region['net_revenue'].max() * 1.45)
ax.grid(axis='y', visible=False)
ax.set_title('Ingresos netos por región del cliente, 1992-1997')
ax.set_xlabel('Ingresos netos')
fig.tight_layout()
fig.savefig(charts_dir / '02_revenue_by_region.png')
plt.show()


# ---------------------------------------------------------------------------
# 3. How much margin does discounting cost?
#    Margin % by discount level (0% to 10%), computed on net revenue.
# ---------------------------------------------------------------------------
discount = sf.to_pandas(sf.query("""
    select
        discount_rate,
        count(*)                                        as order_lines,
        sum(gross_sales_amount)                         as gross_sales,
        sum(discount_amount)                            as discount_given,
        sum(net_revenue)                                as net_revenue,
        sum(gross_margin)                               as gross_margin,
        div0(sum(gross_margin), sum(net_revenue))       as gross_margin_pct
    from fct_order_lines
    group by all
    order by discount_rate
"""))
print(discount)

fig, ax = plt.subplots()
labels = [pct(d, 0) for d in discount['discount_rate']]
bars = ax.bar(labels, discount['gross_margin_pct'], color=blue, width=0.7)
ax.bar_label(bars, labels=[pct(v) for v in discount['gross_margin_pct']], padding=6, fontsize=14,
             color=text_primary)
ax.yaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
ax.set_ylim(0, discount['gross_margin_pct'].max() * 1.15)
ax.grid(axis='x', visible=False)
ax.set_title('El margen bruto cae a medida que crece el descuento')
ax.set_xlabel('Descuento aplicado a la línea de pedido')
ax.set_ylabel('Margen bruto (% de los ingresos netos)')
fig.tight_layout()
fig.savefig(charts_dir / '03_margin_by_discount.png')
plt.show()

total_discount = discount['discount_given'].sum()
print(f"Total discount given: ${total_discount / 1e9:,.2f}B "
      f"({total_discount / discount['gross_sales'].sum():.1%} of gross sales)")


# ---------------------------------------------------------------------------
# 4. Market segments: discount and margin (table for the slide)
# ---------------------------------------------------------------------------
segments = sf.to_pandas(sf.query("""
    select
        c.market_segment,
        sum(f.net_revenue)                                          as net_revenue,
        sum(f.discount_amount)                                      as discount_given,
        div0(sum(f.discount_amount), sum(f.gross_sales_amount))     as effective_discount_rate,
        div0(sum(f.gross_margin), sum(f.net_revenue))               as gross_margin_pct
    from fct_order_lines f
    left join dim_customer c on f.customer_sk = c.customer_sk
    group by all
    order by net_revenue desc
"""))
print(segments)


# ---------------------------------------------------------------------------
# 5. Top 10 brands by gross margin
# ---------------------------------------------------------------------------
brands = sf.to_pandas(sf.query("""
    select
        p.brand,
        sum(f.net_revenue)                                as net_revenue,
        sum(f.gross_margin)                               as gross_margin,
        div0(sum(f.gross_margin), sum(f.net_revenue))     as gross_margin_pct
    from fct_order_lines f
    left join dim_part p on f.part_sk = p.part_sk
    group by all
    order by gross_margin desc
    limit 10
"""))
print(brands)

top = brands.sort_values('gross_margin')
fig, ax = plt.subplots()
bars = ax.barh(top['brand'], top['gross_margin'], color=blue, height=0.65)
ax.bar_label(bars, labels=[f'{musd(v)}  ·  {pct(p)}' for v, p in zip(top['gross_margin'], top['gross_margin_pct'])],
             padding=8, fontsize=14, color=text_primary)
ax.xaxis.set_major_formatter(billions)
ax.set_xlim(0, top['gross_margin'].max() * 1.25)
ax.grid(axis='y', visible=False)
ax.set_title('Top 10 marcas por margen bruto  (etiqueta: margen · % de margen)')
ax.set_xlabel('Margen bruto')
fig.tight_layout()
fig.savefig(charts_dir / '04_top_brands_margin.png')
plt.show()


# ---------------------------------------------------------------------------
# 6. Supplier delivery performance: distribution of late-delivery rates
#    Only received lines can be judged late or on time.
# ---------------------------------------------------------------------------
suppliers = sf.to_pandas(sf.query("""
    select
        s.supplier_name,
        s.nation_name,
        s.region_name,
        count(*)                                                     as received_lines,
        div0(count_if(f.is_late_delivery), count(*))                 as late_delivery_rate,
        avg(f.delivery_delay_days)                                   as avg_delay_days,
        sum(iff(f.is_late_delivery, f.net_revenue, 0))               as late_net_revenue
    from fct_order_lines f
    left join dim_supplier s on f.supplier_sk = s.supplier_sk
    where f.is_received
    group by all
    having count(*) >= 100
"""))
print(suppliers.sort_values('late_delivery_rate', ascending=False).head(10))

median_rate = suppliers['late_delivery_rate'].median()
fig, ax = plt.subplots()
ax.hist(suppliers['late_delivery_rate'], bins=40, color=blue, edgecolor=surface, linewidth=2)
ax.axvline(median_rate, color=text_primary, linewidth=2, linestyle='--')
ax.annotate(f'Mediana {pct(median_rate)}', (median_rate, ax.get_ylim()[1] * 0.92), xytext=(10, 0),
            textcoords='offset points', fontsize=15, color=text_primary)
ax.xaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
ax.grid(axis='x', visible=False)
ax.set_title(f"Tasa de entregas con retraso en {es(f'{len(suppliers):,}')} proveedores")
ax.set_xlabel('% de líneas recibidas después de la fecha comprometida')
ax.set_ylabel('Número de proveedores')
fig.tight_layout()
fig.savefig(charts_dir / '05_supplier_late_rate_distribution.png')
plt.show()


# ---------------------------------------------------------------------------
# 7. Revenue at risk: share of revenue delivered late, by supplier region
# ---------------------------------------------------------------------------
risk = (suppliers.groupby('region_name', as_index=False)
        .agg(late_net_revenue=('late_net_revenue', 'sum')))
region_revenue = sf.to_pandas(sf.query("""
    select s.region_name, sum(f.net_revenue) as received_net_revenue
    from fct_order_lines f
    left join dim_supplier s on f.supplier_sk = s.supplier_sk
    where f.is_received
    group by all
"""))
risk = risk.merge(region_revenue, on='region_name')
risk['late_revenue_share'] = risk['late_net_revenue'] / risk['received_net_revenue']
risk = risk.sort_values('late_net_revenue')
risk['region_es'] = risk['region_name'].map(region_es)
print(risk)

fig, ax = plt.subplots()
bars = ax.barh(risk['region_es'], risk['late_net_revenue'], color=orange, height=0.6)
ax.bar_label(bars, labels=[f'{musd(v)}  ·  {pct(s)} de los ingresos'
                           for v, s in zip(risk['late_net_revenue'], risk['late_revenue_share'])],
             padding=8, fontsize=14, color=text_primary)
ax.xaxis.set_major_formatter(billions)
ax.set_xlim(0, risk['late_net_revenue'].max() * 1.35)
ax.grid(axis='y', visible=False)
ax.set_title('Ingresos entregados con retraso, por región del proveedor')
ax.set_xlabel('Ingresos netos de líneas recibidas después de la fecha comprometida')
fig.tight_layout()
fig.savefig(charts_dir / '06_revenue_at_risk_by_region.png')
plt.show()


# ---------------------------------------------------------------------------
# 8. Customer concentration (Pareto): how much revenue do the top customers bring?
# ---------------------------------------------------------------------------
pareto = sf.to_pandas(sf.query("""
    with customer_revenue as (
        select customer_sk, sum(net_revenue) as net_revenue
        from fct_order_lines
        group by all
    ),
    ranked as (
        select net_revenue, ntile(100) over (order by net_revenue desc) as customer_percentile
        from customer_revenue
    )
    select customer_percentile, sum(net_revenue) as net_revenue, count(*) as customers
    from ranked
    group by all
    order by customer_percentile
"""))
pareto['cumulative_share'] = pareto['net_revenue'].cumsum() / pareto['net_revenue'].sum()
top20_share = pareto.loc[pareto['customer_percentile'] == 20, 'cumulative_share'].iloc[0]
print(f'Top 20% of customers bring {top20_share:.1%} of net revenue')

fig, ax = plt.subplots()
ax.plot(pareto['customer_percentile'], pareto['cumulative_share'], color=blue, label='% acumulado de los ingresos')
ax.plot([0, 100], [0, 1], color=text_secondary, linewidth=1.5, linestyle='--', label='Distribución perfectamente uniforme')
ax.scatter([20], [top20_share], s=90, color=blue, edgecolor=surface, linewidth=2, zorder=3)
ax.annotate(f'El 20% de clientes principales = {pct(top20_share, 0)} de los ingresos', (20, top20_share), xytext=(18, -30),
            textcoords='offset points', fontsize=15, color=text_primary)
ax.xaxis.set_major_formatter(PercentFormatter(100, decimals=0))
ax.yaxis.set_major_formatter(PercentFormatter(1.0, decimals=0))
ax.set_xlim(0, 100)
ax.set_ylim(0, 1.02)
ax.set_title('Concentración de los ingresos netos por cliente')
ax.set_xlabel('Clientes, ordenados por ingresos (de mayor a menor)')
ax.set_ylabel('% acumulado de los ingresos netos')
ax.legend(loc='lower right')
fig.tight_layout()
fig.savefig(charts_dir / '07_customer_concentration.png')
plt.show()

sf.close()
print(f'Charts saved to {charts_dir}')
