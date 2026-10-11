import { api } from "../api/client";
import { Notice, PageHeading, Spinner } from "../components/ui";
import { useAsync } from "../hooks/useAsync";
import { formatWeight } from "../lib/format";

const count = new Intl.NumberFormat("en-IN");

export function ImpactPage() {
  const { data, error, loading, reload } = useAsync((signal) => api.impact(signal), []);

  return (
    <>
      <PageHeading
        title="Impact"
        lead="Only collections that a collection point has weighed and recorded are counted."
      />

      {loading && !data ? (
        <div className="center-block">
          <Spinner label="Loading impact" />
        </div>
      ) : null}

      {error && !data ? (
        <Notice
          tone="error"
          action={
            <button type="button" className="btn btn--secondary btn--small" onClick={reload}>
              Retry
            </button>
          }
        >
          {error.message}
        </Notice>
      ) : null}

      {data ? (
        <>
          <dl className="stats">
            <div className="stat">
              <dt>Collected</dt>
              <dd>{formatWeight(data.collected_g)}</dd>
            </div>
            <div className="stat">
              <dt>Pickups completed</dt>
              <dd>{count.format(data.pickups_collected)}</dd>
            </div>
            <div className="stat">
              <dt>Requests received</dt>
              <dd>{count.format(data.pickups_total)}</dd>
            </div>
          </dl>

          <section className="card" aria-labelledby="by-category">
            <h2 id="by-category" className="card__title">
              Collected by item type
            </h2>
            {data.by_category.length === 0 ? (
              <p className="muted">Nothing has been collected yet.</p>
            ) : (
              <ul className="bars">
                {data.by_category.map((row) => {
                  const max = data.by_category[0]?.grams ?? 1;
                  return (
                    <li key={row.category} className="bars__row">
                      <span className="bars__label">{row.label}</span>
                      <span className="bars__track" aria-hidden="true">
                        <span className="bars__fill" style={{ width: `${Math.max(2, (row.grams / max) * 100)}%` }} />
                      </span>
                      <span className="bars__value">{formatWeight(row.grams)}</span>
                    </li>
                  );
                })}
              </ul>
            )}
          </section>
        </>
      ) : null}
    </>
  );
}
