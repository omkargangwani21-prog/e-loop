import type { ReactNode } from "react";
import type { Hazard, Status } from "../api/types";

export function Spinner({ label = "Loading" }: { label?: string }) {
  return (
    <span className="spinner" role="status" aria-label={label}>
      <span className="spinner__ring" aria-hidden="true" />
    </span>
  );
}

export function Notice({
  tone = "info",
  title,
  children,
  action,
}: {
  tone?: "info" | "warn" | "error";
  title?: string;
  children: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className={`notice notice--${tone}`} role={tone === "error" ? "alert" : "status"}>
      <div className="notice__body">
        {title ? <strong className="notice__title">{title}</strong> : null}
        <span>{children}</span>
      </div>
      {action}
    </div>
  );
}

const STATUS_LABELS: Record<Status, string> = {
  requested: "Requested",
  confirmed: "Confirmed",
  collected: "Collected",
};

export function StatusPill({ status }: { status: Status }) {
  return <span className={`pill pill--${status}`}>{STATUS_LABELS[status]}</span>;
}

const HAZARD_LABELS: Record<Hazard, string> = {
  low: "Low hazard",
  moderate: "Handle with care",
  high: "Hazardous",
};

export function HazardTag({ hazard }: { hazard: Hazard }) {
  return <span className={`tag tag--${hazard}`}>{HAZARD_LABELS[hazard]}</span>;
}

export function Field({
  id,
  label,
  hint,
  error,
  children,
}: {
  id: string;
  label: string;
  hint?: string;
  error?: string | undefined;
  children: ReactNode;
}) {
  return (
    <div className={`field${error ? " field--invalid" : ""}`}>
      <label className="field__label" htmlFor={id}>
        {label}
      </label>
      {children}
      {hint && !error ? (
        <p className="field__hint" id={`${id}-hint`}>
          {hint}
        </p>
      ) : null}
      {error ? (
        <p className="field__error" id={`${id}-error`}>
          {error}
        </p>
      ) : null}
    </div>
  );
}

/** Wires an input to its hint/error text for assistive technology. */
export function describedBy(id: string, hasHint: boolean, error?: string): string | undefined {
  if (error) return `${id}-error`;
  return hasHint ? `${id}-hint` : undefined;
}

export function PageHeading({ title, lead }: { title: string; lead?: string }) {
  return (
    <header className="page-heading">
      <h1>{title}</h1>
      {lead ? <p className="lead">{lead}</p> : null}
    </header>
  );
}
