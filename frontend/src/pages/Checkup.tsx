// Checkup — run a new analysis. Two paths:
//   1. "Simulate" — animated progress, then POST with use_device_reading=false.
//   2. "Scan with Device" — POST with use_device_reading=true; 409 is handled
//      with a clear message and Retry button.

import { useCallback, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import { useUser } from '../hooks/useUser';
import { useDeviceStatus } from '../hooks/useDeviceStatus';
import { getErrorMessage } from '../utils/errors';
import CheckupProgress from '../components/ui/CheckupProgress';
import DeviceStatus from '../components/ui/DeviceStatus';
import LoadingSpinner from '../components/ui/LoadingSpinner';

type Phase =
  | { kind: 'idle' }
  | { kind: 'simulating' }
  | { kind: 'creating'; label: string }
  | { kind: 'error'; message: string };

const SIMULATION_MS = 15_000;

export default function Checkup() {
  const { user } = useUser();
  const navigate = useNavigate();
  const deviceStatus = useDeviceStatus(user?.device_id);
  const [phase, setPhase] = useState<Phase>({ kind: 'idle' });

  const create = useCallback(
    async (useDeviceReading: boolean) => {
      if (!user) {
        return;
      }
      setPhase({ kind: 'creating', label: 'Finalizing your report…' });
      try {
        const checkup = await api.createCheckup({
          user_id: user.id,
          use_device_reading: useDeviceReading,
        });
        navigate(`/report/${checkup.id}`);
      } catch (err) {
        setPhase({ kind: 'error', message: getErrorMessage(err) });
      }
    },
    [user, navigate],
  );

  const handleSimulate = () => {
    setPhase({ kind: 'simulating' });
  };

  const handleScan = () => {
    void create(true);
  };

  if (!user) {
    return null;
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6 animate-fade-in">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">New checkup</h1>
        <p className="mt-1 text-sm text-slate-500">
          Analyze your saliva strip with the Doctordrobe device, or run a simulated
          analysis to explore the app.
        </p>
      </div>

      <DeviceStatus
        status={deviceStatus.status}
        loading={deviceStatus.loading}
        error={deviceStatus.error}
      />

      {phase.kind === 'idle' && (
        <div className="grid gap-4 sm:grid-cols-2">
          <button
            type="button"
            onClick={handleSimulate}
            data-testid="checkup-simulate"
            className="rounded-xl bg-brand-600 px-5 py-6 text-left text-sm font-semibold text-white shadow hover:bg-brand-700"
          >
            Simulate
            <span className="mt-1 block text-xs font-normal text-brand-100">
              No hardware required — runs the demo biomarker pipeline.
            </span>
          </button>
          <button
            type="button"
            onClick={handleScan}
            data-testid="checkup-scan"
            className="rounded-xl border border-slate-200 bg-white px-5 py-6 text-left text-sm font-semibold text-slate-800 shadow hover:bg-slate-50"
          >
            Scan with Device
            <span className="mt-1 block text-xs font-normal text-slate-500">
              Uses the latest reading from your ESP32 device.
            </span>
          </button>
        </div>
      )}

      {phase.kind === 'simulating' && (
        <div className="flex justify-center rounded-xl border border-slate-200 bg-white p-8">
          <CheckupProgress
            durationMs={SIMULATION_MS}
            onComplete={() => void create(false)}
          />
        </div>
      )}

      {phase.kind === 'creating' && <LoadingSpinner label={phase.label} />}

      {phase.kind === 'error' && (
        <div
          role="alert"
          data-testid="checkup-error"
          className="rounded-xl border border-rose-200 bg-rose-50 p-5"
        >
          <p className="text-sm font-semibold text-rose-800">Could not run checkup</p>
          <p className="mt-1 text-sm text-rose-700">{phase.message}</p>
          <div className="mt-4 flex gap-3">
            <button
              type="button"
              onClick={() => setPhase({ kind: 'idle' })}
              data-testid="checkup-retry"
              className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700"
            >
              Retry
            </button>
            {phase.message.toLowerCase().includes('device reading') && (
              <button
                type="button"
                onClick={() => void create(false)}
                className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-white"
              >
                Run simulation instead
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
