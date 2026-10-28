/* =============================================================================
   Snowflake setup for the TPC-H Medallion project
   Run once, top to bottom, in a Snowsight SQL worksheet logged in as the
   user that created the trial account (it has ACCOUNTADMIN).

   Filled in for this account:
     Snowsight user : WILLIAMGARCIA
     RSA_PUBLIC_KEY : public key from scripts/generate_keypair.ps1
                      (public part only; the private .p8 never leaves the laptop)
   Use the arrow next to Run > Run All.
   ============================================================================= */

-- 1. Roles --------------------------------------------------------------------
--    TRANSFORMER : used by dbt (dev, CI and prod). Owns the project database.
--    REPORTER    : read-only access to GOLD, for BI tools / analysts.
USE ROLE SECURITYADMIN;

CREATE ROLE IF NOT EXISTS TRANSFORMER COMMENT = 'dbt transformations';
CREATE ROLE IF NOT EXISTS REPORTER    COMMENT = 'Read-only consumer of the GOLD layer';

-- Standard hierarchy: custom roles roll up to SYSADMIN
GRANT ROLE TRANSFORMER TO ROLE SYSADMIN;
GRANT ROLE REPORTER    TO ROLE SYSADMIN;

-- Your own user can switch to both roles in Snowsight
GRANT ROLE TRANSFORMER TO USER WILLIAMGARCIA;
GRANT ROLE REPORTER    TO USER WILLIAMGARCIA;

-- 2. Compute ------------------------------------------------------------------
--    Separate warehouses for transformation and consumption: BI queries never
--    compete with dbt runs, and cost is visible per workload.
USE ROLE SYSADMIN;

CREATE WAREHOUSE IF NOT EXISTS WH_TRANSFORM
    WAREHOUSE_SIZE = XSMALL AUTO_SUSPEND = 60 AUTO_RESUME = TRUE
    INITIALLY_SUSPENDED = TRUE COMMENT = 'dbt runs';

CREATE WAREHOUSE IF NOT EXISTS WH_REPORTING
    WAREHOUSE_SIZE = XSMALL AUTO_SUSPEND = 60 AUTO_RESUME = TRUE
    INITIALLY_SUSPENDED = TRUE COMMENT = 'BI / ad-hoc queries on GOLD';

GRANT USAGE ON WAREHOUSE WH_TRANSFORM TO ROLE TRANSFORMER;
GRANT USAGE ON WAREHOUSE WH_REPORTING TO ROLE REPORTER;

-- 3. Database & schemas -------------------------------------------------------
CREATE DATABASE IF NOT EXISTS TPCH_ANALYTICS COMMENT = 'TPC-H Medallion project';
GRANT OWNERSHIP ON DATABASE TPCH_ANALYTICS TO ROLE TRANSFORMER COPY CURRENT GRANTS;

USE ROLE TRANSFORMER;
CREATE SCHEMA IF NOT EXISTS TPCH_ANALYTICS.BRONZE COMMENT = 'Raw landing, source as-is';
CREATE SCHEMA IF NOT EXISTS TPCH_ANALYTICS.SILVER COMMENT = 'Cleansed and conformed';
CREATE SCHEMA IF NOT EXISTS TPCH_ANALYTICS.GOLD   COMMENT = 'Star schema for consumption';

-- REPORTER only sees GOLD (Bronze/Silver are internal layers)
GRANT USAGE ON DATABASE TPCH_ANALYTICS          TO ROLE REPORTER;
GRANT USAGE ON SCHEMA   TPCH_ANALYTICS.GOLD     TO ROLE REPORTER;
GRANT SELECT ON FUTURE TABLES IN SCHEMA TPCH_ANALYTICS.GOLD TO ROLE REPORTER;
GRANT SELECT ON FUTURE VIEWS  IN SCHEMA TPCH_ANALYTICS.GOLD TO ROLE REPORTER;

-- 4. Source data access -------------------------------------------------------
USE ROLE ACCOUNTADMIN;
-- On some new accounts the sample database is not mounted yet. If the next
-- statement fails with "does not exist", run this first:
--   CREATE DATABASE SNOWFLAKE_SAMPLE_DATA FROM SHARE SFC_SAMPLES.SAMPLE_DATA;
GRANT IMPORTED PRIVILEGES ON DATABASE SNOWFLAKE_SAMPLE_DATA TO ROLE TRANSFORMER;

-- 5. Service user for dbt (key-pair auth, no password) ------------------------
USE ROLE SECURITYADMIN;
CREATE USER IF NOT EXISTS DBT_USER
    TYPE = SERVICE
    DEFAULT_ROLE = TRANSFORMER
    DEFAULT_WAREHOUSE = WH_TRANSFORM
    RSA_PUBLIC_KEY = 'MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAvJzhqmXmiRiUgitUTybA8lI3erCpByzGN/CafM/OkRcWWXM6ZbUU6RzHaTlBSg2wJxDvUCfgbkntsG3TsAIqLPJqBh+gZ9WAdGUkvDT0F97scFs/ODz3ExC3MtuWnY1BjmC4ZU9IU5A6JQdnPa+xoLo5kcsrNvNIKiE0RmlqHnbOf+uIzfxfOo/M98N7a9h9Ew0zhF2Pr+bSkVMeHx+HzDWPH7coU6F25FTwM4o5a+PYAaYBaQ/wpjfrZcUU+G/wEPvGfqiJdTSxw7kabbb7nXBvbT4jgnMaJw7qqCPf13ky/a8FyHT2g/x+7AVycaq1KHzAvhx0v0QyyFGqNnvI8QIDAQAB'
    COMMENT = 'dbt Core (local, CI and CD)';
GRANT ROLE TRANSFORMER TO USER DBT_USER;

-- 6. Cost guardrail -----------------------------------------------------------
USE ROLE ACCOUNTADMIN;
CREATE RESOURCE MONITOR IF NOT EXISTS RM_TPCH_PROJECT
    WITH CREDIT_QUOTA = 30 FREQUENCY = MONTHLY START_TIMESTAMP = IMMEDIATELY
    TRIGGERS ON 80 PERCENT DO NOTIFY
             ON 100 PERCENT DO SUSPEND;
ALTER WAREHOUSE WH_TRANSFORM SET RESOURCE_MONITOR = RM_TPCH_PROJECT;
ALTER WAREHOUSE WH_REPORTING SET RESOURCE_MONITOR = RM_TPCH_PROJECT;

-- 7. Smoke test ---------------------------------------------------------------
USE ROLE TRANSFORMER;
USE WAREHOUSE WH_TRANSFORM;
SELECT COUNT(*) AS lineitem_rows FROM SNOWFLAKE_SAMPLE_DATA.TPCH_SF1.LINEITEM;  -- ~6,001,215

-- Value for SNOWFLAKE_ACCOUNT in scripts/set_env.ps1
SELECT CURRENT_ORGANIZATION_NAME() || '-' || CURRENT_ACCOUNT_NAME() AS snowflake_account;
