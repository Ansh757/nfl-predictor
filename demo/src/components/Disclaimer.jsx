import React from 'react';
import { SOURCE_URL } from './shell/TopHeader';

export const DISCLAIMER_TEXT =
  'For informational and entertainment purposes only. Not financial or betting advice.';

/**
 * Site footer. Carries the disclaimer once, sitewide, so it is present on every
 * view rather than only on the pages someone remembered to annotate.
 */
const Disclaimer = () => (
  <footer className="mt-24 border-t border-edge">
    <div className="mx-auto flex max-w-7xl flex-col gap-2 px-4 py-8 text-sm text-content-muted sm:flex-row sm:items-start sm:justify-between sm:px-6">
      <div className="space-y-1">
        <p>{DISCLAIMER_TEXT}</p>
        <p className="text-xs">
          Accuracy figures are walk-forward backtest results on completed seasons and live
          results on picks recorded before kickoff - how the model scored, not a forecast.
        </p>
      </div>
      <a href={SOURCE_URL} target="_blank" rel="noreferrer" className="shrink-0 transition hover:text-content">
        View source
      </a>
    </div>
  </footer>
);

export default Disclaimer;
