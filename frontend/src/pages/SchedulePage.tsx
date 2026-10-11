import { useState } from "react";
import { ApiError, api } from "../api/client";
import type { TrackedPickup } from "../api/types";
import { Notice, Spinner } from "../components/ui";
import { Link } from "../lib/router";
import { useMeta } from "../hooks/useMeta";
import { DetailsStep, type DetailsValues } from "./schedule/DetailsStep";
import { DoneStep } from "./schedule/DoneStep";
import { ItemStep } from "./schedule/ItemStep";
import { NO_PHOTO, PhotoStep, type PhotoResult } from "./schedule/PhotoStep";
import { Stepper } from "./schedule/Stepper";

type Step = "photo" | "item" | "details" | "done";
const STEP_ORDER: Step[] = ["photo", "item", "details", "done"];

const HOW_IT_WORKS = [
  { title: "Photograph it", body: "A photo helps us suggest what the item is and how to handle it." },
  { title: "We match a collector", body: "The nearest collection point that accepts your item is assigned automatically." },
  { title: "Collected and recorded", body: "The collector weighs the item and the record is sealed so it can be verified later." },
];

export function SchedulePage() {
  const meta = useMeta();
  const [step, setStep] = useState<Step>("photo");
  const [photo, setPhoto] = useState<PhotoResult>(NO_PHOTO);
  const [category, setCategory] = useState<string | null>(null);
  const [quantity, setQuantity] = useState(1);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<ApiError | null>(null);
  const [result, setResult] = useState<TrackedPickup | null>(null);

  const reset = () => {
    setStep("photo");
    setPhoto(NO_PHOTO);
    setCategory(null);
    setQuantity(1);
    setSubmitError(null);
    setResult(null);
  };

  const handlePhoto = (next: PhotoResult) => {
    setPhoto(next);
    setCategory(next.predictions[0]?.category ?? null);
    setStep("item");
  };

  const submit = async (details: DetailsValues) => {
    if (!category) return;
    const top = photo.predictions[0];
    const accepted = top !== undefined && top.category === category;

    setSubmitting(true);
    setSubmitError(null);
    try {
      const created = await api.createPickup({
        category,
        quantity,
        image_key: photo.imageKey,
        classified_by: accepted ? photo.source : "manual",
        confidence: accepted ? top.confidence : null,
        ...details,
      });
      setResult(created);
      setStep("done");
    } catch (cause) {
      setSubmitError(cause instanceof ApiError ? cause : new ApiError(0, "UNKNOWN", "Something went wrong. Please try again."));
    } finally {
      setSubmitting(false);
    }
  };

  const data = meta.data;
  const selectedCategory = data?.categories.find((c) => c.key === category);

  return (
    <>
      <section className="hero" aria-labelledby="hero-title">
        <div className="hero__copy">
          <span className="badge">Waste &amp; Energy &middot; e-waste</span>
          <h1 id="hero-title">
            Give old electronics <span className="gradient-text">a second loop.</span>
          </h1>
          <p className="lead">
            Snap a photo, get matched to the nearest collection point, and receive a verifiable record of exactly what
            was collected and weighed.
          </p>
          <div className="hero__cta">
            <a className="btn btn--primary" href="#schedule">
              Schedule a pickup
            </a>
            <Link to="/track" className="btn btn--secondary">
              Track a pickup
            </Link>
          </div>
          <ul className="chips" aria-label="Highlights">
            <li>Auto-matched collector</li>
            <li>Hash-sealed record</li>
            <li>Data auto-deletes</li>
          </ul>
        </div>

        <aside className="hero__card" aria-label="Sample collection record">
          <header className="receipt__head">
            <div>
              <p className="eyebrow">Sample collection record</p>
              <p className="receipt__id">EL-7K2M9QXA</p>
            </div>
            <span className="receipt__badge">
              <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true">
                <path d="M3.5 8.4l3 3 6-6.4" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              Verified
            </span>
          </header>

          <dl className="receipt__facts">
            <div>
              <dt>Item</dt>
              <dd>Smartphone &times; 1</dd>
            </div>
            <div>
              <dt>Weighed</dt>
              <dd>0.4 kg</dd>
            </div>
            <div>
              <dt>Collection point</dt>
              <dd>Dwarka</dd>
            </div>
          </dl>

          <ol className="mini-timeline">
            <li>
              <span className="mini-timeline__dot" aria-hidden="true" />
              <div>
                <div className="mini-timeline__row">
                  <strong>Requested</strong>
                  <time>10:02</time>
                </div>
                <code className="mini-timeline__hash">a41f&hellip;9c02</code>
              </div>
            </li>
            <li>
              <span className="mini-timeline__dot" aria-hidden="true" />
              <div>
                <div className="mini-timeline__row">
                  <strong>Confirmed</strong>
                  <time>10:09</time>
                </div>
                <code className="mini-timeline__hash">7be3&hellip;d815</code>
              </div>
            </li>
            <li>
              <span className="mini-timeline__dot mini-timeline__dot--done" aria-hidden="true" />
              <div>
                <div className="mini-timeline__row">
                  <strong>Collected</strong>
                  <time>11:40</time>
                </div>
                <code className="mini-timeline__hash">c09d&hellip;42ae</code>
              </div>
            </li>
          </ol>

          <p className="receipt__foot">
            <span className="receipt__lock" aria-hidden="true" />
            Chain verified. Every step is sealed with the one before it.
          </p>
        </aside>
      </section>

      <div className="split" id="schedule">
        <div className="intro">
          <p className="eyebrow">How it works</p>
          <ol className="how">
            {HOW_IT_WORKS.map((item, index) => (
              <li key={item.title}>
                <span className="how__index" aria-hidden="true">
                  {index + 1}
                </span>
                <div>
                  <strong>{item.title}</strong>
                  <p className="muted">{item.body}</p>
                </div>
              </li>
            ))}
          </ol>
        </div>

      <div className="card wizard">
        {meta.loading && !data ? (
          <div className="center-block">
            <Spinner label="Loading" />
          </div>
        ) : null}

        {meta.error && !data ? (
          <Notice
            tone="error"
            title="Couldn't load the form"
            action={
              <button type="button" className="btn btn--secondary btn--small" onClick={meta.reload}>
                Retry
              </button>
            }
          >
            {meta.error.message}
          </Notice>
        ) : null}

        {data ? (
          <>
            <Stepper steps={["Photo", "Item", "Details"]} current={STEP_ORDER.indexOf(step)} />
            {step === "photo" ? <PhotoStep maxBytes={data.limits.max_upload_bytes} onComplete={handlePhoto} /> : null}
            {step === "item" ? (
              <ItemStep
                categories={data.categories}
                predictions={photo.predictions}
                notice={photo.notice}
                category={category}
                quantity={quantity}
                onCategory={setCategory}
                onQuantity={setQuantity}
                onBack={() => setStep("photo")}
                onNext={() => setStep("details")}
              />
            ) : null}
            {step === "details" ? (
              <DetailsStep
                areas={data.areas}
                submitting={submitting}
                error={submitError}
                onBack={() => setStep("item")}
                onSubmit={submit}
              />
            ) : null}
            {step === "done" && result && selectedCategory ? (
              <DoneStep pickup={result} category={selectedCategory} onReset={reset} />
            ) : null}
          </>
        ) : null}
      </div>
      </div>
    </>
  );
}
