import { useEffect, useState, type FormEvent } from "react";
import { ApiError, api } from "../api/client";
import { Progress, Timeline } from "../components/Timeline";
import { Field, Notice, PageHeading, Spinner, StatusPill, describedBy } from "../components/ui";
import { useAsync } from "../hooks/useAsync";
import { PICKUP_CODE_PATTERN, formatDateTime, formatWeight, shortHash } from "../lib/format";
import { Link, useRouter } from "../lib/router";

const POLL_MS = 20_000;

function TrackSearch() {
  const { navigate } = useRouter();
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | undefined>();

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const normalised = code.trim().toUpperCase();
    if (!PICKUP_CODE_PATTERN.test(normalised)) {
      setError("Enter the code exactly as shown, for example EL-7K3Q9M2X.");
      return;
    }
    navigate(`/track/${normalised}`);
  };

  return (
    <>
      <PageHeading title="Track a pickup" lead="Enter the tracking code you received when you scheduled the pickup." />
      <form className="card narrow" onSubmit={submit} noValidate>
        <Field id="code" label="Tracking code" error={error}>
          <input
            id="code"
            className="input input--mono"
            autoComplete="off"
            autoCapitalize="characters"
            spellCheck={false}
            placeholder="EL-XXXXXXXX"
            value={code}
            onChange={(e) => setCode(e.target.value)}
            aria-invalid={Boolean(error)}
            aria-describedby={describedBy("code", false, error)}
          />
        </Field>
        <button type="submit" className="btn btn--primary">
          Find pickup
        </button>
      </form>
    </>
  );
}

function TrackDetail({ id }: { id: string }) {
  const { data, error, loading, reload } = useAsync((signal) => api.getPickup(id, signal), [id]);

  // Keep the page live while the pickup is still in progress.
  const status = data?.status;
  useEffect(() => {
    if (!status || status === "collected") return;
    const timer = window.setInterval(reload, POLL_MS);
    return () => window.clearInterval(timer);
  }, [status, reload]);

  if (!data && loading) {
    return (
      <div className="center-block">
        <Spinner label="Loading pickup" />
      </div>
    );
  }

  if (!data) {
    const notFound = error instanceof ApiError && error.status === 404;
    return (
      <>
        <PageHeading title={notFound ? "No pickup found" : "Couldn't load this pickup"} />
        <Notice
          tone={notFound ? "warn" : "error"}
          action={
            notFound ? (
              <Link to="/track" className="btn btn--secondary btn--small">
                Try another code
              </Link>
            ) : (
              <button type="button" className="btn btn--secondary btn--small" onClick={reload}>
                Retry
              </button>
            )
          }
        >
          {notFound ? `We couldn't find a pickup with the code ${id}. Check it and try again.` : error?.message ?? "Please try again."}
        </Notice>
      </>
    );
  }

  return (
    <>
      <header className="track-head">
        <div>
          <p className="eyebrow">Tracking code</p>
          <h1 className="mono-title">{data.id}</h1>
        </div>
        <StatusPill status={data.status} />
      </header>

      <div className="grid-2">
        <section className="card" aria-labelledby="progress-heading">
          <h2 id="progress-heading" className="card__title">
            Progress
          </h2>
          <Progress status={data.status} />
          <Timeline events={data.events} />
        </section>

        <div className="stack">
          <section className="card" aria-labelledby="details-heading">
            <h2 id="details-heading" className="card__title">
              Details
            </h2>
            <dl className="summary summary--stacked">
              <div>
                <dt>Item</dt>
                <dd>
                  {data.quantity} x {data.category_label}
                </dd>
              </div>
              <div>
                <dt>Collection point</dt>
                <dd>{data.collector?.name ?? "Assigned shortly"}</dd>
              </div>
              <div>
                <dt>{data.collected_weight_g !== null ? "Weighed at pickup" : "Estimated weight"}</dt>
                <dd>{formatWeight(data.collected_weight_g ?? data.est_weight_g)}</dd>
              </div>
              <div>
                <dt>Requested</dt>
                <dd>{formatDateTime(data.created_at)}</dd>
              </div>
            </dl>
          </section>

          <section className="card" aria-labelledby="integrity-heading">
            <h2 id="integrity-heading" className="card__title">
              Record integrity
            </h2>
            {data.chain_verified ? (
              <p>
                Verified. Each of the {data.events.length} entries is linked to the one before it, so any later change
                would be detected.
                {data.head_hash ? (
                  <>
                    {" "}
                    Latest fingerprint <code className="inline-code">{shortHash(data.head_hash)}</code>.
                  </>
                ) : null}
              </p>
            ) : (
              <Notice tone="error" title="Integrity check failed">
                This record's history does not verify. Please contact the collection point.
              </Notice>
            )}
          </section>
        </div>
      </div>
    </>
  );
}

export function TrackPage({ id }: { id?: string }) {
  return id ? <TrackDetail id={id} /> : <TrackSearch />;
}
