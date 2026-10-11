const number = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 1 });
const rupee = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 });
const dateTime = new Intl.DateTimeFormat("en-IN", { dateStyle: "medium", timeStyle: "short" });

export function formatWeight(grams: number): string {
  return grams < 1000 ? `${number.format(grams)} g` : `${number.format(grams / 1000)} kg`;
}

export function formatInrRange(min: number, max: number): string {
  return `${rupee.format(min)} to ${rupee.format(max)}`;
}

export function formatDateTime(iso: string): string {
  return dateTime.format(new Date(iso));
}

export function shortHash(hash: string): string {
  return hash.slice(0, 10);
}

export function formatPhone(phone: string): string {
  return phone.length === 10 ? `+91 ${phone.slice(0, 5)} ${phone.slice(5)}` : phone;
}

const EVENT_LABELS: Record<string, string> = {
  requested: "Pickup requested",
  confirmed: "Confirmed by collection point",
  collected: "Collected and weighed",
};

export function eventLabel(type: string): string {
  return EVENT_LABELS[type] ?? type;
}

export const PICKUP_CODE_PATTERN = /^EL-[0-9A-HJKMNP-TV-Z]{8}$/;
