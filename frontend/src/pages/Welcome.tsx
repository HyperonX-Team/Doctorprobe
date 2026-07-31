// Welcome — onboarding form. Creates the user profile and starts the
// session. Uses plain controlled inputs with client-side validation.

import { useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import { useUser } from '../hooks/useUser';
import type { ActivityLevel, Sex } from '../types';
import { getErrorMessage } from '../utils/errors';
import LoadingSpinner from '../components/ui/LoadingSpinner';

interface FormValues {
  age: string;
  sex: Sex;
  heightCm: string;
  weightKg: string;
  activityLevel: ActivityLevel;
}

const INITIAL: FormValues = {
  age: '',
  sex: 'female',
  heightCm: '',
  weightKg: '',
  activityLevel: 'moderate',
};

const ACTIVITY_OPTIONS: { value: ActivityLevel; label: string }[] = [
  { value: 'sedentary', label: 'Mostly desk-bound' },
  { value: 'light', label: 'Light exercise' },
  { value: 'moderate', label: 'Regular exercise' },
  { value: 'active', label: 'Very active' },
  { value: 'athlete', label: 'Athlete' },
];

export default function Welcome() {
  const navigate = useNavigate();
  const { login } = useUser();
  const [values, setValues] = useState<FormValues>(INITIAL);
  const [errors, setErrors] = useState<Partial<Record<keyof FormValues, string>>>({});
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const set = <K extends keyof FormValues>(key: K, value: FormValues[K]) => {
    setValues((current) => ({ ...current, [key]: value }));
    setErrors((current) => ({ ...current, [key]: undefined }));
  };

  const validate = (): boolean => {
    const next: Partial<Record<keyof FormValues, string>> = {};
    const age = Number(values.age);
    const height = Number(values.heightCm);
    const weight = Number(values.weightKg);

    if (!values.age || Number.isNaN(age) || age < 1 || age > 120) {
      next.age = 'Age must be between 1 and 120';
    }
    if (!values.heightCm || Number.isNaN(height) || height < 50 || height > 250) {
      next.heightCm = 'Height must be between 50 and 250 cm';
    }
    if (!values.weightKg || Number.isNaN(weight) || weight < 2 || weight > 500) {
      next.weightKg = 'Weight must be between 2 and 500 kg';
    }
    setErrors(next);
    return Object.keys(next).length === 0;
  };

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (!validate()) {
      return;
    }
    setSubmitting(true);
    setFormError(null);
    try {
      const user = await api.createUser({
        age: Number(values.age),
        sex: values.sex,
        height_cm: Number(values.heightCm),
        weight_kg: Number(values.weightKg),
        activity_level: values.activityLevel,
        share_data: false,
        device_id: 'doctordrobe_demo_001',
      });
      login(user);
      navigate('/checkup');
    } catch (err) {
      setFormError(getErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  };

  if (submitting) {
    return <LoadingSpinner label="Creating your profile…" />;
  }

  const inputClass = (hasError: boolean) =>
    `w-full rounded-lg border px-3 py-2 text-sm outline-none focus:ring-2 ${
      hasError
        ? 'border-rose-400 focus:border-rose-400 focus:ring-rose-100'
        : 'border-slate-300 focus:border-brand-500 focus:ring-brand-100'
    }`;

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-brand-50 via-slate-50 to-sky-50 px-4">
      <div className="w-full max-w-md animate-fade-in rounded-2xl bg-white p-8 shadow-xl">
        <div className="flex items-center gap-2">
          <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand-600 text-lg font-bold text-white">
            D
          </span>
          <div>
            <h1 className="text-xl font-bold text-slate-900">Doctordrobe</h1>
            <p className="text-xs text-slate-500">Home health analysis</p>
          </div>
        </div>

        <h2 className="mt-6 text-lg font-semibold text-slate-800">
          Let's get to know you
        </h2>
        <p className="mt-1 text-sm text-slate-500">
          Your profile tunes the biomarker analysis. No password needed — this device
          keeps you signed in.
        </p>

        <form onSubmit={handleSubmit} noValidate className="mt-6 space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label
                htmlFor="age"
                className="mb-1 block text-xs font-semibold text-slate-600"
              >
                Age
              </label>
              <input
                id="age"
                type="number"
                inputMode="numeric"
                min={1}
                max={120}
                value={values.age}
                onChange={(e) => set('age', e.target.value)}
                className={inputClass(Boolean(errors.age))}
                placeholder="e.g. 34"
                data-testid="welcome-age"
              />
              {errors.age && <p className="mt-1 text-xs text-rose-600">{errors.age}</p>}
            </div>
            <div>
              <label
                htmlFor="sex"
                className="mb-1 block text-xs font-semibold text-slate-600"
              >
                Sex
              </label>
              <select
                id="sex"
                value={values.sex}
                onChange={(e) => set('sex', e.target.value as Sex)}
                className={inputClass(false)}
                data-testid="welcome-sex"
              >
                <option value="female">Female</option>
                <option value="male">Male</option>
                <option value="other">Other</option>
              </select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label
                htmlFor="height"
                className="mb-1 block text-xs font-semibold text-slate-600"
              >
                Height (cm)
              </label>
              <input
                id="height"
                type="number"
                inputMode="decimal"
                min={50}
                max={250}
                step="0.1"
                value={values.heightCm}
                onChange={(e) => set('heightCm', e.target.value)}
                className={inputClass(Boolean(errors.heightCm))}
                placeholder="e.g. 165"
                data-testid="welcome-height"
              />
              {errors.heightCm && (
                <p className="mt-1 text-xs text-rose-600">{errors.heightCm}</p>
              )}
            </div>
            <div>
              <label
                htmlFor="weight"
                className="mb-1 block text-xs font-semibold text-slate-600"
              >
                Weight (kg)
              </label>
              <input
                id="weight"
                type="number"
                inputMode="decimal"
                min={2}
                max={500}
                step="0.1"
                value={values.weightKg}
                onChange={(e) => set('weightKg', e.target.value)}
                className={inputClass(Boolean(errors.weightKg))}
                placeholder="e.g. 62"
                data-testid="welcome-weight"
              />
              {errors.weightKg && (
                <p className="mt-1 text-xs text-rose-600">{errors.weightKg}</p>
              )}
            </div>
          </div>

          <div>
            <label
              htmlFor="activity"
              className="mb-1 block text-xs font-semibold text-slate-600"
            >
              Activity level
            </label>
            <select
              id="activity"
              value={values.activityLevel}
              onChange={(e) => set('activityLevel', e.target.value as ActivityLevel)}
              className={inputClass(false)}
              data-testid="welcome-activity"
            >
              {ACTIVITY_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>

          {formError && (
            <p
              role="alert"
              data-testid="welcome-error"
              className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700"
            >
              {formError}
            </p>
          )}

          <button
            type="submit"
            data-testid="welcome-submit"
            className="w-full rounded-lg bg-brand-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-brand-700 focus:outline-none focus:ring-2 focus:ring-brand-300"
          >
            Start my first checkup
          </button>
        </form>
      </div>
    </div>
  );
}
