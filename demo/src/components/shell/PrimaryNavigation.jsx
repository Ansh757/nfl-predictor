import React from 'react';
import { Home, ListOrdered, Trophy } from 'lucide-react';

/**
 * The three sections, and only three.
 *
 * Rendered twice: inline in the header on desktop, and as a fixed bottom bar on
 * mobile, where a horizontal row in the header would either wrap or shrink the
 * targets below 44px.
 */
export const VIEWS = [
  { key: 'overview', label: 'Overview', icon: Home },
  { key: 'predictions', label: 'Predictions', icon: ListOrdered },
  { key: 'playoffs', label: 'Playoffs', icon: Trophy },
];

const PrimaryNavigation = ({ activeView, onViewChange, className = '' }) => (
  <nav aria-label="Primary" className={className}>
    <ul className="flex items-center gap-1">
      {VIEWS.map(({ key, label }) => {
        const active = activeView === key;
        return (
          <li key={key}>
            {/* The active tab carries a broadcast-red rule along the header's
                bottom edge, as well as full-contrast text - never colour alone. */}
            <button
              type="button"
              onClick={() => onViewChange(key)}
              aria-current={active ? 'page' : undefined}
              className={`relative rounded-md px-3 py-2 font-display text-sm font-semibold uppercase tracking-wider transition ${
                active ? 'text-content' : 'text-content-muted hover:text-content'
              }`}
            >
              {label}
              {active && (
                <span aria-hidden="true" className="absolute inset-x-3 -bottom-[13px] h-0.5 bg-brand" />
              )}
            </button>
          </li>
        );
      })}
    </ul>
  </nav>
);

/**
 * Mobile bar. Separate component rather than a breakpoint on the one above,
 * because it needs icons, 44px targets and fixed positioning - and sharing
 * those through class overrides would make both harder to read.
 */
export const MobileNavigation = ({ activeView, onViewChange }) => (
  <nav
    aria-label="Primary"
    className="fixed inset-x-0 bottom-0 z-40 border-t border-edge bg-background lg:hidden"
  >
    <ul className="mx-auto flex max-w-lg">
      {VIEWS.map(({ key, label, icon: Icon }) => {
        const active = activeView === key;
        return (
          <li key={key} className="flex-1">
            <button
              type="button"
              onClick={() => onViewChange(key)}
              aria-current={active ? 'page' : undefined}
              className={`flex min-h-[52px] w-full flex-col items-center justify-center gap-0.5 font-display text-[11px] font-semibold uppercase tracking-wider transition ${
                active ? 'text-content' : 'text-content-muted'
              }`}
            >
              <Icon aria-hidden="true" className={`h-4 w-4 ${active ? 'text-brand-text' : ''}`} />
              {label}
            </button>
          </li>
        );
      })}
    </ul>
  </nav>
);

export default PrimaryNavigation;
