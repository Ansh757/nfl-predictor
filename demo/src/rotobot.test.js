import React from 'react';
import { render, screen, within } from '@testing-library/react';
import RotobotPanel, { isProjection } from './components/predictions/RotobotPanel';
import { keyLine } from './utils/rotobot';

/**
 * The Rotobot panel shows projections; it must never become a control. It also
 * has to say plainly that its win probability is the market's, not the pick's.
 */
const player = (overrides) => ({
  player_id: 'p1', name: 'Josh Allen', position: 'QB', starter: true,
  stats: { passing_yards: 262.4, passing_tds: 1.84, passing_interceptions: 0.71, rushing_yards: 31.2,
    rushing_tds: 0.4, receptions: 0, receiving_yards: 0, receiving_tds: 0 },
  fantasy: { ppr: 21.6, half_ppr: 21.6, standard: 21.6 },
  ranges: { ppr: [11.2, 31.9] },
  actual_ppr: null,
  ...overrides,
});

const projection = (overrides = {}) => ({
  game_id: 7, home_team: 'Buffalo Bills', away_team: 'Los Angeles Rams',
  source: { spread: 'live_market', total: 'live_market' },
  anchor: { home_spread: -3.5, total: 47.5, home_implied_points: 25.5, away_implied_points: 22 },
  median: { home: 26, away: 21 },
  interval: { level: 0.8, home: [14, 37], away: [11, 33], margin: [-12, 19], total: [32, 63] },
  probabilities: { home_win: 0.604, away_win: 0.3935, tie: 0.0025, home_covers: 0.51, over: 0.48 },
  final: null,
  players: {
    available: true,
    home: { players: [player()], out: ['Dalton Kincaid'], injury_source: 'espn_live' },
    away: { players: [player({ player_id: 'p2', name: 'Puka Nacua', position: 'WR',
      stats: { receptions: 6.4, receiving_yards: 82.6, receiving_tds: 0.52, rushing_yards: 0, rushing_tds: 0,
        passing_yards: 0, passing_tds: 0, passing_interceptions: 0 },
      fantasy: { ppr: 17.9 }, ranges: { ppr: [7.4, 29.8] } })], out: [], injury_source: 'espn_live' },
  },
  ...overrides,
});

const serve = (body, ok = true) => {
  global.fetch = jest.fn(() => Promise.resolve({ ok, status: ok ? 200 : 500, json: () => Promise.resolve(body) }));
};

const GAME = { game_id: 7, home_team: 'Buffalo Bills', away_team: 'Los Angeles Rams' };

afterEach(() => jest.restoreAllMocks());

describe('RotobotPanel', () => {
  test('shows the projected score with its range, and labels the market as the market', async () => {
    serve(projection());
    render(<RotobotPanel game={GAME} apiUrl="http://api" />);
    const panel = await screen.findByRole('region', { name: /rotobot projection/i });
    await within(panel).findByText('26');
    expect(within(panel).getByText('80% range 14–37')).toBeInTheDocument();
    expect(within(panel).getByText(/separate from the five-agent pick/i)).toBeInTheDocument();
    expect(within(panel).getByText('Live betting market')).toBeInTheDocument();
    expect(global.fetch).toHaveBeenCalledWith('http://api/games/7/rotobot');
  });

  test('lists players with their line, PPR range and who is out', async () => {
    serve(projection());
    render(<RotobotPanel game={GAME} apiUrl="http://api" />);
    expect(await screen.findByText('Josh Allen')).toBeInTheDocument();
    // Rendered twice: in its own column, and under the name for phones (one is hidden by CSS)
    expect(screen.getAllByText('262 pass yds · 1.8 TD · 0.7 INT · 31 rush')).toHaveLength(2);
    expect(screen.getByText('11.2–31.9')).toBeInTheDocument();
    expect(screen.getByText(/Not projected \(injury report\): Dalton Kincaid/)).toBeInTheDocument();
    // Upcoming game: no "Actual" column
    expect(screen.queryByRole('columnheader', { name: 'Actual' })).not.toBeInTheDocument();
  });

  test('a played game shows the final and each player\'s actual points', async () => {
    const body = projection({ final: { home: 20, away: 31 } });
    body.players.home.players[0].actual_ppr = 14.2;
    body.players.away.players[0].actual_ppr = null;
    serve(body);
    render(<RotobotPanel game={GAME} apiUrl="http://api" />);
    expect(await screen.findByText('Final 20')).toBeInTheDocument();
    expect(screen.getAllByRole('columnheader', { name: 'Actual' })).toHaveLength(2);
    expect(screen.getByText('14.2')).toBeInTheDocument();
    expect(screen.getByText('Did not play')).toBeInTheDocument();
  });

  test('says so when the projection cannot be loaded', async () => {
    serve({}, false);
    render(<RotobotPanel game={GAME} apiUrl="http://api" />);
    expect(await screen.findByRole('alert')).toHaveTextContent(/could not load/i);
  });

  test('an unexpected response is an error state, not a crash', async () => {
    serve({ games: [] });
    render(<RotobotPanel game={GAME} apiUrl="http://api" />);
    expect(await screen.findByRole('alert')).toBeInTheDocument();
    expect(isProjection({ games: [] })).toBe(false);
    expect(isProjection(projection())).toBe(true);
  });

  test('it is a projection, not a control', async () => {
    serve(projection());
    render(<RotobotPanel game={GAME} apiUrl="http://api" />);
    const panel = await screen.findByRole('region', { name: /rotobot projection/i });
    await within(panel).findByText('Josh Allen');
    expect(within(panel).queryAllByRole('button')).toHaveLength(0);
    expect(within(panel).queryAllByRole('textbox')).toHaveLength(0);
    expect(within(panel).queryAllByRole('combobox')).toHaveLength(0);
    expect(within(panel).queryByText(/simulat/i)).not.toBeInTheDocument();
  });

  test('renders nothing without a selected game', () => {
    const { container } = render(<RotobotPanel game={null} apiUrl="http://api" />);
    expect(container).toBeEmptyDOMElement();
  });
});

describe('keyLine', () => {
  test('each position leads with the stat that position is drafted for', () => {
    expect(keyLine({ position: 'RB', stats: { rushing_yards: 71.6, receptions: 2.94, rushing_tds: 0.5, receiving_tds: 0.1 } }))
      .toBe('72 rush yds · 2.9 rec · 0.6 TD');
    expect(keyLine({ position: 'TE', stats: { receptions: 4.04, receiving_yards: 44.4, receiving_tds: 0.33 } }))
      .toBe('4 rec · 44 yds · 0.3 TD');
  });

  test('a receiver who carries the ball shows where his points come from', () => {
    expect(keyLine({ position: 'WR', stats: { receptions: 0, receiving_yards: 0, receiving_tds: 0,
      rushing_yards: 31.65, rushing_tds: 0.23 } })).toBe('0 rec · 0 yds · 32 rush · 0.2 TD');
  });
});
