import React from 'react';
import { Home, CalendarDays, Trophy, Settings } from 'lucide-react';

/**
 * Primary navigation.
 *
 * Trends and Compare appear in the design but have no working view yet, so
 * they are omitted rather than shipped as items that render nothing - which is
 * exactly the bug the old tab bar had.
 */
const NAV = [
  { key: 'overview', label: 'Overview', icon: Home },
  { key: 'regular', label: 'Regular Season', icon: CalendarDays },
  { key: 'playoffs', label: 'Playoffs', icon: Trophy }
];

const Sidebar = ({ activeView, onViewChange }) => (
  <nav
    aria-label="Primary"
    className="flex gap-2 overflow-x-auto border-b border-ink-700 bg-ink-900 px-4 py-3 lg:w-56 lg:flex-col lg:overflow-visible lg:border-b-0 lg:border-r lg:py-6"
  >
    {NAV.map((item) => {
      const Icon = item.icon;
      const active = activeView === item.key;
      return (
        <button
          key={item.key}
          type="button"
          aria-current={active ? 'page' : undefined}
          onClick={() => onViewChange(item.key)}
          className={`flex flex-shrink-0 items-center gap-3 rounded-xl px-4 py-2.5 text-sm font-semibold transition lg:flex-shrink ${
            active
              ? 'bg-accent/15 text-mist ring-1 ring-accent/40'
              : 'text-slate-400 hover:bg-ink-800 hover:text-mist'
          }`}
        >
          <Icon aria-hidden="true" className="h-4 w-4" />
          {item.label}
        </button>
      );
    })}

    <div className="hidden flex-1 lg:block" />

    <button
      type="button"
      className="flex flex-shrink-0 items-center gap-3 rounded-xl px-4 py-2.5 text-sm font-semibold text-slate-400 transition hover:bg-ink-800 hover:text-mist"
    >
      <Settings aria-hidden="true" className="h-4 w-4" />
      Settings
    </button>
  </nav>
);

export default Sidebar;
