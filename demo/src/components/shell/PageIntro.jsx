import React from 'react';
import { teamAbbreviation, teamLogo } from '../../utils/teams';

/**
 * The building blocks the three pages share: a page title, a section title, a
 * stat tile and a team logo. Kept together because they are one visual system -
 * a red eyebrow over a condensed uppercase heading - and drift between pages is
 * what a shared component is for.
 */

/** Top of a page: red eyebrow, big condensed title, one line of explanation. */
export const PageIntro = ({ eyebrow, title, children, aside }) => (
  <div className="flex flex-col gap-6 pb-8 pt-10 md:flex-row md:items-end md:justify-between">
    <div className="max-w-2xl">
      <p className="eyebrow text-brand-text">{eyebrow}</p>
      <h2 className="mt-2 font-display text-5xl font-bold uppercase leading-[0.95] text-content sm:text-6xl">
        {title}
      </h2>
      {children && <p className="mt-4 text-base text-content-muted">{children}</p>}
    </div>
    {aside}
  </div>
);

/** A section within a page. */
export const SectionHead = ({ eyebrow, title, id, children }) => (
  <div className="mb-10 max-w-2xl">
    <p className="eyebrow text-brand-text">{eyebrow}</p>
    <h2 id={id} className="mt-2 font-display text-4xl font-bold uppercase text-content sm:text-5xl">
      {title}
    </h2>
    {children && <p className="mt-3 text-content-muted">{children}</p>}
  </div>
);

/** A labelled figure on a card. */
export const StatTile = ({ label, value, sub, tone, size = 'md' }) => (
  <div className="rounded-lg border border-edge bg-surface px-5 py-4">
    <dt className="eyebrow text-content-muted">{label}</dt>
    <dd className={`tnum mt-1 font-display font-bold ${size === 'lg' ? 'text-5xl' : 'text-3xl'} ${
      tone === 'success' ? 'text-success' : 'text-content'
    }`}>
      {value}
    </dd>
    {sub && <p className="text-xs text-content-muted">{sub}</p>}
  </div>
);

/**
 * A team's logo, from ESPN's CDN, falling back to its abbreviation in a disc
 * when there is no logo (TBD) or the image fails to load.
 */
export const TeamLogo = ({ team, size = 40, dim = false, className = '' }) => {
  const [failed, setFailed] = React.useState(false);
  const placeholder = !team || team === 'TBD';
  if (placeholder || failed) {
    return (
      <span
        aria-hidden="true"
        className={`grid flex-shrink-0 place-items-center rounded-full border border-edge bg-surface-elevated font-display text-xs font-bold text-content-muted ${className}`}
        style={{ width: size, height: size }}
      >
        {placeholder ? '?' : teamAbbreviation(team)}
      </span>
    );
  }
  return (
    <img
      src={teamLogo(team)}
      alt=""
      loading="lazy"
      width={size}
      height={size}
      onError={() => setFailed(true)}
      className={`flex-shrink-0 object-contain transition ${dim ? 'opacity-40 grayscale' : ''} ${className}`}
      style={{ width: size, height: size }}
    />
  );
};

/**
 * Split win-probability bar, away on the left. The accent marks the side the
 * model picked - never simply the home team - and the coin flip is marked.
 */
export const ProbabilityBar = ({ homeProbability, homePicked, thick = false }) => {
  const away = Math.round((1 - homeProbability) * 100);
  const home = 100 - away;
  return (
    <div className="flex items-center gap-3 font-display">
      <span className={`tnum w-10 text-sm font-semibold ${homePicked ? 'text-content-muted' : 'text-content'}`}>
        {away}%
      </span>
      <span data-probability-bar aria-hidden="true" className={`relative flex flex-1 gap-0.5 overflow-hidden rounded-full ${thick ? 'h-2.5' : 'h-1.5'}`}>
        <span className={`rounded-l-full ${homePicked ? 'bg-opposing' : 'bg-accent'}`} style={{ width: `${away}%` }} />
        <span className={`rounded-r-full ${homePicked ? 'bg-accent' : 'bg-opposing'}`} style={{ width: `${home}%` }} />
        <span className="absolute inset-y-0 left-1/2 w-px bg-content/40" />
      </span>
      <span className={`tnum w-10 text-right text-sm font-semibold ${homePicked ? 'text-content' : 'text-content-muted'}`}>
        {home}%
      </span>
    </div>
  );
};
