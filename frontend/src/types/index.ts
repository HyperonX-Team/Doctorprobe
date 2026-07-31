// Type definitions mirroring the backend Pydantic schemas exactly.
// Keep these in sync with backend/app/schemas/*.py.

export type Sex = 'male' | 'female' | 'other';
export type ActivityLevel = 'sedentary' | 'light' | 'moderate' | 'active' | 'athlete';
export type RiskState = 'low' | 'medium' | 'high';
export type BiomarkerState = 'low' | 'normal' | 'high';

/** Backend: app/schemas/user.py -> UserResponse */
export interface User {
  id: string;
  age: number;
  sex: Sex;
  height_cm: number;
  weight_kg: number;
  activity_level: ActivityLevel;
  share_data: boolean;
  token_balance: number;
  device_id: string;
  created_at: string;
}

/** Backend: app/schemas/user.py -> UserUpdate */
export type UserUpdate = Partial<
  Pick<
    User,
    | 'age'
    | 'sex'
    | 'height_cm'
    | 'weight_kg'
    | 'activity_level'
    | 'share_data'
    | 'device_id'
  >
>;

/** Backend: app/schemas/user.py -> UserCreate (minus id/created_at) */
export type UserCreate = Omit<User, 'id' | 'token_balance' | 'created_at'>;

/** Backend: app/schemas/checkup.py -> Biomarker */
export interface Biomarker {
  name: string;
  value: number;
  unit: string;
  ref_low: number | null;
  ref_high: number | null;
  state: BiomarkerState;
  message: string;
}

/** Backend: app/schemas/checkup.py -> CheckupSummary */
export interface CheckupSummary {
  id: string;
  user_id: string;
  summary: string;
  overall_risk: RiskState;
  created_at: string;
  is_shared: boolean;
}

/** Backend: app/schemas/checkup.py -> CheckupResponse */
export interface Checkup extends CheckupSummary {
  text_summary: string;
  biomarkers: Biomarker[];
}

/** Backend: app/schemas/checkup.py -> CheckupCreate */
export interface CheckupCreate {
  user_id: string;
}

/** Backend: app/schemas/checkup.py -> CheckupCreateResponse */
export interface CheckupCreated {
  id: string;
  user_id: string;
  summary: string;
  overall_risk: RiskState;
  created_at: string;
  is_shared: boolean;
}

/** Backend: app/schemas/checkup.py -> ShareResponse */
export interface ShareResponse {
  checkup_id: string;
  tokens_awarded: number;
  new_balance: number;
  is_shared: boolean;
}

/** Backend: app/schemas/device.py -> DeviceReadingResponse */
export interface DeviceReading {
  id: string;
  device_id: string;
  rgb_r: number;
  rgb_g: number;
  rgb_b: number;
  temperature_c: number;
  humidity_pct: number;
  created_at: string;
}

/** Backend: app/schemas/device.py -> DeviceStatus */
export interface DeviceStatus {
  connected: boolean;
  last_seen: string | null;
}
