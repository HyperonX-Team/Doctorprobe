// Settings — profile management: data sharing toggle, device id, user id
// with copy button, and account deletion.

import { useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import { useUser } from '../hooks/useUser';
import { useToast } from '../components/ui/Toast';
import ConfirmDialog from '../components/ui/ConfirmDialog';
import { getErrorMessage } from '../utils/errors';

export default function Settings() {
  const { user, refreshUser, logout } = useUser();
  const toast = useToast();
  const navigate = useNavigate();

  const [deviceId, setDeviceId] = useState(user?.device_id ?? '');
  const [shareData, setShareData] = useState(user?.share_data ?? false);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [copied, setCopied] = useState(false);

  const handleSave = async (event: FormEvent) => {
    event.preventDefault();
    if (!user || !deviceId.trim()) {
      setSaveError('Device ID cannot be empty');
      return;
    }
    setSaving(true);
    setSaveError(null);
    try {
      await api.updateUser(user.id, {
        device_id: deviceId.trim(),
        share_data: shareData,
      });
      await refreshUser();
      toast.show('Settings saved', 'success');
    } catch (err) {
      setSaveError(getErrorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  const handleCopyUserId = async () => {
    if (!user) {
      return;
    }
    try {
      await navigator.clipboard.writeText(user.id);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      toast.show('Could not copy user id', 'error');
    }
  };

  const handleDeleteAccount = async () => {
    if (!user) {
      return;
    }
    setDeleting(true);
    try {
      await api.deleteUser(user.id);
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

  const inputClass =
    'w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-100';

  return (
    <div className="mx-auto max-w-2xl space-y-6 animate-fade-in">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Settings</h1>
        <p className="mt-1 text-sm text-slate-500">
          Manage your profile, privacy and device.
        </p>
      </div>

      <form
        onSubmit={handleSave}
        className="space-y-5 rounded-xl border border-slate-200 bg-white p-6"
      >
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
            Your user id
          </p>
          <div className="mt-2 flex items-center gap-2">
            <code
              className="flex-1 truncate rounded-lg bg-slate-50 px-3 py-2 font-mono text-xs text-slate-700"
              data-testid="settings-user-id"
            >
              {user.id}
            </code>
            <button
              type="button"
              onClick={() => void handleCopyUserId()}
              className="rounded-lg border border-slate-300 px-3 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-50"
            >
              {copied ? 'Copied!' : 'Copy'}
            </button>
          </div>
          <p className="mt-1 text-xs text-slate-400">
            Used to identify your profile on this device.
          </p>
        </div>

        <div>
          <label
            htmlFor="device-id"
            className="mb-1 block text-xs font-semibold text-slate-600"
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

        <label className="flex items-start gap-3">
          <input
            type="checkbox"
            checked={shareData}
            onChange={(e) => setShareData(e.target.checked)}
            className="mt-0.5 h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-300"
            data-testid="settings-share-data"
          />
          <span>
            <span className="block text-sm font-semibold text-slate-700">
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
            className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700"
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

      <div className="rounded-xl border border-rose-200 bg-white p-6">
        <p className="text-sm font-semibold text-rose-700">Danger zone</p>
        <p className="mt-1 text-xs text-slate-500">
          Deleting your account permanently removes your profile and every checkup. This
          cannot be undone.
        </p>
        <button
          type="button"
          onClick={() => setConfirmDelete(true)}
          data-testid="settings-delete-account"
          className="mt-4 rounded-lg border border-rose-300 px-4 py-2 text-sm font-semibold text-rose-700 hover:bg-rose-50"
        >
          Delete account
        </button>
      </div>

      <ConfirmDialog
        open={confirmDelete}
        title="Delete your account?"
        message="Your profile and all checkups will be permanently removed."
        confirmLabel="Delete account"
        busy={deleting}
        onConfirm={() => void handleDeleteAccount()}
        onCancel={() => setConfirmDelete(false)}
      />
    </div>
  );
}
