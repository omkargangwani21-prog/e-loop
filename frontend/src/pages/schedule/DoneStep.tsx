import { useState } from "react";
import type { Category, TrackedPickup } from "../../api/types";
import { useFocusOnMount } from "../../hooks/useFocusOnMount";
import { formatInrRange, formatWeight } from "../../lib/format";
import { Link } from "../../lib/router";

export function DoneStep({
  pickup,
  category,
  onReset,
}: {
  pickup: TrackedPickup;
  category: Category;
  onReset: () => void;
}) {
  const heading = useFocusOnMount<HTMLHeadingElement>();
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(pickup.id);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false); // clipboard can be unavailable; the code is selectable on screen
    }
  };

  return (
    <section aria-labelledby="done-heading">
      <h2 id="done-heading" ref={heading} tabIndex={-1} className="step-title">
        Pickup requested
      </h2>
      <p className="muted">Keep this code. It is the only way to look up your pickup.</p>

      <div className="code-card">
        <span className="code-card__label">Tracking code</span>
        <code className="code-card__value">{pickup.id}</code>
        <button type="button" className="btn btn--secondary btn--small" onClick={copy}>
          {copied ? "Copied" : "Copy code"}
        </button>
      </div>

      <dl className="summary">
        <div>
          <dt>Item</dt>
          <dd>
            {pickup.quantity} x {pickup.category_label}
          </dd>
        </div>
        <div>
          <dt>Collection point</dt>
          <dd>{pickup.collector ? pickup.collector.name : "Assigned shortly"}</dd>
        </div>
        <div>
          <dt>Estimated weight</dt>
          <dd>{formatWeight(pickup.est_weight_g)}</dd>
        </div>
        <div>
          <dt>Indicative scrap value</dt>
          <dd>{formatInrRange(category.value_inr_min * pickup.quantity, category.value_inr_max * pickup.quantity)}</dd>
        </div>
      </dl>
      <p className="muted">The collection point confirms the final weight and value at pickup.</p>

      <div className="actions">
        <button type="button" className="btn btn--ghost" onClick={onReset}>
          Schedule another
        </button>
        <Link to={`/track/${pickup.id}`} className="btn btn--primary">
          Track this pickup
        </Link>
      </div>
    </section>
  );
}
