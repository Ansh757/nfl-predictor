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
 * time does not.
 *
 * Compares the rendered clock time rather than the zone name. Matching on the
 * IANA zone looked right and was wrong: America/Toronto is not
 * America/New_York, so a Toronto reader - the exact case this feature was
 * built for - was shown "8:20 PM EDT · 8:20 PM ET". Comparing what is actually
 * printed also handles the half-hour zones and the DST boundary for free.
 */
export const easternHint = (value) => {
  const date = toDate(value);
  if (!date) return null;
  try {
    const local = date.toLocaleString('en-US', TIME_PARTS);
    const eastern = date.toLocaleString('en-US', { ...TIME_PARTS, timeZone: EASTERN_ZONE });
    return local === eastern ? null : `${eastern} ET`;
  } catch {
    return null;
  }
};
