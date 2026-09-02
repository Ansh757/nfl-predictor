/**
 * Kickoff formatting.
 *
 * The schedule stores kickoffs as UTC instants ("2025-09-05T00:20Z"), so the
 * browser renders them correctly in the viewer's own zone - but the dashboard
 * used to print "5:20 PM" with no zone attached. A reader in Toronto had no
 * way to tell whether that was their 5:20 or somebody else's, and for a game
 * that kicks off at 8:20 PM ET the page simply looked wrong.
 *
 * So every kickoff now carries its zone. The viewer's local time is the
 * headline, because that is the number they act on; ET is shown alongside it
 * wherever there is room, because that is the zone the NFL schedules in and
 * the one every broadcast quotes.
 */

export const EASTERN_ZONE = 'America/New_York';

const DATE_PARTS = { weekday: 'short', month: 'short', day: 'numeric' };
const TIME_PARTS = { hour: 'numeric', minute: '2-digit' };

const toDate = (value) => {
  if (value instanceof Date) return value;
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? null : date;
};

/** The viewer's IANA zone, or null where the runtime will not say. */
export const viewerTimeZone = () => {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || null;
  } catch {
    return null;
  }
};

/**
 * True when the viewer is already on Eastern time, in which case repeating the
 * ET conversion next to their local time would just be noise.
 */
export const viewerIsEastern = () => {
  const zone = viewerTimeZone();
  if (zone) return zone === EASTERN_ZONE;
  // No resolved zone to compare, so fall back to comparing the rendered
  // offset for a fixed instant.
  const probe = new Date('2025-09-07T17:00:00Z');
  try {
    return (
      probe.toLocaleString('en-US', { ...TIME_PARTS, timeZone: EASTERN_ZONE }) ===
      probe.toLocaleString('en-US', TIME_PARTS)
    );
  } catch {
    return false;
  }
};

/**
 * "Sun, Sep 7, 1:00 PM EDT" - the viewer's local time, always zone-labelled.
 * Falls back to an unlabelled time only if the runtime rejects timeZoneName,
 * which is better than rendering nothing.
 */
export const formatKickoff = (value) => {
  const date = toDate(value);
  if (!date) return 'Time TBD';
  try {
    return date.toLocaleString('en-US', { ...DATE_PARTS, ...TIME_PARTS, timeZoneName: 'short' });
  } catch {
    return date.toLocaleString('en-US', { ...DATE_PARTS, ...TIME_PARTS });
  }
};

/** "1:00 PM ET" - the same kickoff in the zone the league schedules in. */
export const formatKickoffEastern = (value) => {
  const date = toDate(value);
  if (!date) return null;
  try {
    return `${date.toLocaleString('en-US', { ...TIME_PARTS, timeZone: EASTERN_ZONE })} ET`;
  } catch {
    return null;
  }
};

/**
 * The ET rendering, but only when it tells the viewer something their local
 * time does not. Returns null for anyone already on Eastern.
 */
export const easternHint = (value) => (viewerIsEastern() ? null : formatKickoffEastern(value));
