import React, { useEffect, useState } from 'react';
import { api, getLastApiError } from '../services/api';

/**
 * Degraded-state banner.
 *
 * The dashboard must never render fabricated inventory or audit figures, so
 * when the backend is unreachable this banner is shown explicitly.
 */
export function ApiStatusBanner() {
  const [error, setError] = useState(() => getLastApiError());

  useEffect(() => {
    let mounted = true;

    async function probe() {
      try {
        await api.health();
      } catch {
        // api.health() records lastApiError on failure
      }
      if (mounted) setError(getLastApiError());
    }

    probe();
    const timer = setInterval(probe, 15000);
    return () => {
      mounted = false;
      clearInterval(timer);
    };
  }, []);

  if (!error) return null;

  return (
    <div className="mb-4 rounded-xl border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-sm text-amber-200">
      <div className="flex items-start gap-2">
        <span aria-hidden="true">⚠️</span>
        <div>
          <div className="font-semibold">Backend tidak dapat dijangkau — data tidak ditampilkan.</div>
          <div className="text-amber-200/80 mt-0.5">
            <code className="text-xs">{error.message}</code>
          </div>
          <div className="text-amber-200/60 text-xs mt-1">
            Demo lokal: jalankan <code>python demo/scripts/05_dashboard_api.py</code> (port 8000).
            AWS: set <code>VITE_API_BASE_URL</code> ke URL API Gateway.
          </div>
        </div>
      </div>
    </div>
  );
}
