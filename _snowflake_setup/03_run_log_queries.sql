/* Run log written by dbt at the end of every invocation
   (on-run-end hook -> macros/log_run_results.sql -> TPCH_ANALYTICS.AUDIT.DBT_RUN_RESULTS). */
USE ROLE TRANSFORMER;
USE WAREHOUSE WH_TRANSFORM;
USE SCHEMA TPCH_ANALYTICS.AUDIT;

-- 1. Summary per run (latest first)
SELECT invocation_id, target_name, command,
       MIN(run_started_at)                         AS run_started_at,
       COUNT(*)                                    AS nodes,
       COUNT_IF(status IN ('success', 'pass'))     AS ok,
       COUNT_IF(status = 'warn')                   AS warnings,
       COUNT_IF(status IN ('error', 'fail'))       AS errors,
       COUNT_IF(status = 'skipped')                AS skipped,
       ROUND(SUM(execution_time_s), 1)             AS total_s
FROM dbt_run_results
GROUP BY ALL
ORDER BY run_started_at DESC
LIMIT 20;

-- 2. Everything that warned or failed in the last 7 days
SELECT run_started_at, target_name, resource_type, node_name, status, failures, message
FROM dbt_run_results
WHERE status IN ('warn', 'fail', 'error')
  AND run_started_at >= DATEADD(day, -7, CURRENT_TIMESTAMP())
ORDER BY run_started_at DESC;

-- 3. Slowest models of the latest run
SELECT node_name, schema_name, execution_time_s, rows_affected
FROM dbt_run_results
WHERE resource_type = 'model'
  AND invocation_id = (SELECT invocation_id FROM dbt_run_results ORDER BY logged_at DESC LIMIT 1)
ORDER BY execution_time_s DESC;

-- 4. Duration trend of the fact table across runs
SELECT run_started_at, target_name, execution_time_s, rows_affected
FROM dbt_run_results
WHERE node_name = 'fct_order_lines'
ORDER BY run_started_at DESC;
