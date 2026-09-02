import React from 'react';
import { Info } from 'lucide-react';

export const DISCLAIMER_TEXT =
  'For informational and entertainment purposes only. Not financial or betting advice.';

/**
 * Compact form, for placing next to an individual prediction where the claim
 * is actually being made.
 */
export const InlineDisclaimer = ({ className = '' }) => (
  <p className={`flex items-start gap-2 text-[11px] leading-relaxed text-slate-500 ${className}`}>
    <Info aria-hidden="true" className="mt-0.5 h-3.5 w-3.5 flex-shrink-0" />
    <span>{DISCLAIMER_TEXT}</span>
  </p>
);

/**
 * Site footer. Carries the disclaimer once, sitewide, so it is present on every
 * view rather than only on the pages someone remembered to annotate.
 */
const Disclaimer = () => (
  <footer className="mt-8 border-t border-ink-700 px-2 py-6">
    <div className="mx-auto flex max-w-4xl flex-col items-center gap-2 text-center">
      <InlineDisclaimer />
      <p className="text-[11px] leading-relaxed text-slate-600">
        Accuracy figures quoted on this site are walk-forward backtest results on
        completed seasons. They describe how the model scored on games that have
        already been played, and are not a forecast of future results.
      </p>
      <p className="text-[11px] text-slate-600">
        NFL Predictor · beta ·{' '}
        <a
          href="https://github.com/Ansh757/nfl-predictor"
          target="_blank"
          rel="noreferrer"
          className="underline transition hover:text-slate-400"
        >
          source
        </a>
      </p>
    </div>
  </footer>
);

export default Disclaimer;
