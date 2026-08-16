// Report — chat-style view of a single checkup with expandable biomarker
// table, share (token reward) and save-to-vault actions.

import { Link, useParams } from 'react-router-dom';
import { useEffect, useState } from 'react';
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
  const { checkup, loading, error, reload } = useCheckup(checkupId);
  const toast = useToast();
  const [sharing, setSharing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [noteDraft, setNoteDraft] = useState('');
  const [noteSaving, setNoteSaving] = useState(false);
  const [noteError, setNoteError] = useState<string | null>(null);

  // Sync the editor with the loaded report (also after saving/reload).
  useEffect(() => {
    setNoteDraft(checkup?.note ?? '');
  }, [checkup?.id, checkup?.note]);

  const handleSaveNote = async (value?: string) => {
    if (!checkup) {
      return;
    }
    const next = (value ?? noteDraft).trim();
    setNoteSaving(true);
    setNoteError(null);
    try {
      const updated = await api.updateCheckupNote(checkup.id, next);
      await reload();
      // Keep the local draft in sync with what the server stored.
      setNoteDraft(updated.note ?? '');
      toast.show(updated.note ? 'Note saved' : 'Note cleared', 'success');
    } catch (err) {
      setNoteError(getErrorMessage(err));
    } finally {
      setNoteSaving(false);
    }
  };

  const handleShare = async () => {
    if (!checkup || !user) {
      return;
    }
    setSharing(true);
    try {
      const result = await api.shareCheckup(checkup.id);
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

  const handleExportPdf = async () => {
    if (!checkup) {
      return;
    }
    setExporting(true);
    try {
      const blob = await api.exportCheckup(checkup.id);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = `doctordrobe-report-${checkup.id}.pdf`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
      toast.show('Clinician PDF downloaded', 'success');
    } catch (err) {
      toast.show(getErrorMessage(err), 'error');
    } finally {
      setExporting(false);
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
        className="rounded-xl border border-rose-200 bg-rose-50 p-5 text-sm text-rose-700 dark:border-rose-900 dark:bg-rose-950 dark:text-rose-300"
      >
        {error}
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6 animate-fade-in">
      <Link
        to="/history"
        className="inline-block text-xs font-semibold text-slate-500 hover:text-brand-700 dark:text-slate-400 dark:hover:text-brand-300"
        data-testid="report-back"
      >
        ← Back to history
      </Link>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white">
            Your report
          </h1>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            {formatDate(checkup.created_at)}
          </p>
        </div>
        <span
          className={`rounded-full px-3 py-1 text-xs font-semibold ${riskBadgeClasses(checkup.overall_risk)}`}
        >
          {checkup.overall_risk.toUpperCase()} RISK
        </span>
      </div>

      <div
        className="rounded-xl border border-slate-200 bg-white p-5 dark:border-slate-700 dark:bg-slate-900"
        data-testid="report-note"
      >
        <label
          htmlFor="report-note-input"
          className="block text-xs font-semibold uppercase tracking-wide text-slate-400"
        >
          Your note
        </label>
        <textarea
          id="report-note-input"
          value={noteDraft}
          onChange={(e) => setNoteDraft(e.target.value)}
          rows={2}
          maxLength={2000}
          placeholder="Add a private note to this checkup — how you felt, what you ate, anything you want to remember."
          className="mt-2 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-100 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-100 dark:placeholder:text-slate-500"
          data-testid="report-note-input"
        />
        <div className="mt-2 flex items-center gap-3">
          <button
            type="button"
            onClick={() => void handleSaveNote()}
            disabled={noteSaving}
            data-testid="report-note-save"
            className="rounded-lg bg-brand-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-brand-700 disabled:opacity-50"
          >
            {noteSaving ? 'Saving…' : 'Save note'}
          </button>
          {checkup.note && (
            <button
              type="button"
              onClick={() => void handleSaveNote('')}
              disabled={noteSaving}
              className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-semibold text-slate-600 hover:bg-slate-50 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-800"
              data-testid="report-note-clear"
            >
              Clear
            </button>
          )}
          {noteError && (
            <span className="text-xs text-rose-600 dark:text-rose-400">
              {noteError}
            </span>
          )}
        </div>
        <p className="mt-2 text-[11px] text-slate-400">
          Notes are stored encrypted with your report.
        </p>
      </div>

      <div className="space-y-3">
        <ChatBubble role="user">How am I doing today?</ChatBubble>
        <ChatBubble role="assistant">{checkup.text_summary}</ChatBubble>
      </div>

      {checkup.quality && checkup.quality.grade !== 'good' && (
        <div
          role="alert"
          data-testid="report-quality"
          className={`rounded-xl border p-5 ${
            checkup.quality.grade === 'poor'
              ? 'border-rose-200 bg-rose-50'
              : 'border-amber-200 bg-amber-50'
          }`}
        >
          <p
            className={`text-sm font-semibold ${
              checkup.quality.grade === 'poor' ? 'text-rose-800' : 'text-amber-800'
            }`}
          >
            {checkup.quality.grade === 'poor'
              ? 'This reading may not be trustworthy — consider retaking it'
              : 'This reading has some limitations'}
          </p>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-xs text-slate-600">
            {checkup.quality.reasons.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
          {checkup.quality.recommended_action === 'retake_reading' && (
            <p className="mt-3 text-xs font-semibold text-rose-700">
              Recommended action: retake the reading with a fresh strip, then run a new
              checkup.
            </p>
          )}
        </div>
      )}

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
          onClick={() => void handleExportPdf()}
          disabled={exporting}
          data-testid="report-export-pdf"
          className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
        >
          {exporting ? 'Generating…' : 'Download clinician PDF'}
        </button>
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
