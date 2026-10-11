import type { ReactNode } from "react";
import { Link, useRouter } from "../lib/router";

const NAV = [
  { to: "/", label: "Schedule pickup", match: (p: string) => p === "/" },
  { to: "/track", label: "Track", match: (p: string) => p.startsWith("/track") },
  { to: "/impact", label: "Impact", match: (p: string) => p === "/impact" },
] as const;

function Mark() {
  return (
    <svg className="brand__mark" viewBox="0 0 24 24" width="22" height="22" aria-hidden="true">
      <path d="M12 4a8 8 0 1 0 8 8" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" />
      <circle cx="18.5" cy="5.5" r="2.4" fill="currentColor" />
    </svg>
  );
}

export function Layout({ children }: { children: ReactNode }) {
  const { path } = useRouter();

  return (
    <div className="shell">
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <header className="site-header">
        <div className="container site-header__inner">
          <Link to="/" className="brand" aria-label="E-Loop home">
            <Mark />
            <span>E-Loop</span>
          </Link>
          <nav className="nav" aria-label="Primary">
            {NAV.map((item) => (
              <Link key={item.to} to={item.to} aria-current={item.match(path) ? "page" : undefined}>
                {item.label}
              </Link>
            ))}
            <Link
              to="/collector"
              className="nav__quiet"
              aria-current={path.startsWith("/collector") ? "page" : undefined}
            >
              Collector sign in
            </Link>
          </nav>
        </div>
      </header>
      <main id="main" className="container main" tabIndex={-1}>
        {children}
      </main>
      <footer className="site-footer">
        <div className="container">
          <span>E-Loop &middot; Built on AWS for Environmental Hacks</span>
          <span>Demo build: collection points and scrap values are placeholders.</span>
        </div>
      </footer>
    </div>
  );
}
