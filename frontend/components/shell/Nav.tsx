"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";

export interface NavRoute {
  href: string;
  label: string;
  /** Optional short line under the label — what the page is for. */
  hint?: string;
  /** Which badge count to show, if any. */
  badgeKey?: "cards" | "cells" | "patterns";
}

export interface NavSection {
  section: string;
  items: NavRoute[];
}

interface NavProps {
  sections: NavSection[];
}

type Badges = Partial<Record<"cards" | "cells" | "patterns", number>>;

/**
 * Left-sidebar nav, following the accounting demo's structure: a logo block,
 * titled sections, and live count badges.
 *
 * Two things were quietly broken before and are worth naming, because both
 * were the same fault — this shell's components and its stylesheet drifted
 * apart:
 *
 *   - the active item emitted `nav-item-active` while the stylesheet styles
 *     `.nav-item.active`, so the current page has never been highlighted;
 *   - `.nav-logo`, `.nav-section` and `.nav-badge` were all defined and none
 *     of them were ever rendered.
 */
export default function Nav({ sections }: NavProps) {
  const pathname = usePathname();
  const [badges, setBadges] = useState<Badges>({});
  const [drawerOpen, setDrawerOpen] = useState(false);

  useEffect(() => {
    let active = true;
    apiFetch<Badges>("/api/nav/badges")
      .then((d) => { if (active) setBadges(d); })
      .catch(() => {});          // a nav without counts is fine; a broken nav is not
    return () => { active = false; };
  }, []);

  useEffect(() => { setDrawerOpen(false); }, [pathname]);

  const isActive = (href: string) =>
    pathname === href || (href !== "/" && (pathname?.startsWith(href) ?? false));

  return (
    <>
      <div className="nav-mobile-bar">
        <button className="nav-mobile-hamburger" onClick={() => setDrawerOpen((v) => !v)}
                aria-label={drawerOpen ? "Close menu" : "Open menu"}>
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor"
               strokeWidth="2" strokeLinecap="round"><path d="M3 6h18M3 12h18M3 18h18" /></svg>
        </button>
        <span className="nav-mobile-title">Predictive SQL</span>
      </div>

      {drawerOpen && <div className="nav-overlay" onClick={() => setDrawerOpen(false)} />}

      <nav className={`nav ${drawerOpen ? "open" : ""}`}>
        <div className="nav-logo">
          <div className="nav-logo-mark">
            <div className="nav-logo-icon" aria-hidden="true">
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                <path d="M2.5 12.5V6M6.5 12.5V3M10.5 12.5V8M14 12.5h-13"
                      stroke="#0d1520" strokeWidth="1.8" strokeLinecap="round" />
              </svg>
            </div>
            <span className="nav-logo-text">Predictive SQL</span>
          </div>
          <div className="nav-logo-sub">Every number is one statement</div>
        </div>

        {sections.map((s) => (
          <div key={s.section}>
            <div className="nav-section">{s.section}</div>
            {s.items.map((item) => {
              const count = item.badgeKey ? badges[item.badgeKey] : undefined;
              return (
                <Link key={item.href} href={item.href}
                      className={`nav-item ${isActive(item.href) ? "active" : ""}`}>
                  <span className="nav-item-body">
                    <span className="nav-item-label">{item.label}</span>
                    {item.hint && <span className="nav-item-hint">{item.hint}</span>}
                  </span>
                  {count !== undefined && count > 0 && (
                    <span className="nav-badge">{count.toLocaleString()}</span>
                  )}
                </Link>
              );
            })}
          </div>
        ))}

        <div className="nav-user">
          <a className="nav-foot" href="https://aito.ai/docs/api/sql/guide"
             target="_blank" rel="noreferrer">
            Aito SQL guide ↗
          </a>
        </div>
      </nav>
    </>
  );
}
