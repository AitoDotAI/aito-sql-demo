-- Federation: a third-party engine querying Aito with no Aito-specific code.
--
-- This is the demo's strongest single claim and the one hardest to fake, so it
-- is a script you run rather than a screenshot. DuckDB's postgres extension
-- speaks the Postgres wire protocol; Aito answers it. Nothing here knows it is
-- talking to a predictive database.
--
--   ./do federate
--
-- Two things worth watching for.
--
-- 1. THE NUMBERS MATCH THE DASHBOARD EXACTLY. hot + passive comes back 45.2%
--    over n=431, which is what /explore computes and what the M1 card shows.
--    Two engines, two query paths, same answer.
--
-- 2. DUCKDB ANSWERS A QUESTION AITO'S OWN SQL CANNOT. Aito's GROUP BY takes a
--    single column (see sql-reference #limitations). The last query here groups
--    by TWO and adds a HAVING. So federation is not only "your tools still
--    work" — it is "your tools fill the gaps in ours", which is a much better
--    argument and an honest one about the subset's limits.

INSTALL postgres;
LOAD postgres;

-- The password is the Aito API key; `user` is ignored. On a multi-database
-- server `dbname` is the DATABASE, not the environment.
ATTACH 'host=${AITO_HOST} port=5432 dbname=${AITO_DB} user=aito password=${AITO_KEY}'
    AS aito (TYPE POSTGRES, READ_ONLY);

.print
.print === 1. DuckDB can see Aito's tables ===
SELECT table_name
  FROM duckdb_tables()
 WHERE database_name = 'aito'
 ORDER BY table_name
 LIMIT 8;

.print
.print === 2. An ordinary SELECT, executed by Aito ===
SELECT climate, cooling, count(*) AS n
  FROM aito.analysis
 GROUP BY climate, cooling
 ORDER BY n DESC
 LIMIT 5;

.print
.print === 3. The one Aito's own SQL cannot do: GROUP BY two columns, with HAVING ===
.print ===    DuckDB pulls the rows and aggregates locally. Same data, more SQL. ===
SELECT climate,
       cooling,
       round(100.0 * avg(CASE WHEN churned = 'true' THEN 1 ELSE 0 END), 1) AS churn_pct,
       count(*) AS n
  FROM aito.analysis
 GROUP BY climate, cooling
HAVING count(*) > 100
 ORDER BY churn_pct DESC
 LIMIT 5;

.print
.print === 4. And a join across two Aito tables, planned by DuckDB ===
SELECT s.climate, p.grade, count(*) AS installs
  FROM aito.installs i
  JOIN aito.sites s    ON i.site = s.site_id
  JOIN aito.products p ON i.product = p.product_id
 GROUP BY s.climate, p.grade
 ORDER BY installs DESC
 LIMIT 5;
