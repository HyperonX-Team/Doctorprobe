// Type definitions mirroring the backend Pydantic schemas exactly.
// Keep these in sync with backend/app/schemas/*.py.

export type Sex = 'male' | 'female' | 'other';
export type ActivityLevel = 'sedentary' | 'light' | 'moderate' | 'active' | 'athlete';
export type RiskState = 'low' | 'medium' | 'high';
export type BiomarkerState = 'low' | 'normal' | 'high';

/** Backend: app/schemas/user.py -> UserResponse */
export interface User {
  id: string;
  email: string | null;
  age: number;
  sex: Sex;
  height_cm: number;
  weight_kg: number;
  activity_level: ActivityLevel;
  share_data: boolean;
  token_balance: number;
  device_id: string;
  reference_ranges: Record<string, ReferenceRange> | null;
  created_at: string;
}

/** Per-marker personalized reference bounds (backend analyzer defaults if null). */
export interface ReferenceRange {
  low: number;
  high: number;
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
    | 'reference_ranges'
  >
>;

/** Backend: app/schemas/user.py -> UserCreate (minus id/created_at) */
export type UserCreate = Omit<User, 'id' | 'token_balance' | 'created_at'>;

/** Backend: app/schemas/auth.py -> RegisterRequest */
export interface RegisterInput {
  email: string;
  password: string;
  age: number;
  sex: Sex;
  height_cm: number;
  weight_kg: number;
  activity_level: ActivityLevel;
  share_data: boolean;
  device_id: string;
}

/** Backend: app/schemas/auth.py -> LoginRequest */
export interface LoginInput {
  email: string;
  password: string;
}

/** Backend: app/schemas/auth.py -> ChangePasswordRequest */
export interface ChangePasswordInput {
  current_password: string;
  new_password: string;
}

/** Backend: app/schemas/auth.py -> AuthResponse */
export interface AuthResponse {
  token: string;
  user: User;
}

/** Backend: app/schemas/checkup.py -> MeasurementQuality */
export interface MeasurementQuality {
  grade: 'good' | 'fair' | 'poor';
  reasons: string[];
  recommended_action: string | null;
}

/** Backend: app/schemas/checkup.py -> Biomarker */
export interface Biomarker {
  key: string;
  name: string;
  value: number;
  unit: string;
  ref_low: number | null;
  ref_high: number | null;
  state: BiomarkerState;
  message: string;
  confidence?: number;
}

/** Backend: app/schemas/checkup.py -> AnalysisInfo */
export interface AnalysisInfo {
  method: string;
  prior_source: string;
  n_measurements: number;
  condition_number?: number | null;
  rank?: number | null;
  reconstruction_residual?: number | null;
  reference_source?: string | null;
}

/** Backend: app/schemas/checkup.py -> CheckupSummary */
export interface CheckupSummary {
  id: string;
  user_id: string;
  summary: string;
  overall_risk: RiskState;
  quality_grade: string | null;
  created_at: string;
  is_shared: boolean;
}

/** Backend: app/schemas/checkup.py -> CheckupResponse */
export interface Checkup extends CheckupSummary {
  text_summary: string;
  biomarkers: Biomarker[];
  analysis?: AnalysisInfo;
  quality?: MeasurementQuality;
  note?: string | null;
}

/** Backend: app/schemas/checkup.py -> CheckupCreateResponse */
export interface CheckupCreated {
  id: string;
  user_id: string;
  summary: string;
  overall_risk: RiskState;
  quality_grade: string | null;
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

/** Backend: app/schemas/device.py -> DeviceBaselineResponse */
export interface DeviceBaseline {
  id: string;
  device_id: string;
  rgb_r: number;
  rgb_g: number;
  rgb_b: number;
  created_at: string;
  updated_at: string;
}

/** Backend: app/services/calibration_stats.py -> build_calibration_stats payload */
export interface AnalyteCalibrationStats {
  name: string;
  unit: string;
  count: number;
  min_concentration: number | null;
  max_concentration: number | null;
  envelope_min: number;
  envelope_max: number;
  enough: boolean;
  last_sample_at: string | null;
  model_source: string | null;
  model_metrics: Record<string, number>;
}

export interface CalibrationStats {
  total_samples: number;
  min_real_samples: number;
  analytes: Record<string, AnalyteCalibrationStats>;
  model: {
    present: boolean;
    model_name: string | null;
    model_version: string | null;
    trained_at: string | null;
  };
}

/** Backend: app/schemas/community.py -> CommunityInsightsResponse */
export interface CommunityMarkerInsight {
  key: string;
  name: string;
  unit: string;
  user_latest: number | null;
  user_state: string | null;
  cohort_count: number;
  cohort_mean: number | null;
  cohort_std: number | null;
  cohort_p10: number | null;
  cohort_p50: number | null;
  cohort_p90: number | null;
  user_percentile: number | null;
  ref_low: number | null;
  ref_high: number | null;
}

export interface CommunityInsights {
  cohort_checkups: number;
  cohort_users: number;
  min_cohort: number;
  similar_profile: { sex: string; age_band: string; activity_level: string } | null;
  similar_profile_count: number;
  markers: Record<string, CommunityMarkerInsight>;
}

/** Backend: app/schemas/notification.py -> NotificationResponse */
export interface AppNotification {
  id: string;
  kind: string;
  message: string;
  created_at: string;
  read_at: string | null;
}

export interface NotificationsResponse {
  unread_count: number;
  items: AppNotification[];
}

/** Backend: app/services/trends.py -> build_trends payload */
export interface TrendPoint {
  date: string;
  value: number;
  state: BiomarkerState;
  confidence: number | null;
  name: string;
  unit: string;
}

export interface TrendAlert {
  type: string;
  severity: 'info' | 'warning';
  message: string;
}

export interface MarkerStats {
  count: number;
  mean: number;
  std: number;
  min: number;
  max: number;
  latest: number;
}

export interface MarkerTrend {
  key: string;
  name: string;
  unit: string;
  ref_low: number | null;
  ref_high: number | null;
  points: TrendPoint[];
  stats: MarkerStats | null;
  alerts: TrendAlert[];
}

export interface TrendsResponse {
  window_days: number;
  checkup_count: number;
  alert_count: number;
  markers: Record<string, MarkerTrend>;
}
