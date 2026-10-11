import type { Category, Prediction } from "../../api/types";
import { HazardTag, Notice } from "../../components/ui";
import { useFocusOnMount } from "../../hooks/useFocusOnMount";
import { formatInrRange, formatWeight } from "../../lib/format";

interface Props {
  categories: Category[];
  predictions: Prediction[];
  notice: string | null;
  category: string | null;
  quantity: number;
  onCategory: (key: string) => void;
  onQuantity: (quantity: number) => void;
  onBack: () => void;
  onNext: () => void;
}

export function ItemStep({
  categories,
  predictions,
  notice,
  category,
  quantity,
  onCategory,
  onQuantity,
  onBack,
  onNext,
}: Props) {
  const heading = useFocusOnMount<HTMLHeadingElement>();
  const top = predictions[0];
  const suggested = top ? categories.find((c) => c.key === top.category) : undefined;
  const selected = categories.find((c) => c.key === category);

  return (
    <section aria-labelledby="item-heading">
      <h2 id="item-heading" ref={heading} tabIndex={-1} className="step-title">
        What are you handing over?
      </h2>

      {suggested && top ? (
        <Notice tone="info" title={`Looks like: ${suggested.label}`}>
          {Math.round(top.confidence * 100)}% match from your photo. Change it below if that's wrong.
        </Notice>
      ) : notice ? (
        <Notice tone="warn">{notice}</Notice>
      ) : null}

      <fieldset className="options">
        <legend className="visually-hidden">Item type</legend>
        {categories.map((item) => (
          <label key={item.key} className={item.key === category ? "option is-selected" : "option"}>
            <input
              type="radio"
              name="category"
              value={item.key}
              checked={item.key === category}
              onChange={() => onCategory(item.key)}
            />
            <span className="option__label">{item.label}</span>
            <span className="option__meta">about {formatWeight(item.typical_weight_g)}</span>
          </label>
        ))}
      </fieldset>

      {selected ? (
        <aside className="detail-panel" aria-live="polite">
          <div className="detail-panel__row">
            <HazardTag hazard={selected.hazard} />
            <span className="muted">
              Indicative scrap value {formatInrRange(selected.value_inr_min * quantity, selected.value_inr_max * quantity)}
            </span>
          </div>
          <p>{selected.handling}</p>
          <p className="muted">Recoverable materials: {selected.materials.join(", ")}.</p>
        </aside>
      ) : null}

      <div className="field field--inline">
        <label className="field__label" htmlFor="quantity">
          How many of this item?
        </label>
        <input
          id="quantity"
          className="input input--narrow"
          type="number"
          inputMode="numeric"
          min={1}
          max={20}
          value={quantity}
          onChange={(event) => {
            const next = Math.round(Number(event.target.value));
            if (Number.isFinite(next)) onQuantity(Math.min(20, Math.max(1, next)));
          }}
        />
      </div>

      <div className="actions">
        <button type="button" className="btn btn--ghost" onClick={onBack}>
          Back
        </button>
        <button type="button" className="btn btn--primary" disabled={!category} onClick={onNext}>
          Continue
        </button>
      </div>
    </section>
  );
}
