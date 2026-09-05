/**
 * Team abbreviations and logos.
 *
 * ESPN serves logos straight from its CDN keyed by abbreviation, so the
 * dashboard needs no asset pipeline and no backend change to show them.
 */
export const TEAM_ABBREVIATIONS = {
  'Arizona Cardinals': 'ARI', 'Atlanta Falcons': 'ATL', 'Baltimore Ravens': 'BAL',
  'Buffalo Bills': 'BUF', 'Carolina Panthers': 'CAR', 'Chicago Bears': 'CHI',
  'Cincinnati Bengals': 'CIN', 'Cleveland Browns': 'CLE', 'Dallas Cowboys': 'DAL',
  'Denver Broncos': 'DEN', 'Detroit Lions': 'DET', 'Green Bay Packers': 'GB',
  'Houston Texans': 'HOU', 'Indianapolis Colts': 'IND', 'Jacksonville Jaguars': 'JAX',
  'Kansas City Chiefs': 'KC', 'Las Vegas Raiders': 'LV', 'Los Angeles Chargers': 'LAC',
  'Los Angeles Rams': 'LAR', 'Miami Dolphins': 'MIA', 'Minnesota Vikings': 'MIN',
  'New England Patriots': 'NE', 'New Orleans Saints': 'NO', 'New York Giants': 'NYG',
  'New York Jets': 'NYJ', 'Philadelphia Eagles': 'PHI', 'Pittsburgh Steelers': 'PIT',
  'San Francisco 49ers': 'SF', 'Seattle Seahawks': 'SEA', 'Tampa Bay Buccaneers': 'TB',
  'Tennessee Titans': 'TEN', 'Washington Commanders': 'WSH'
};

export function teamAbbreviation(teamName = '') {
  return TEAM_ABBREVIATIONS[teamName] || teamName.slice(0, 3).toUpperCase();
}

export function teamLogo(teamName = '') {
  return `https://a.espncdn.com/i/teamlogos/nfl/500/${teamAbbreviation(teamName).toLowerCase()}.png`;
}

/** Confidence bands used for the badges and colour coding. */
export function confidenceBand(confidence) {
  if (confidence == null) return { label: '—', tone: 'muted' };
  if (confidence >= 0.7) return { label: 'HIGH', tone: 'success' };
  if (confidence >= 0.6) return { label: 'MEDIUM', tone: 'warning' };
  return { label: 'LOW', tone: 'muted' };
}

/**
 * Conference and division for all 32 teams.
 *
 * Reference data, not derived data - the same category as the abbreviations and
 * logo paths above, or the venue coordinates in the Python service. The API
 * does not return it and there is nothing to compute it from, but it is a fact
 * about the league rather than a guess about a season.
 */
export const TEAM_ALIGNMENT = {
  'Buffalo Bills':        { conference: 'AFC', division: 'East' },
  'Miami Dolphins':       { conference: 'AFC', division: 'East' },
  'New England Patriots': { conference: 'AFC', division: 'East' },
  'New York Jets':        { conference: 'AFC', division: 'East' },
  'Baltimore Ravens':     { conference: 'AFC', division: 'North' },
  'Cincinnati Bengals':   { conference: 'AFC', division: 'North' },
  'Cleveland Browns':     { conference: 'AFC', division: 'North' },
  'Pittsburgh Steelers':  { conference: 'AFC', division: 'North' },
  'Houston Texans':       { conference: 'AFC', division: 'South' },
  'Indianapolis Colts':   { conference: 'AFC', division: 'South' },
  'Jacksonville Jaguars': { conference: 'AFC', division: 'South' },
  'Tennessee Titans':     { conference: 'AFC', division: 'South' },
  'Denver Broncos':       { conference: 'AFC', division: 'West' },
  'Kansas City Chiefs':   { conference: 'AFC', division: 'West' },
  'Las Vegas Raiders':    { conference: 'AFC', division: 'West' },
  'Los Angeles Chargers': { conference: 'AFC', division: 'West' },
  'Dallas Cowboys':       { conference: 'NFC', division: 'East' },
  'New York Giants':      { conference: 'NFC', division: 'East' },
  'Philadelphia Eagles':  { conference: 'NFC', division: 'East' },
  'Washington Commanders':{ conference: 'NFC', division: 'East' },
  'Chicago Bears':        { conference: 'NFC', division: 'North' },
  'Detroit Lions':        { conference: 'NFC', division: 'North' },
  'Green Bay Packers':    { conference: 'NFC', division: 'North' },
  'Minnesota Vikings':    { conference: 'NFC', division: 'North' },
  'Atlanta Falcons':      { conference: 'NFC', division: 'South' },
  'Carolina Panthers':    { conference: 'NFC', division: 'South' },
  'New Orleans Saints':   { conference: 'NFC', division: 'South' },
  'Tampa Bay Buccaneers': { conference: 'NFC', division: 'South' },
  'Arizona Cardinals':    { conference: 'NFC', division: 'West' },
  'Los Angeles Rams':     { conference: 'NFC', division: 'West' },
  'San Francisco 49ers':  { conference: 'NFC', division: 'West' },
  'Seattle Seahawks':     { conference: 'NFC', division: 'West' },
};

export const conferenceOf = (team) => TEAM_ALIGNMENT[team]?.conference ?? null;
export const divisionOf = (team) => TEAM_ALIGNMENT[team]?.division ?? null;
