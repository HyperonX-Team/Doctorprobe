// Login — email + password sign-in. Exchanges credentials for an opaque
// bearer token, which every subsequent request carries.

import { useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import { useUser } from '../hooks/useUser';
import { getErrorMessage } from '../utils/errors';
import LoadingSpinner from '../components/ui/LoadingSpinner';

export default function Login() {
  const navigate = useNavigate();
  const { login } = useUser();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (!email.trim() || !password) {
      setFormError('Enter your email and password');
      return;
    }
    setSubmitting(true);
    setFormError(null);
    try {
      const auth = await api.login({ email: email.trim(), password });
      login(auth.token, auth.user);
      navigate('/');
    } catch (err) {
      setFormError(getErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  };

  if (submitting) {
    return <LoadingSpinner label="Signing you in…" />;
  }

  const inputClass =
    'w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-100';

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

        <h2 className="mt-6 text-lg font-semibold text-slate-800">Welcome back</h2>
        <p className="mt-1 text-sm text-slate-500">
          Log in to see your checkups and trends.
        </p>

        <form onSubmit={handleSubmit} noValidate className="mt-6 space-y-4">
          <div>
            <label
              htmlFor="login-email"
              className="mb-1 block text-xs font-semibold text-slate-600"
            >
              Email
            </label>
            <input
              id="login-email"
              type="email"
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className={inputClass}
              placeholder="you@example.com"
              data-testid="login-email"
            />
          </div>
          <div>
            <label
              htmlFor="login-password"
              className="mb-1 block text-xs font-semibold text-slate-600"
            >
              Password
            </label>
            <input
              id="login-password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className={inputClass}
              placeholder="Your password"
              data-testid="login-password"
            />
          </div>

          {formError && (
            <p
              role="alert"
              data-testid="login-error"
              className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700"
            >
              {formError}
            </p>
          )}

          <button
            type="submit"
            data-testid="login-submit"
            className="w-full rounded-lg bg-brand-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-brand-700 focus:outline-none focus:ring-2 focus:ring-brand-300"
          >
            Log in
          </button>
        </form>

        <p className="mt-4 text-center text-sm text-slate-500">
          New here?{' '}
          <Link to="/welcome" className="font-semibold text-brand-700 hover:underline">
            Create an account
          </Link>
        </p>
      </div>
    </div>
  );
}
