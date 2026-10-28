import sys
sys.path.append(r'C:\Users\William Ordiales\OneDrive\Documentos\propelling_datachellenge\_modules')
from snowflake_client import SnowflakeClient
# credentials are read (encrypted) from _credentials/ - see _modules/cripto.py

sf = SnowflakeClient(target="dev", layer="audit")
sf.connect()

result = sf.query("""
    select node_name, target_name, min(run_started_at) as dt_start,
           count(*) as total,
           count_if(status = 'warn') as warn,
           count_if(status in ('error', 'fail')) as error,
           round(sum(execution_time_s), 1) as seconds
    from audit.dbt_run_results
    group by all
    having warn > 0 or error > 0
    order by dt_start desc
""")
df = sf.to_pandas(result)
df
sf.close()

df