// Settings — account management: profile, personalized reference ranges,
// device detail, data sharing, export-before-delete, password change and
// account deletion. All calls run as the authenticated user derived from
// the session token.

import { useCallback, useEffect, useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import { useUser } from '../hooks/useUser';
import { useToast } from '../components/ui/Toast';
import ConfirmDialog from '../components/ui/ConfirmDialog';
import DeviceStatus from '../components/ui/DeviceStatus';
import { useDeviceStatus } from '../hooks/useDeviceStatus';
import { getErrorMessage } from '../utils/errors';
import type { ActivityLevel, ReferenceRange, Sex } from '../types';

// Analyzer defaults shown when the user has no personalized ranges yet.
const DEFAULT_RANGES: Record<string, ReferenceRange> = {
  glucose: { low: 0.5, high: 7.0 },
  crp: { low: 0.02, high: 1.5 },
  cortisol: { low: 0.1, high: 0.6 },
  ph: { low: 6.5, high: 7.4 },
  siga: { low: 5.0, high: 25.0 },
};

const RANGE_LABELS: Record<string, string> = {
  glucose: 'Salivary Glucose (mg/dL)',
  crp: 'Salivary CRP (ng/mL)',
  cortisol: 'Salivary Cortisol (µg/dL)',
  ph: 'Salivary pH',
  siga: 'Secretory IgA (mg/dL)',
};

const ACTIVITY_OPTIONS: { value: ActivityLevel; label: string }[] = [
  { value: 'sedentary', label: 'Mostly desk-bound' },
  { value: 'light', label: 'Light exercise' },
  { value: 'moderate', label: 'Regular exercise' },
  { value: 'active', label: 'Very active' },
  { value: 'athlete', label: 'Athlete' },
];

const inputClass =
  'w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-100 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100';

export default function Settings() {
  const { user, refreshUser, logout } = useUser();
  const toast = useToast();
  const navigate = useNavigate();

  // Profile fields (editable — the backend PUT /me has always supported them).
  const [age, setAge] = useState('');
  const [sex, setSex] = useState<Sex>('female');
  const [heightCm, setHeightCm] = useState('');
  const [weightKg, setWeightKg] = useState('');
  const [activityLevel, setActivityLevel] = useState<ActivityLevel>('moderate');

  const [deviceId, setDeviceId] = useState('');
  const [shareData, setShareData] = useState(false);
  const [ranges, setRanges] = useState<Record<string, ReferenceRange>>({});
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [changing, setChanging] = useState(false);
  const [passwordError, setPasswordError] = useState<string | null>(null);

  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [exporting, setExporting] = useState(false);

  const [deviceDetail, setDeviceDetail] = useState<{
    latest: {
      rgb_r: number;
      rgb_g: number;
      rgb_b: number;
      temperature_c: number;
      humidity_pct: number;
      created_at: string;
    } | null;
    baseline: {
      rgb_r: number;
      rgb_g: number;
      rgb_b: number;
      updated_at: string;
    } | null;
    error: string | null;
  }>({ latest: null, baseline: null, error: null });

  const deviceStatus = useDeviceStatus(deviceId || user?.device_id);

  // Sync the form from the profile when the *account* changes. Keying on
  // the user id (not the object identity) keeps in-progress edits intact
  // when refreshUser() returns a fresh profile object after a save.
  const userId = user?.id;
  useEffect(() => {
    if (!user || !userId) {
      return;
    }
    setAge(String(user.age));
    setSex(user.sex);
    setHeightCm(String(user.height_cm));
    setWeightKg(String(user.weight_kg));
    setActivityLevel(user.activity_level);
    setDeviceId(user.device_id);
    setShareData(user.share_data);
    setRanges(user.reference_ranges ?? {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userId]);

  const loadDeviceDetail = useCallback(async () => {
    const id = deviceId.trim() || user?.device_id;
    if (!id) {
      return;
    }
    try {
      const [latest, baseline] = await Promise.allSettled([
        api.getLatestReading(id),
        api.getDeviceBaseline(id),
      ]);
      setDeviceDetail({
        latest: latest.status === 'fulfilled' ? latest.value : null,
        baseline: baseline.status === 'fulfilled' ? baseline.value : null,
        error: null,
      });
    } catch (err) {
      setDeviceDetail((current) => ({
        ...current,
        error: getErrorMessage(err),
      }));
    }
  }, [deviceId, user?.device_id]);

  useEffect(() => {
    void loadDeviceDetail();
  }, [loadDeviceDetail]);

  const handleSave = async (event: FormEvent) => {
    event.preventDefault();
    if (!user || !deviceId.trim()) {
      setSaveError('Device ID cannot be empty');
      return;
    }
    const ageNum = Number(age);
    const heightNum = Number(heightCm);
    const weightNum = Number(weightKg);
    if (!ageNum || ageNum < 1 || ageNum > 120) {
      setSaveError('Age must be between 1 and 120');
      return;
    }
    if (!heightNum || heightNum < 50 || heightNum > 250) {
      setSaveError('Height must be between 50 and 250 cm');
      return;
    }
    if (!weightNum || weightNum < 2 || weightNum > 500) {
      setSaveError('Weight must be between 2 and 500 kg');
      return;
    }

    setSaving(true);
    setSaveError(null);
    try {
      await api.updateMe({
        device_id: deviceId.trim(),
        share_data: shareData,
        age: ageNum,
        sex,
        height_cm: heightNum,
        weight_kg: weightNum,
        activity_level: activityLevel,
        reference_ranges: Object.keys(ranges).length > 0 ? ranges : null,
      });
      await refreshUser();
      toast.show('Settings saved', 'success');
    } catch (err) {
      setSaveError(getErrorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  const handleExportData = async () => {
    setExporting(true);
    try {
      const blob = await api.exportMe();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = `doctordrobe-data-${user?.id}.json`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
      toast.show('Your data has been exported', 'success');
    } catch (err) {
      toast.show(getErrorMessage(err), 'error');
    } finally {
      setExporting(false);
    }
  };

  const handleChangePassword = async (event: FormEvent) => {
    event.preventDefault();
    if (newPassword.length < 8) {
      setPasswordError('New password must be at least 8 characters');
      return;
    }
    setChanging(true);
    setPasswordError(null);
    try {
      await api.changePassword({
        current_password: currentPassword,
        new_password: newPassword,
      });
      setCurrentPassword('');
      setNewPassword('');
      toast.show('Password changed — other sessions were signed out', 'success');
    } catch (err) {
      setPasswordError(getErrorMessage(err));
    } finally {
      setChanging(false);
    }
  };

  const handleDeleteAccount = async () => {
    if (!user) {
      return;
    }
    setDeleting(true);
    try {
      await api.deleteMe();
      logout();
      toast.show('Account deleted', 'success');
      navigate('/welcome');
    } catch (err) {
      toast.show(getErrorMessage(err), 'error');
    } finally {
      setDeleting(false);
    }
  };

  if (!user) {
    return null;
  }

  const card =
    'rounded-xl border border-slate-200 bg-white p-6 dark:border-slate-700 dark:bg-slate-900';

  return (
    <div className="mx-auto max-w-2xl space-y-6 animate-fade-in">
      <div>
        <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Settings</h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Manage your account, profile, privacy and device.
        </p>
      </div>

      <div className={card}>
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
          Account
        </p>
        <dl className="mt-3 space-y-2 text-sm">
          <div className="flex items-center justify-between gap-3">
            <dt className="text-slate-500 dark:text-slate-400">Email</dt>
            <dd
              className="font-medium text-slate-800 dark:text-slate-100"
              data-testid="settings-email"
            >
              {user.email ?? '—'}
            </dd>
          </div>
          <div className="flex items-center justify-between gap-3">
            <dt className="text-slate-500 dark:text-slate-400">Account id</dt>
            <dd
              className="font-mono text-xs text-slate-700 dark:text-slate-300"
              data-testid="settings-user-id"
            >
              {user.id}
            </dd>
          </div>
          <div className="flex items-center justify-between gap-3">
            <dt className="text-slate-500 dark:text-slate-400">Token balance</dt>
            <dd className="font-semibold text-slate-800 dark:text-slate-100">
              {user.token_balance}
            </dd>
          </div>
        </dl>
      </div>

      <form onSubmit={handleSave} className={`${card} space-y-5`}>
        <div>
          <p className="text-sm font-semibold text-slate-800 dark:text-slate-100">
            Profile &amp; device
          </p>
          <p className="mt-1 text-xs text-slate-400">
            Your profile tunes the biomarker analysis. Changes apply to new checkups.
          </p>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label
              htmlFor="settings-age"
              className="mb-1 block text-xs font-semibold text-slate-600 dark:text-slate-300"
            >
              Age
            </label>
            <input
              id="settings-age"
              type="number"
              min={1}
              max={120}
              value={age}
              onChange={(e) => setAge(e.target.value)}
              className={inputClass}
              data-testid="settings-age"
            />
          </div>
          <div>
            <label
              htmlFor="settings-sex"
              className="mb-1 block text-xs font-semibold text-slate-600 dark:text-slate-300"
            >
              Sex
            </label>
            <select
              id="settings-sex"
              value={sex}
              onChange={(e) => setSex(e.target.value as Sex)}
              className={inputClass}
              data-testid="settings-sex"
            >
              <option value="female">Female</option>
              <option value="male">Male</option>
              <option value="other">Other</option>
            </select>
          </div>
          <div>
            <label
              htmlFor="settings-height"
              className="mb-1 block text-xs font-semibold text-slate-600 dark:text-slate-300"
            >
              Height (cm)
            </label>
            <input
              id="settings-height"
              type="number"
              min={50}
              max={250}
              step="0.1"
              value={heightCm}
              onChange={(e) => setHeightCm(e.target.value)}
              className={inputClass}
              data-testid="settings-height"
            />
          </div>
          <div>
            <label
              htmlFor="settings-weight"
              className="mb-1 block text-xs font-semibold text-slate-600 dark:text-slate-300"
            >
              Weight (kg)
            </label>
            <input
              id="settings-weight"
              type="number"
              min={2}
              max={500}
              step="0.1"
              value={weightKg}
              onChange={(e) => setWeightKg(e.target.value)}
              className={inputClass}
              data-testid="settings-weight"
            />
          </div>
          <div className="sm:col-span-2">
            <label
              htmlFor="settings-activity"
              className="mb-1 block text-xs font-semibold text-slate-600 dark:text-slate-300"
            >
              Activity level
            </label>
            <select
              id="settings-activity"
              value={activityLevel}
              onChange={(e) => setActivityLevel(e.target.value as ActivityLevel)}
              className={inputClass}
              data-testid="settings-activity"
            >
              {ACTIVITY_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>
          <div className="sm:col-span-2">
            <label
              htmlFor="device-id"
              className="mb-1 block text-xs font-semibold text-slate-600 dark:text-slate-300"
            >
              Device ID
            </label>
            <input
              id="device-id"
              value={deviceId}
              onChange={(e) => setDeviceId(e.target.value)}
              className={inputClass}
              maxLength={64}
              data-testid="settings-device-id"
            />
            <p className="mt-1 text-xs text-slate-400">
              Must match the DEVICE_ID configured in your ESP32 firmware.
            </p>
          </div>
        </div>

        <label className="flex items-start gap-3">
          <input
            type="checkbox"
            checked={shareData}
            onChange={(e) => setShareData(e.target.checked)}
            className="mt-0.5 h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-300"
            data-testid="settings-share-data"
          />
          <span>
            <span className="block text-sm font-semibold text-slate-700 dark:text-slate-200">
              Share checkup data with the community
            </span>
            <span className="block text-xs text-slate-400">
              Earn 5 tokens per shared checkup. Sharing is always opt-in per checkup on
              the report page.
            </span>
          </span>
        </label>

        {saveError && (
          <p
            role="alert"
            className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700 dark:bg-rose-950 dark:text-rose-300"
          >
            {saveError}
          </p>
        )}

        <button
          type="submit"
          disabled={saving}
          data-testid="settings-save"
          className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-50"
        >
          {saving ? 'Saving…' : 'Save settings'}
        </button>
      </form>

      <div className={card}>
        <p className="text-sm font-semibold text-slate-800 dark:text-slate-100">
          Personalized reference ranges
        </p>
        <p className="mt-1 text-xs text-slate-400">
          Override the default ranges per marker. “Normal” is classified against these
          bounds in new reports. Leave a marker untouched to keep the default.
        </p>
        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          {Object.entries(RANGE_LABELS).map(([key, label]) => {
            const range = ranges[key] ?? DEFAULT_RANGES[key];
            return (
              <div
                key={key}
                className="rounded-lg border border-slate-200 p-3 dark:border-slate-700"
                data-testid={`settings-range-${key}`}
              >
                <p className="text-xs font-semibold text-slate-600 dark:text-slate-300">
                  {label}
                </p>
                <div className="mt-2 flex items-center gap-2">
                  <input
                    type="number"
                    step="any"
                    value={range.low}
                    aria-label={`${label} lower bound`}
                    onChange={(e) =>
                      setRanges((current) => ({
                        ...current,
                        [key]: { ...range, low: Number(e.target.value) },
                      }))
                    }
                    className={inputClass}
                    data-testid={`settings-range-${key}-low`}
                  />
                  <span className="text-xs text-slate-400">–</span>
                  <input
                    type="number"
                    step="any"
                    value={range.high}
                    aria-label={`${label} upper bound`}
                    onChange={(e) =>
                      setRanges((current) => ({
                        ...current,
                        [key]: { ...range, high: Number(e.target.value) },
                      }))
                    }
                    className={inputClass}
                    data-testid={`settings-range-${key}-high`}
                  />
                </div>
              </div>
            );
          })}
        </div>
        <button
          type="button"
          onClick={() => setRanges({})}
          className="mt-4 rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-semibold text-slate-600 hover:bg-slate-50 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-800"
          data-testid="settings-ranges-reset"
        >
          Reset all to defaults
        </button>
        <p className="mt-2 text-xs text-slate-400">
          Don't forget to press “Save settings” — ranges are stored with your profile.
        </p>
      </div>

      <div className={card}>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <p className="text-sm font-semibold text-slate-800 dark:text-slate-100">
              Device
            </p>
            <p className="mt-1 text-xs text-slate-400">
              Connection status and last reported reading.
            </p>
          </div>
          <button
            type="button"
            onClick={() => void loadDeviceDetail()}
            className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-semibold text-slate-600 hover:bg-slate-50 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-800"
            data-testid="settings-device-refresh"
          >
            Refresh
          </button>
        </div>
        <div className="mt-3">
          <DeviceStatus
            status={deviceStatus.status}
            loading={deviceStatus.loading}
            error={deviceStatus.error}
          />
        </div>
        {deviceDetail.latest && (
          <dl
            className="mt-3 grid gap-1 text-sm sm:grid-cols-3"
            data-testid="settings-device-latest"
          >
            <div>
              <dt className="text-xs text-slate-400">RGB</dt>
              <dd className="font-mono text-xs text-slate-700 dark:text-slate-300">
                {deviceDetail.latest.rgb_r} · {deviceDetail.latest.rgb_g} ·{' '}
                {deviceDetail.latest.rgb_b}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-slate-400">Temp / humidity</dt>
              <dd className="text-xs text-slate-700 dark:text-slate-300">
                {deviceDetail.latest.temperature_c.toFixed(1)} °C ·{' '}
                {deviceDetail.latest.humidity_pct.toFixed(0)}%
              </dd>
            </div>
            <div>
              <dt className="text-xs text-slate-400">Blank baseline</dt>
              <dd className="text-xs text-slate-700 dark:text-slate-300">
                {deviceDetail.baseline ? 'calibrated' : 'not set (run CAL BLANK)'}
              </dd>
            </div>
          </dl>
        )}
        {deviceDetail.error && (
          <p className="mt-2 text-xs text-rose-600 dark:text-rose-400">
            {deviceDetail.error}
          </p>
        )}
      </div>

      <form onSubmit={handleChangePassword} className={`${card} space-y-4`}>
        <div>
          <p className="text-sm font-semibold text-slate-800 dark:text-slate-100">
            Change password
          </p>
          <p className="mt-1 text-xs text-slate-400">
            Changing your password signs out every other session.
          </p>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label
              htmlFor="current-password"
              className="mb-1 block text-xs font-semibold text-slate-600 dark:text-slate-300"
            >
              Current password
            </label>
            <input
              id="current-password"
              type="password"
              autoComplete="current-password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              className={inputClass}
              data-testid="settings-current-password"
            />
          </div>
          <div>
            <label
              htmlFor="new-password"
              className="mb-1 block text-xs font-semibold text-slate-600 dark:text-slate-300"
            >
              New password
            </label>
            <input
              id="new-password"
              type="password"
              autoComplete="new-password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              className={inputClass}
              data-testid="settings-new-password"
            />
          </div>
        </div>

        {passwordError && (
          <p
            role="alert"
            className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700 dark:bg-rose-950 dark:text-rose-300"
          >
            {passwordError}
          </p>
        )}

        <button
          type="submit"
          disabled={changing}
          data-testid="settings-change-password"
          className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50 dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-800"
        >
          {changing ? 'Changing…' : 'Change password'}
        </button>
      </form>

      <div className="rounded-xl border border-rose-200 bg-white p-6 dark:border-rose-900 dark:bg-slate-900">
        <p className="text-sm font-semibold text-rose-700 dark:text-rose-400">
          Danger zone
        </p>
        <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
          Export your data first — deleting your account permanently removes your
          profile and every checkup. This cannot be undone.
        </p>
        <div className="mt-4 flex flex-wrap gap-3">
          <button
            type="button"
            onClick={() => void handleExportData()}
            disabled={exporting}
            data-testid="settings-export-data"
            className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50 dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-800"
          >
            {exporting ? 'Exporting…' : 'Export my data'}
          </button>
          <button
            type="button"
            onClick={() => setConfirmDelete(true)}
            data-testid="settings-delete-account"
            className="rounded-lg border border-rose-300 px-4 py-2 text-sm font-semibold text-rose-700 hover:bg-rose-50 dark:border-rose-900 dark:text-rose-400 dark:hover:bg-rose-950"
          >
            Delete account
          </button>
        </div>
      </div>

      <ConfirmDialog
        open={confirmDelete}
        title="Delete your account?"
        message="Your profile and all checkups will be permanently removed. Consider exporting your data first."
        confirmLabel="Delete account"
        busy={deleting}
        onConfirm={() => void handleDeleteAccount()}
        onCancel={() => setConfirmDelete(false)}
      />
    </div>
  );
}
