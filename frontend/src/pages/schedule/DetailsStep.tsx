import { useMemo, useState, type ChangeEvent, type FormEvent } from "react";
import type { ApiError } from "../../api/client";
import type { Area } from "../../api/types";
import { Field, Notice, Spinner, describedBy } from "../../components/ui";
import { useFocusOnMount } from "../../hooks/useFocusOnMount";

export interface DetailsValues {
  name: string;
  phone: string;
  address: string;
  area: string | null;
  lat: number;
  lng: number;
}

interface Props {
  areas: Area[];
  submitting: boolean;
  error: ApiError | null;
  onBack: () => void;
  onSubmit: (values: DetailsValues) => void;
}

type Errors = Partial<Record<"name" | "phone" | "address" | "location", string>>;

const PHONE = /^[6-9]\d{9}$/;

export function DetailsStep({ areas, submitting, error, onBack, onSubmit }: Props) {
  const heading = useFocusOnMount<HTMLHeadingElement>();
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [address, setAddress] = useState("");
  const [areaName, setAreaName] = useState("");
  const [device, setDevice] = useState<{ lat: number; lng: number } | null>(null);
  const [locating, setLocating] = useState(false);
  const [locationNote, setLocationNote] = useState<string | null>(null);
  const [errors, setErrors] = useState<Errors>({});

  // Field-level problems reported by the server (it validates again independently).
  const serverErrors = useMemo<Errors>(() => {
    const result: Errors = {};
    for (const issue of error?.details ?? []) {
      if (issue.field === "name" || issue.field === "phone" || issue.field === "address") {
        result[issue.field] = issue.message;
      } else if (issue.field === "lat" || issue.field === "lng") {
        result.location = issue.message;
      }
    }
    return result;
  }, [error]);

  const shown: Errors = { ...serverErrors, ...errors };
  const generalError = error && (error.details.length === 0 || error.status !== 422) ? error.message : null;
  const noCollector = error?.code === "NO_COLLECTOR_IN_RANGE";

  const useDeviceLocation = () => {
    if (!("geolocation" in navigator)) {
      setLocationNote("Location isn't available on this device. Choose your area instead.");
      return;
    }
    setLocating(true);
    setLocationNote(null);
    navigator.geolocation.getCurrentPosition(
      (position) => {
        setDevice({ lat: position.coords.latitude, lng: position.coords.longitude });
        setLocating(false);
      },
      () => {
        setLocating(false);
        setLocationNote("We couldn't get your location. Choose your area instead.");
      },
      { enableHighAccuracy: false, timeout: 10_000 },
    );
  };

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    const found = areas.find((a) => a.name === areaName);
    const next: Errors = {};
    if (name.trim().length < 2) next.name = "Enter your name.";
    if (!PHONE.test(phone)) next.phone = "Enter a 10-digit Indian mobile number.";
    if (address.trim().length < 10) next.address = "Add a fuller address so the collector can find you.";
    if (!device && !found) next.location = "Choose your area or share your location.";
    setErrors(next);
    if (Object.keys(next).length > 0) return;

    const point = device ?? found;
    if (!point) return;
    onSubmit({
      name: name.trim(),
      phone,
      address: address.trim(),
      area: found?.name ?? null,
      lat: point.lat,
      lng: point.lng,
    });
  };

  return (
    <section aria-labelledby="details-heading">
      <h2 id="details-heading" ref={heading} tabIndex={-1} className="step-title">
        Where should we collect it?
      </h2>
      <p className="muted">
        Your contact details are shared with the collection point only after they accept the pickup.
      </p>

      <form onSubmit={handleSubmit} noValidate>
        <Field id="name" label="Full name" error={shown.name}>
          <input
            id="name"
            className="input"
            autoComplete="name"
            value={name}
            onChange={(e: ChangeEvent<HTMLInputElement>) => setName(e.target.value)}
            aria-invalid={Boolean(shown.name)}
            aria-describedby={describedBy("name", false, shown.name)}
          />
        </Field>

        <Field id="phone" label="Mobile number" hint="10 digits. The collector may call to arrange a time." error={shown.phone}>
          <div className="input-group">
            <span className="input-group__prefix" aria-hidden="true">
              +91
            </span>
            <input
              id="phone"
              className="input"
              type="tel"
              inputMode="numeric"
              autoComplete="tel-national"
              maxLength={10}
              value={phone}
              onChange={(e) => setPhone(e.target.value.replace(/\D/g, ""))}
              aria-invalid={Boolean(shown.phone)}
              aria-describedby={describedBy("phone", true, shown.phone)}
            />
          </div>
        </Field>

        <Field id="address" label="Pickup address" hint="House or flat number, street and landmark." error={shown.address}>
          <textarea
            id="address"
            className="input input--area"
            rows={3}
            autoComplete="street-address"
            value={address}
            onChange={(e) => setAddress(e.target.value)}
            aria-invalid={Boolean(shown.address)}
            aria-describedby={describedBy("address", true, shown.address)}
          />
        </Field>

        <Field
          id="area"
          label="Area"
          hint="Used to find the nearest collection point."
          error={shown.location}
        >
          <select
            id="area"
            className="input"
            value={areaName}
            onChange={(e) => setAreaName(e.target.value)}
            aria-invalid={Boolean(shown.location)}
            aria-describedby={describedBy("area", true, shown.location)}
          >
            <option value="">Select your area</option>
            {areas.map((a) => (
              <option key={a.name} value={a.name}>
                {a.name}
              </option>
            ))}
          </select>
        </Field>

        <div className="location-row">
          {device ? (
            <>
              <span className="muted">Using your device location for matching.</span>
              <button type="button" className="link-button" onClick={() => setDevice(null)}>
                Clear
              </button>
            </>
          ) : (
            <button type="button" className="btn btn--secondary btn--small" onClick={useDeviceLocation} disabled={locating}>
              {locating ? "Locating..." : "Use my current location"}
            </button>
          )}
        </div>
        {locationNote ? <p className="field__hint">{locationNote}</p> : null}

        {generalError ? (
          <Notice tone="error" title={noCollector ? "Outside our current coverage" : undefined}>
            {generalError}
          </Notice>
        ) : null}

        <div className="actions">
          <button type="button" className="btn btn--ghost" onClick={onBack} disabled={submitting}>
            Back
          </button>
          <button type="submit" className="btn btn--primary" disabled={submitting}>
            {submitting ? (
              <>
                <Spinner label="Scheduling" />
                <span>Scheduling</span>
              </>
            ) : (
              "Schedule pickup"
            )}
          </button>
        </div>
      </form>
    </section>
  );
}
