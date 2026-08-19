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
