import type { NavRoute } from "@/components/shell/Nav";

/** One entry per top-level page. Shared by every page so the sidebar cannot
 *  drift between them. */
export const ROUTES: NavRoute[] = [
  { href: "/", label: "The six cards", icon: "◧" },
  { href: "/map", label: "The map behind them", icon: "▦" },
  { href: "/explore", label: "Explorer", icon: "◈" },
  { href: "/patterns", label: "Patterns", icon: "❖" },
];
