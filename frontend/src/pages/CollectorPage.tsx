import { useState, type FormEvent } from "react";
import { ApiError, api } from "../api/client";
import { COGNITO_ENABLED, signInWithCognito } from "../api/cognito";
import type { CollectorProfile, Credentials, QueueItem } from "../api/types";
import { Field, HazardTag, Notice, PageHeading, Spinner, StatusPill, describedBy } from "../components/ui";
import { useAsync } from "../hooks/useAsync";
import { formatDateTime, formatPhone, formatWeight } from "../lib/format";

const STORAGE_KEY = "eloop.collector";

function loadSession(): Credentials | null {
  try {
    const raw = window.sessionStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as Credentials) : null;
  } catch {
    return null;
  }
}

function saveSession(credentials: Credentials | null) {
  try {
    if (credentials) window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(credentials));
    else window.sessionStorage.removeItem(STORAGE_KEY);
  } catch {
    // Storage can be blocked (private mode); the session then lasts until the page closes.
  }
}

function SignIn({ onSignedIn }: { onSignedIn: (credentials: Credentials) => void }) {
  const [collectorId, setCollectorId] = useState("");
  const [key, setKey] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const id = collectorId.trim().toLowerCase();
    const secret = COGNITO_ENABLED ? key : key.trim();
    if (!id || !secret) {
      setError(COGNITO_ENABLED ? "Enter your collection point ID and password." : "Enter your collection point ID and access key.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const credentials = { collectorId: id, key: COGNITO_ENABLED ? await signInWithCognito(id, secret) : secret };
      await api.collector.me(credentials);
      onSignedIn(credentials);
    } catch (cause) {
      setError(
        cause instanceof ApiError && cause.status === 401
          ? "Those details don't match. Check the ID and key you were given."
          : cause instanceof Error
            ? cause.message
            : "Sign in failed. Please try again.",
      );
      setBusy(false);
    }
  };

  return (
    <>
      <PageHeading title="Collector sign in" lead="For registered collection points. You'll see the requests assigned to you." />
      <form className="card narrow" onSubmit={submit} noValidate>
        <Field id="collector-id" label="Collection point ID">
          <input
            id="collector-id"
            className="input input--mono"
            autoComplete="username"
            autoCapitalize="none"
            spellCheck={false}
            value={collectorId}
            onChange={(e) => setCollectorId(e.target.value)}
          />
        </Field>
        <Field id="collector-key" label={COGNITO_ENABLED ? "Password" : "Access key"} error={error ?? undefined}>
          <input
            id="collector-key"
            className="input input--mono"
            type="password"
            autoComplete="current-password"
            value={key}
            onChange={(e) => setKey(e.target.value)}
            aria-invalid={Boolean(error)}
            aria-describedby={describedBy("collector-key", false, error ?? undefined)}
          />
        </Field>
        <button type="submit" className="btn btn--primary" disabled={busy}>
          {busy ? (
            <>
              <Spinner label="Signing in" />
              <span>Signing in</span>
            </>
          ) : (
            "Sign in"
          )}
        </button>
      </form>
    </>
  );
}

function QueueCard({
  item,
  credentials,
  onChanged,
}: {
  item: QueueItem;
  credentials: Credentials;
  onChanged: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [weight, setWeight] = useState("");

  const run = async (action: () => Promise<unknown>) => {
    setBusy(true);
    setError(null);
    try {
      await action();
      onChanged();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Something went wrong. Please try again.");
    } finally {
      setBusy(false);
    }
  };

  const collect = (event: FormEvent) => {
    event.preventDefault();
    const kilograms = Number(weight.replace(",", "."));
    if (!Number.isFinite(kilograms) || kilograms <= 0 || kilograms > 200) {
      setError("Enter the weighed amount in kilograms, between 0.001 and 200.");
      return;
    }
    void run(() => api.collector.collect(credentials, item.id, Math.round(kilograms * 1000)));
  };

  const { contact } = item;

  return (
    <li className="card queue-card">
      <div className="queue-card__head">
        <div>
          <code className="inline-code">{item.id}</code>
          <h3 className="queue-card__title">
            {item.quantity} x {item.category_label}
          </h3>
        </div>
        <StatusPill status={item.status} />
      </div>

      <p className="muted">
        {item.area ?? "Area not given"} - {item.distance_km} km away - about {formatWeight(item.est_weight_g)} - requested{" "}
        {formatDateTime(item.created_at)}
      </p>
      <div className="queue-card__handling">
        <HazardTag hazard={item.hazard} />
        <span>{item.handling}</span>
      </div>

      {contact ? (
        <dl className="summary summary--stacked contact">
          <div>
            <dt>Contact</dt>
            <dd>{contact.name}</dd>
          </div>
          <div>
            <dt>Phone</dt>
            <dd>
              <a href={`tel:+91${contact.phone}`}>{formatPhone(contact.phone)}</a>
            </dd>
          </div>
          <div>
            <dt>Address</dt>
            <dd>
              {contact.address}{" "}
              <a
                href={`https://www.google.com/maps/search/?api=1&query=${contact.lat},${contact.lng}`}
                target="_blank"
                rel="noreferrer noopener"
              >
                Open in Maps
              </a>
            </dd>
          </div>
        </dl>
      ) : (
        <p className="muted">Contact details are shown once you accept this pickup.</p>
      )}

      {error ? <Notice tone="error">{error}</Notice> : null}

      {item.status === "requested" ? (
        <div className="actions actions--end">
          <button
            type="button"
            className="btn btn--primary"
            disabled={busy}
            onClick={() => void run(() => api.collector.confirm(credentials, item.id))}
          >
            {busy ? "Accepting..." : "Accept pickup"}
          </button>
        </div>
      ) : null}

      {item.status === "confirmed" ? (
        <form className="collect-form" onSubmit={collect} noValidate>
          <Field id={`weight-${item.id}`} label="Weighed at pickup (kg)">
            <input
              id={`weight-${item.id}`}
              className="input input--narrow"
              inputMode="decimal"
              value={weight}
              onChange={(e) => setWeight(e.target.value)}
              placeholder="0.00"
            />
          </Field>
          <button type="submit" className="btn btn--primary" disabled={busy}>
            {busy ? "Saving..." : "Mark collected"}
          </button>
        </form>
      ) : null}
    </li>
  );
}

function Dashboard({ credentials, onSignOut }: { credentials: Credentials; onSignOut: () => void }) {
  const profile = useAsync<CollectorProfile>(() => api.collector.me(credentials), [credentials]);
  const queue = useAsync((signal) => api.collector.queue(credentials, signal), [credentials]);

  const unauthorised = [profile.error, queue.error].some((e) => e instanceof ApiError && e.status === 401);
  if (unauthorised) {
    return (
      <Notice
        tone="error"
        title="Your session is no longer valid"
        action={
          <button type="button" className="btn btn--secondary btn--small" onClick={onSignOut}>
            Sign in again
          </button>
        }
      >
        The access key was rejected.
      </Notice>
    );
  }

  const pickups = queue.data?.pickups ?? [];

  return (
    <>
      <header className="track-head">
        <div>
          <p className="eyebrow">Signed in</p>
          <h1>{profile.data?.name ?? credentials.collectorId}</h1>
        </div>
        <div className="actions actions--tight">
          <button type="button" className="btn btn--secondary btn--small" onClick={queue.reload} disabled={queue.loading}>
            Refresh
          </button>
          <button type="button" className="btn btn--ghost btn--small" onClick={onSignOut}>
            Sign out
          </button>
        </div>
      </header>

      {queue.error ? <Notice tone="error">{queue.error.message}</Notice> : null}
      {queue.loading && !queue.data ? (
        <div className="center-block">
          <Spinner label="Loading requests" />
        </div>
      ) : null}

      {queue.data && pickups.length === 0 ? (
        <div className="card empty">
          <strong>No open requests</strong>
          <p className="muted">New pickups matched to your collection point will appear here.</p>
        </div>
      ) : null}

      <ul className="queue">
        {pickups.map((item) => (
          <QueueCard key={item.id} item={item} credentials={credentials} onChanged={queue.reload} />
        ))}
      </ul>
    </>
  );
}

export function CollectorPage() {
  const [credentials, setCredentials] = useState<Credentials | null>(loadSession);

  const signIn = (next: Credentials) => {
    saveSession(next);
    setCredentials(next);
  };
  const signOut = () => {
    saveSession(null);
    setCredentials(null);
  };

  return credentials ? <Dashboard credentials={credentials} onSignOut={signOut} /> : <SignIn onSignedIn={signIn} />;
}
