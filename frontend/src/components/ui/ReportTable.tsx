// ReportTable — expandable biomarker detail table for the report page.

import { useState } from 'react';
import type { Biomarker } from '../../types';
import { formatNumber, stateBadgeClasses } from '../../utils/formatters';

interface ReportTableProps {
  biomarkers: Biomarker[];
}

export default function ReportTable({ biomarkers }: ReportTableProps) {
  const [expanded, setExpanded] = useState(false);

  const visible = expanded ? biomarkers : biomarkers.slice(0, 3);

  return (
    <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
      <table className="w-full text-left text-sm" data-testid="report-table">
        <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
          <tr>
            <th scope="col" className="px-4 py-2.5 font-semibold">
              Biomarker
            </th>
            <th scope="col" className="px-4 py-2.5 font-semibold">
              Value
            </th>
            <th scope="col" className="px-4 py-2.5 font-semibold">
              Reference
            </th>
            <th scope="col" className="px-4 py-2.5 font-semibold">
              State
            </th>
            <th scope="col" className="px-4 py-2.5 font-semibold">
              Confidence
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {visible.map((marker) => (
            <tr key={marker.name}>
              <td className="px-4 py-3 font-medium text-slate-800">{marker.name}</td>
              <td className="px-4 py-3 text-slate-700">
                {formatNumber(marker.value)} {marker.unit}
              </td>
              <td className="px-4 py-3 text-slate-500">
                {marker.ref_low != null && marker.ref_high != null
                  ? `${formatNumber(marker.ref_low)} – ${formatNumber(marker.ref_high)}`
                  : '—'}
              </td>
              <td className="px-4 py-3">
                <span
                  className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${stateBadgeClasses(marker.state)}`}
                >
                  {marker.state}
                </span>
              </td>
              <td className="px-4 py-3 text-slate-500">
                {marker.confidence != null
                  ? `${Math.round(marker.confidence * 100)}%`
                  : '—'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {biomarkers.length > 3 && (
        <button
          type="button"
          onClick={() => setExpanded((value) => !value)}
          className="block w-full border-t border-slate-100 px-4 py-2.5 text-xs font-semibold text-brand-700 hover:bg-brand-50"
          data-testid="report-table-toggle"
        >
          {expanded ? 'Show fewer markers' : `Show all ${biomarkers.length} markers`}
        </button>
      )}
    </div>
  );
}
