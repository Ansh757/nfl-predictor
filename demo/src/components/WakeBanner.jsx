import React, { useEffect, useState } from 'react';
import { Loader2 } from 'lucide-react';

/**
 * Shown while the prediction service is still coming up.
 *
 * The deploy sleeps when idle, so a first load can sit for up to ~90 seconds
 * before anything answers. Unannounced, that reads as a broken site: the
 * status badge went red, the games list said "Loading games…" forever, and
 * there was nothing to say the wait was expected or how long it would last.
 * The elapsed counter is the point - it turns a hang into progress.
 */
const WakeBanner = () => {
  const [seconds, setSeconds] = useState(0);

  useEffect(() => {
    const timer = setInterval(() => setSeconds((value) => value + 1), 1000);
    return () => clearInterval(timer);
  }, []);

  return (
    <div
      role="status"
      className="mx-6 mt-4 flex flex-wrap items-center gap-3 rounded-2xl border border-caution/30 bg-caution/10 px-4 py-3"
    >
      <Loader2 aria-hidden="true" className="h-4 w-4 flex-shrink-0 animate-spin text-caution" />
      <div className="min-w-0">
        <p className="text-sm font-semibold text-mist">Waking the prediction service…</p>
        <p className="mt-0.5 text-xs leading-relaxed text-slate-400">
          This deployment sleeps when nobody is using it, so the first load of the
          day can take up to a minute. Nothing is broken — the page fills in on its
          own as soon as the service answers.
        </p>
      </div>
      <span className="ml-auto whitespace-nowrap text-xs font-semibold tabular-nums text-caution">
        {seconds}s
      </span>
    </div>
  );
};

export default WakeBanner;
