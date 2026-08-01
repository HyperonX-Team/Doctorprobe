// Report — chat-style view of a single checkup with expandable biomarker
// table, share (token reward) and save-to-vault actions.

import { useParams } from 'react-router-dom';
import { useState } from 'react';
import { api } from '../api/client';
import { useUser } from '../hooks/useUser';
import { useCheckup } from '../hooks/useCheckup';
import { useToast } from '../components/ui/Toast';
import ChatBubble from '../components/ui/ChatBubble';
import ReportTable from '../components/ui/ReportTable';
import LoadingSpinner from '../components/ui/LoadingSpinner';
import { formatDate, riskBadgeClasses } from '../utils/formatters';
import { getErrorMessage } from '../utils/errors';

export default function Report() {
  const { checkupId } = useParams<{ checkupId: string }>();
  const { user, refreshUser } = useUser();
  const { checkup, loading, error } = useCheckup(checkupId, user?.id);
  const toast = useToast();
  const [sharing, setSharing] = useState(false);
  const [saving, setSaving] = useState(false);

  const handleShare = async () => {
    if (!checkup || !user) {
      return;
    }
    setSharing(true);
    try {
      const result = await api.shareCheckup(checkup.id, user.id);
      await refreshUser();
      toast.show(
        `Checkup shared — you earned ${result.tokens_awarded} tokens (balance ${result.new_balance})`,
        'success',
      );
    } catch (err) {
      toast.show(getErrorMessage(err), 'error');
    } finally {
      setSharing(false);
    }
  };

  const handleSaveToVault = () => {
    if (!checkupId) {
      return;
    }
    setSaving(true);
    // Demo: the vault is the browser — persist a pointer and confirm.
    const saved = JSON.parse(
      localStorage.getItem('doctordrobe_vault') ?? '[]',
    ) as string[];
    if (!saved.includes(checkupId)) {
      saved.unshift(checkupId);
      localStorage.setItem('doctordrobe_vault', JSON.stringify(saved));
    }
    window.setTimeout(() => setSaving(false), 400);
    toast.show('Saved to your vault', 'success');
  };

  if (loading || !checkup) {
    return <LoadingSpinner label="Decrypting your report…" />;
  }

  if (error) {
    return (
      <div
        role="alert"
        data-testid="report-error"
        className="rounded-xl border border-rose-200 bg-rose-50 p-5 text-sm text-rose-700"
      >
        {error}
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6 animate-fade-in">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Your report</h1>
          <p className="mt-1 text-sm text-slate-500">
            {formatDate(checkup.created_at)}
          </p>
        </div>
        <span
          className={`rounded-full px-3 py-1 text-xs font-semibold ${riskBadgeClasses(checkup.overall_risk)}`}
        >
          {checkup.overall_risk.toUpperCase()} RISK
        </span>
      </div>

      <div className="space-y-3">
        <ChatBubble role="user">How am I doing today?</ChatBubble>
        <ChatBubble role="assistant">{checkup.text_summary}</ChatBubble>
      </div>

      <ReportTable biomarkers={checkup.biomarkers} />

      <div className="flex flex-wrap gap-3">
        {user?.share_data && (
          <button
            type="button"
            onClick={() => void handleShare()}
            disabled={sharing || checkup.is_shared}
            data-testid="report-share"
            className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {checkup.is_shared
              ? 'Already shared'
              : sharing
                ? 'Sharing…'
                : 'Share with community (+5 tokens)'}
          </button>
        )}
        <button
          type="button"
          onClick={handleSaveToVault}
          disabled={saving}
          data-testid="report-save-vault"
          className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
        >
          {saving ? 'Saving…' : 'Save to Vault'}
        </button>
      </div>

      {!user?.share_data && (
        <p className="text-xs text-slate-400">
          Enable “Share data” in Settings to earn tokens when sharing reports.
        </p>
      )}
    </div>
  );
}
