import type { Status, TimelineEvent } from "../api/types";
import { eventLabel, formatDateTime, shortHash } from "../lib/format";

const STAGES: { status: Status; label: string }[] = [
  { status: "requested", label: "Requested" },
  { status: "confirmed", label: "Confirmed" },
  { status: "collected", label: "Collected" },
];

export function Progress({ status }: { status: Status }) {
  const current = STAGES.findIndex((stage) => stage.status === status);
  return (
    <ol className="progress" aria-label="Pickup progress">
      {STAGES.map((stage, index) => (
        <li
          key={stage.status}
          className={index <= current ? "progress__step is-done" : "progress__step"}
          aria-current={index === current ? "step" : undefined}
        >
          <span className="progress__dot" aria-hidden="true" />
          <span>{stage.label}</span>
        </li>
      ))}
    </ol>
  );
}

export function Timeline({ events }: { events: TimelineEvent[] }) {
  return (
    <ol className="timeline">
      {events.map((event) => (
        <li key={event.seq} className="timeline__item">
          <div className="timeline__head">
            <span className="timeline__title">{eventLabel(event.type)}</span>
            <time dateTime={event.at}>{formatDateTime(event.at)}</time>
          </div>
          <code className="timeline__hash" title={event.hash}>
            {shortHash(event.hash)}
          </code>
        </li>
      ))}
    </ol>
  );
}
