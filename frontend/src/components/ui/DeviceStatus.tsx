// DeviceStatus — banner showing whether the physical device is connected.

import type { ReactNode } from 'react';
import type { DeviceStatus as DeviceStatusType } from '../../types';

interface DeviceStatusProps {
  status: DeviceStatusType | null;
  loading: boolean;
  error: string | null;
}

export default function DeviceStatus({ status, loading, error }: DeviceStatusProps) {
  let content: ReactNode;

  if (loading) {
    content = (
      <span className="text-sm text-slate-500 animate-pulse-soft">
        Checking device…
      </span>
    );
  } else if (error) {
    content = (
      <span className="text-sm text-rose-600">Device status unavailable: {error}</span>
    );
  } else if (!status) {
    content = (
      <span className="text-sm text-slate-500">
        No status yet — your device has not been seen.
      </span>
    );
  } else if (status.connected) {
    content = (
      <span className="flex items-center gap-2 text-sm text-emerald-700">
        <span className="h-2 w-2 rounded-full bg-emerald-500" aria-hidden="true" />
        Device connected
        {status.last_seen && (
          <span className="text-slate-400">
            · last seen {new Date(status.last_seen).toLocaleTimeString()}
          </span>
        )}
      </span>
    );
  } else {
    content = (
      <span className="flex items-center gap-2 text-sm text-slate-500">
        <span className="h-2 w-2 rounded-full bg-slate-300" aria-hidden="true" />
        Device offline — press the button on your Doctordrobe to send a reading.
      </span>
    );
  }

  return (
    <div
      data-testid="device-status"
      className="rounded-xl border border-slate-200 bg-white px-4 py-3"
    >
      {content}
    </div>
  );
}
