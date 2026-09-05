-- aito-sql-demo — the schema.
--
-- Written in docs/design.md as the SQL we WANTED to write, at a time when
-- neither REFERENCES nor analysed `text` existed. Both shipped (2026-08), so
-- this file is executed rather than aspirational.
--
--   REFERENCES  declares an Aito LINK — what makes dotted paths and INNER JOIN
--               work, and what lets predict/relate/recommend reason across
--               tables. Every card depends on them.
--   text        is ANALYSED (tokenised, @@-searchable, per-token relate).
--               varchar is CATEGORICAL and is what predict() learns to output.
--               Getting it backwards is silent at write time and disappointing
--               at query time.
--
-- NOTE ON COMMENT PLACEMENT — not a style choice. On build 6f2700e2 the SQL
-- parser does not strip comments INSIDE a statement: a `-- note` after a column
-- definition fails with "expected a column name but got '-'", and a /* block */
-- fails likewise. Only comments BETWEEN statements survive, because psql strips
-- those before sending. Hence every note here sits above its CREATE TABLE.
-- Filed as a bug; when it is fixed these can move back inline.
--
-- Load order follows the links: a REFERENCES target must exist first.

-- products
--   name             analysed: searchable
--   grade            consumer | pro | industrial
--   cooling          passive | active | liquid     ← M1
CREATE TABLE products (
  product_id      varchar PRIMARY KEY,
  name            text NOT NULL,
  family          varchar NOT NULL,
  grade           varchar NOT NULL,
  cooling         varchar NOT NULL,
  load_rating_kg  integer NOT NULL,
  duty_cycle_pct  integer NOT NULL,
  ip_rating       varchar NOT NULL,
  price           numeric NOT NULL,
  launched        date    NOT NULL
);

-- customers
--   industry         construction | food | logistics | mining
CREATE TABLE customers (
  customer_id varchar PRIMARY KEY,
  name        varchar NOT NULL,
  industry    varchar NOT NULL,
  size_band   varchar NOT NULL,
  country     varchar NOT NULL
);

-- sites
--   climate          temperate | hot | arctic       ← M1
--   shift_pattern    1-shift | 2-shift | 3-shift    ← M2
CREATE TABLE sites (
  site_id       varchar PRIMARY KEY,
  customer      varchar NOT NULL REFERENCES customers(customer_id),
  climate       varchar NOT NULL,
  dust_level    varchar NOT NULL,
  shift_pattern varchar NOT NULL,
  altitude_m    integer NOT NULL
);

-- campaigns
--   channel          paid-social | search | trade-fair | distributor-ME | referral   ← M3
CREATE TABLE campaigns (
  campaign_id   varchar PRIMARY KEY,
  channel       varchar NOT NULL,
  region        varchar NOT NULL,
  message_angle varchar NOT NULL,
  spend         numeric NOT NULL
);

-- sessions
--   customer         NULL until identified
CREATE TABLE sessions (
  session_id   varchar PRIMARY KEY,
  campaign     varchar NOT NULL REFERENCES campaigns(campaign_id),
  customer     varchar          REFERENCES customers(customer_id),
  landing_page varchar NOT NULL,
  device       varchar NOT NULL,
  ts           date    NOT NULL
);

-- orders
--   session          attribution
CREATE TABLE orders (
  order_id varchar PRIMARY KEY,
  customer varchar NOT NULL REFERENCES customers(customer_id),
  session  varchar          REFERENCES sessions(session_id),
  product  varchar NOT NULL REFERENCES products(product_id),
  qty      integer NOT NULL,
  value    numeric NOT NULL,
  ts       date    NOT NULL
);

-- installs
--   commissioning    self | guided | on-site        ← lever
--   service_plan     none | standard | premium      ← lever
--   support_tier     pooled | dedicated             ← lever (M4)
CREATE TABLE installs (
  install_id    varchar PRIMARY KEY,
  order_p       varchar NOT NULL REFERENCES orders(order_id),
  customer      varchar NOT NULL REFERENCES customers(customer_id),
  product       varchar NOT NULL REFERENCES products(product_id),
  site          varchar NOT NULL REFERENCES sites(site_id),
  session       varchar          REFERENCES sessions(session_id),
  commissioning varchar NOT NULL,
  service_plan  varchar NOT NULL,
  support_tier  varchar NOT NULL,
  ts            date    NOT NULL
);

-- tickets
--   category         overheat | wear | electrical | user-error
--   body             analysed: "unit shuts down midday, ambient 44C"
--   first_response_h ← M4
CREATE TABLE tickets (
  ticket_id        varchar PRIMARY KEY,
  install          varchar NOT NULL REFERENCES installs(install_id),
  opened           date    NOT NULL,
  category         varchar NOT NULL,
  body             text    NOT NULL,
  first_response_h integer NOT NULL,
  resolved         boolean NOT NULL
);

-- feedback
--   score            1..5
--   body             analysed
CREATE TABLE feedback (
  feedback_id varchar PRIMARY KEY,
  install     varchar NOT NULL REFERENCES installs(install_id),
  score       integer NOT NULL,
  body        text    NOT NULL,
  ts          date    NOT NULL
);

-- events
--   type             ad_click|page_view|spec_download|quote_request|purchase|
--   (table)          install|fault_report|ticket_open|feedback_given|reorder|lapse
--   body             analysed
CREATE TABLE events (
  event_id varchar PRIMARY KEY,
  customer varchar REFERENCES customers(customer_id),
  session  varchar REFERENCES sessions(session_id),
  install  varchar REFERENCES installs(install_id),
  type     varchar NOT NULL,
  page     varchar,
  body     text,
  value    numeric,
  ts       date NOT NULL
);

-- actions
--   lever            sku_quoted | service_plan | commissioning | support_tier | outreach
CREATE TABLE actions (
  action_id varchar PRIMARY KEY,
  customer  varchar NOT NULL REFERENCES customers(customer_id),
  install   varchar          REFERENCES installs(install_id),
  lever     varchar NOT NULL,
  choice    varchar NOT NULL,
  ts        date    NOT NULL
);

-- reorders
--   period           '2026-Q1' …
--   reordered        ← the label
CREATE TABLE reorders (
  reorder_id varchar PRIMARY KEY,
  install    varchar NOT NULL REFERENCES installs(install_id),
  period     varchar NOT NULL,
  reordered  boolean NOT NULL
);

-- analysis
--   THE FLAT TABLE THE DASHBOARD ACTUALLY QUERIES. One row per install, every
--   explanatory field flattened onto it by traversing the links above.
--
--   It is here because of measured limits, not preference. relate() takes no
--   filter (its `to` is the target proposition, not a slice), so conditioning
--   must come from the table being queried; the only way to narrow a table is a
--   VIEW; and a view can neither bake a link-path WHERE (silently empty --
--   td-20260831214438282862) nor project a link-path column. There is also no
--   CREATE TABLE AS SELECT and no INSERT ... SELECT, so nothing derives this
--   server-side. src/generate.py builds it and it loads as a 13th CSV.
--
--   text vs varchar still matters here: `churned` is varchar so predict() can
--   output it, and the two label spellings are both present because a card
--   reads better asking about the outcome it names.
CREATE TABLE analysis (
  install_id          varchar PRIMARY KEY,
  industry            varchar NOT NULL,
  size_band           varchar NOT NULL,
  country             varchar NOT NULL,
  climate             varchar NOT NULL,
  dust_level          varchar NOT NULL,
  shift_pattern       varchar NOT NULL,
  family              varchar NOT NULL,
  grade               varchar NOT NULL,
  cooling             varchar NOT NULL,
  ip_rating           varchar NOT NULL,
  duty_cycle_pct      integer NOT NULL,
  channel             varchar NOT NULL,
  region              varchar NOT NULL,
  message_angle       varchar NOT NULL,
  landing_page        varchar NOT NULL,
  device              varchar NOT NULL,
  commissioning       varchar NOT NULL,
  service_plan        varchar NOT NULL,
  support_tier        varchar NOT NULL,
  had_thermal_fault   varchar NOT NULL,
  slow_first_response varchar NOT NULL,
  ticket_count        integer NOT NULL,
  feedback_score      integer,
  order_value         numeric NOT NULL,
  installed_on        date NOT NULL,
  churned             varchar NOT NULL,
  reordered           varchar NOT NULL
);
