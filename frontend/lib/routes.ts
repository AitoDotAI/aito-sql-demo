import type { NavSection } from "@/components/shell/Nav";

/** The nav is grouped by what each page is FOR, not by page type — read the
 *  answer, check the working, then ask your own question. That ordering is the
 *  demo's argument, so the sidebar may as well carry it. */
export const NAV_SECTIONS: NavSection[] = [
  {
    section: "The answer",
    items: [
      { href: "/", label: "The six cards", hint: "root cause and lever, per question",
        badgeKey: "cards" },
    ],
  },
  {
    section: "Check the working",
    items: [
      { href: "/map", label: "The map behind them", hint: "every field × every slice",
        badgeKey: "cells" },
      { href: "/patterns", label: "Patterns", hint: "combinations nobody proposed",
        badgeKey: "patterns" },
    ],
  },
  {
    section: "Ask your own",
    items: [
      { href: "/explore", label: "Explorer", hint: "narrow endlessly, click anything" },
    ],
  },
];
