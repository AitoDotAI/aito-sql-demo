"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";

/** Connection details for an engineer who wants to run the queries themselves.
 *
 *  The demo's claim is "it is just SQL over the Postgres wire protocol", and
 *  the only convincing form of that claim is a connection string the reader can
 *  paste into their own psql. Everything else is us saying so.
 *
 *  The key only appears when the deployment has published a read-only one
 *  (AITO_SQL_READONLY_KEY). Otherwise the string ships with a placeholder —
 *  a credential should be published by a person deciding to, not by a component
 *  rendering. */
interface Connect {
  host: string; port: number; database: string; user: string;
  key: string; key_published: boolean; psql: string; try: string;
}

function Copy({ text, label }: { text: string; label: string }) {
  const [done, setDone] = useState(false);
  return (
    <button
      className="cx-copy"
      onClick={() => {
        navigator.clipboard?.writeText(text).then(
          () => { setDone(true); setTimeout(() => setDone(false), 1600); },
          () => {},
        );
      }}
      aria-label={`Copy ${label}`}
    >
      {done ? "copied" : "copy"}
    </button>
  );
}

export default function ConnectBox() {
  const [c, setC] = useState<Connect | null>(null);

  useEffect(() => {
    apiFetch<Connect>("/api/connect").then(setC).catch(() => setC(null));
  }, []);

  if (!c) return null;

  return (
    <section className="cx">
      <header className="cx-head">
        <h3>Connect to it yourself</h3>
        <p>
          This is a Postgres wire-protocol endpoint. Every statement on this site can be run from
          any Postgres client — psql, DBeaver, DuckDB, your ORM — with no Aito-specific driver.
        </p>
      </header>

      <div className="cx-grid">
        <div><span className="cx-k">host</span><span className="cx-v">{c.host}</span></div>
        <div><span className="cx-k">port</span><span className="cx-v">{c.port}</span></div>
        <div><span className="cx-k">database</span><span className="cx-v">{c.database}</span></div>
        <div><span className="cx-k">user</span><span className="cx-v">{c.user}</span></div>
      </div>

      <div className="cx-cmd">
        <code>{c.psql}</code>
        <Copy text={c.psql} label="the psql command" />
      </div>

      {!c.key_published && (
        <p className="cx-note">
          The read-only key is not published on this page. Ask for one, or create a database of your
          own from the <a href="https://console.aito.ai/">console</a> — the schema and the generator
          that fills it are both in the repo.
        </p>
      )}

      <div className="cx-try">
        <span className="cx-k">then try</span>
        <code>{c.try}</code>
        <Copy text={c.try} label="the example query" />
      </div>
    </section>
  );
}
