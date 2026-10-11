import { useEffect, useRef, useState, type ChangeEvent } from "react";
import { api, uploadImage } from "../../api/client";
import type { ClassifiedBy, Prediction } from "../../api/types";
import { Notice, Spinner } from "../../components/ui";
import { useFocusOnMount } from "../../hooks/useFocusOnMount";
import { prepareImage } from "../../lib/image";

export interface PhotoResult {
  imageKey: string | null;
  predictions: Prediction[];
  source: ClassifiedBy;
  /** Shown on the next step when the photo could not be used to suggest an item. */
  notice: string | null;
}

export const NO_PHOTO: PhotoResult = { imageKey: null, predictions: [], source: "manual", notice: null };

function CameraIcon() {
  return (
    <svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true">
      <path d="M4 8.5A1.5 1.5 0 0 1 5.5 7h2.2l1.1-1.6A1.5 1.5 0 0 1 10 4.8h4a1.5 1.5 0 0 1 1.2.6L16.3 7h2.2A1.5 1.5 0 0 1 20 8.5v8a1.5 1.5 0 0 1-1.5 1.5h-13A1.5 1.5 0 0 1 4 16.5v-8Z" />
      <circle cx="12" cy="12.5" r="3.2" />
    </svg>
  );
}

export function PhotoStep({ maxBytes, onComplete }: { maxBytes: number; onComplete: (result: PhotoResult) => void }) {
  const heading = useFocusOnMount<HTMLHeadingElement>();
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!file) {
      setPreviewUrl(null);
      return;
    }
    const url = URL.createObjectURL(file);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  const onPick = (event: ChangeEvent<HTMLInputElement>) => {
    setError(null);
    setFile(event.target.files?.[0] ?? null);
  };

  const analyse = async () => {
    if (!file) return;
    setBusy(true);
    setError(null);

    let image: Blob;
    try {
      image = await prepareImage(file, maxBytes);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The photo could not be processed.");
      setBusy(false);
      return;
    }

    // From here on, nothing blocks the user: any failure degrades to choosing the item by hand.
    let imageKey: string | null = null;
    try {
      const ticket = await api.startUpload();
      await uploadImage(ticket, image);
      imageKey = ticket.key;
      const result = await api.classify(ticket.key);
      onComplete({
        imageKey,
        predictions: result.predictions,
        source: result.source,
        notice: result.predictions.length === 0 ? "We couldn't identify the item automatically. Choose the closest match." : null,
      });
    } catch {
      onComplete({
        imageKey,
        predictions: [],
        source: "manual",
        notice: "We couldn't analyse the photo, so please choose the item yourself.",
      });
    }
  };

  return (
    <section aria-labelledby="photo-heading">
      <h2 id="photo-heading" ref={heading} tabIndex={-1} className="step-title">
        Photograph the item
      </h2>
      <p className="muted">One clear photo is enough. We use it to suggest what the item is, and you confirm.</p>

      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        className="visually-hidden"
        onChange={onPick}
        aria-label="Choose a photo"
        tabIndex={-1}
      />
      <button
        type="button"
        className={previewUrl ? "dropzone has-image" : "dropzone"}
        onClick={() => inputRef.current?.click()}
        disabled={busy}
      >
        {previewUrl ? (
          <img src={previewUrl} alt="The photo you selected" />
        ) : (
          <>
            <CameraIcon />
            <span className="dropzone__title">Take or choose a photo</span>
            <span className="dropzone__hint">JPEG or PNG</span>
          </>
        )}
      </button>
      {previewUrl && !busy ? (
        <button type="button" className="link-button" onClick={() => inputRef.current?.click()}>
          Choose a different photo
        </button>
      ) : null}

      {error ? <Notice tone="error">{error}</Notice> : null}

      <div className="actions">
        <button type="button" className="btn btn--ghost" disabled={busy} onClick={() => onComplete(NO_PHOTO)}>
          Continue without a photo
        </button>
        <button type="button" className="btn btn--primary" disabled={!file || busy} onClick={analyse}>
          {busy ? (
            <>
              <Spinner label="Analysing photo" />
              <span>Analysing photo</span>
            </>
          ) : (
            "Continue"
          )}
        </button>
      </div>
    </section>
  );
}
