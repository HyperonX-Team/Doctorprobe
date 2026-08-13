// Checkup — run a new analysis from a physical device reading.
//
// Every checkup is derived from the latest reading the ESP32 has posted
// to /api/devices/reading. There is no simulated mode; if the device has
// never reported, the backend returns 409 and the UI offers retry.

import { useCallback, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import { useUser } from '../hooks/useUser';
import { useDeviceStatus } from '../hooks/useDeviceStatus';
import { getErrorMessage } from '../utils/errors';
import CheckupProgress from '../components/ui/CheckupProgress';
import DeviceStatus from '../components/ui/DeviceStatus';

type Phase =
  { kind: 'idle' } | { kind: 'creating' } | { kind: 'error'; message: string };

export default function Checkup() {
  const { user } = useUser();
  const navigate = useNavigate();
  const deviceStatus = useDeviceStatus(user?.device_id);
  const [phase, setPhase] = useState<Phase>({ kind: 'idle' });

  const create = useCallback(async () => {
    if (!user) {
      return;
    }
    setPhase({ kind: 'creating' });
    try {
      const checkup = await api.createCheckup();
      navigate(`/report/${checkup.id}`);
    } catch (err) {
      setPhase({ kind: 'error', message: getErrorMessage(err) });
    }
  }, [user, navigate]);

  const handleScan = () => {
    void create();
  };

  if (!user) {
    return null;
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6 animate-fade-in">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">New checkup</h1>
        <p className="mt-1 text-sm text-slate-500">
          Place a fresh saliva strip under the sensor on your Doctordrobe device and
          press its button, then scan below. Reports are derived from the physical
          reading — there is no simulated mode.
        </p>
      </div>

      <DeviceStatus
        status={deviceStatus.status}
        loading={deviceStatus.loading}
        error={deviceStatus.error}
      />

      {phase.kind === 'idle' && (
        <button
          type="button"
          onClick={handleScan}
          data-testid="checkup-scan"
          className="w-full rounded-xl border border-slate-200 bg-white px-5 py-6 text-left text-sm font-semibold text-slate-800 shadow hover:bg-slate-50"
        >
          Scan with Device
          <span className="mt-1 block text-xs font-normal text-slate-500">
            Uses the latest reading from your ESP32 device.
          </span>
        </button>
      )}

      {phase.kind === 'creating' && (
        <div className="flex justify-center rounded-xl border border-slate-200 bg-white p-8">
          <CheckupProgress durationMs={4000} />
        </div>
      )}

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
          </div>
        </div>
      )}
    </div>
  );
}
