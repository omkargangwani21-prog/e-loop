export type Hazard = "low" | "moderate" | "high";
export type Status = "requested" | "confirmed" | "collected";
export type ClassifiedBy = "rekognition" | "bedrock" | "manual";

export interface Category {
  key: string;
  label: string;
  hazard: Hazard;
  typical_weight_g: number;
  value_inr_min: number;
  value_inr_max: number;
  materials: string[];
  handling: string;
}

export interface Area {
  name: string;
  lat: number;
  lng: number;
}

export interface Meta {
  categories: Category[];
  areas: Area[];
  limits: { max_upload_bytes: number };
}

export interface UploadTicket {
  url: string;
  fields: Record<string, string>;
  key: string;
}

export interface Prediction {
  category: string;
  confidence: number;
}

export interface ClassifyResult {
  source: ClassifiedBy;
  predictions: Prediction[];
}

export interface PickupDraft {
  category: string;
  quantity: number;
  image_key: string | null;
  classified_by: ClassifiedBy;
  confidence: number | null;
  name: string;
  phone: string;
  address: string;
  lat: number;
  lng: number;
  area: string | null;
}

export interface TimelineEvent {
  seq: number;
  type: string;
  at: string;
  actor: string;
  hash: string;
}

export interface TrackedPickup {
  id: string;
  status: Status;
  category: string;
  category_label: string;
  quantity: number;
  area: string | null;
  collector: { name: string; area: string } | null;
  created_at: string;
  updated_at: string;
  est_weight_g: number;
  collected_weight_g: number | null;
  chain_verified: boolean;
  head_hash: string | null;
  events: TimelineEvent[];
}

export interface Contact {
  name: string;
  phone: string;
  address: string;
  lat: number;
  lng: number;
}

export interface QueueItem {
  id: string;
  status: Status;
  category: string;
  category_label: string;
  quantity: number;
  area: string | null;
  distance_km: number;
  est_weight_g: number;
  hazard: Hazard;
  handling: string;
  created_at: string;
  collected_weight_g: number | null;
  contact: Contact | null;
}

export interface Impact {
  pickups_total: number;
  pickups_collected: number;
  collected_g: number;
  by_category: { category: string; label: string; grams: number }[];
}

export interface CollectorProfile {
  id: string;
  name: string;
  area: string;
}

export interface Credentials {
  collectorId: string;
  key: string;
}

export interface FieldIssue {
  field: string;
  message: string;
}
