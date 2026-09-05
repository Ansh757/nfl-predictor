import { formatKickoff, formatKickoffEastern, easternHint, kickoffParts } from './utils/time';

/**
 * Kickoff formatting, in the timezones that actually caused trouble.
 *
 * jsdom takes its zone from TZ at startup, so these drive toLocaleString
 * directly with an explicit zone rather than trying to restart the runtime.
 */
const KICKOFF = '2025-09-05T00:20Z';   // 8:20 PM ET, 5:20 PM PT

describe('formatKickoff', () => {
  test('always names a zone', () => {
    // The reported bug: a bare "5:20 PM" with nothing to say whose clock it was
    expect(formatKickoff(KICKOFF)).toMatch(/\d{1,2}:\d{2}\s?(AM|PM)\s+[A-Z]{2,5}/);
  });

  test('degrades to a readable string rather than throwing', () => {
    expect(formatKickoff('not a date')).toBe('Time TBD');
    expect(formatKickoff(undefined)).toBe('Time TBD');
  });
});

describe('formatKickoffEastern', () => {
  test('renders the league zone regardless of where it is called from', () => {
    expect(formatKickoffEastern(KICKOFF)).toBe('8:20 PM ET');
  });

  test('returns null for an unusable value', () => {
    expect(formatKickoffEastern('nonsense')).toBeNull();
  });
});

describe('easternHint', () => {
  const withZone = (zone, run) => {
    // Pin what the browser would resolve to, the way a viewer's machine does.
    const real = Date.prototype.toLocaleString;
    jest.spyOn(Date.prototype, 'toLocaleString').mockImplementation(function (locale, options) {
      return real.call(this, locale, { ...options, timeZone: options?.timeZone ?? zone });
    });
    try {
      return run();
    } finally {
      Date.prototype.toLocaleString.mockRestore();
    }
  };

  test('shows ET to a viewer on a different clock', () => {
    expect(withZone('America/Los_Angeles', () => easternHint(KICKOFF))).toBe('8:20 PM ET');
  });

  test('stays silent for a viewer already on Eastern', () => {
    expect(withZone('America/New_York', () => easternHint(KICKOFF))).toBeNull();
  });

  test('stays silent for Toronto, which is Eastern under another name', () => {
    // The bug this replaced compared IANA zone names, so America/Toronto - the
    // case the feature was built for - got "8:20 PM EDT · 8:20 PM ET".
    expect(withZone('America/Toronto', () => easternHint(KICKOFF))).toBeNull();
  });

  test('shows ET for a half-hour offset zone', () => {
    expect(withZone('America/St_Johns', () => easternHint(KICKOFF))).toBe('8:20 PM ET');
  });
});

describe('kickoffParts', () => {
  test('splits a kickoff into the pieces the matchup card lays out', () => {
    const parts = kickoffParts(KICKOFF);
    expect(parts.weekday).toMatch(/^[A-Z]{3}$/);
    expect(parts.date).toMatch(/^[A-Z]{3} \d{1,2}$/);
    // The zone stays attached, for the reason in the module header: a kickoff
    // without one is a kickoff a reader outside ET cannot act on.
    expect(parts.time).toMatch(/\d{1,2}:\d{2}\s?(AM|PM)\s+[A-Z]{2,5}/);
  });

  test('agrees with the one-line rendering it is a split of', () => {
    const parts = kickoffParts(KICKOFF);
    expect(formatKickoff(KICKOFF)).toContain(parts.time);
  });

  test('returns nothing rather than a broken date for junk', () => {
    // The card falls back to formatKickoff's "Time TBD" on null.
    expect(kickoffParts('not a date')).toBeNull();
    expect(kickoffParts(undefined)).toBeNull();
  });
});
