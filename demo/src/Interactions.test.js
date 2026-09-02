import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import App from './App';

/**
 * Every control on the page, clicked.
 *
 * Prompted by two reports from a user: the theme toggle did nothing, and "some
 * other button" did nothing either. Both were real - the toggle flipped a state
 * variable no surface read, and there were two Settings buttons with no handler
 * at all. Neither was covered, because the existing suite tested rendering and
 * data, not interaction.
 *
 * So this file clicks things. If a control is added without wiring, the sweep
 * at the bottom fails.
 */

const TEAMS = [
  ['New England Patriots', 'Buffalo Bills'],
  ['Dallas Cowboys', 'Philadelphia Eagles'],
  ['Green Bay Packers', 'Chicago Bears'],
  ['Kansas City Chiefs', 'Denver Broncos'],
  ['Seattle Seahawks', 'San Francisco 49ers'],
  ['Miami Dolphins', 'New York Jets']
];

const games = TEAMS.map(([away, home], index) => ({
  game_id: index + 1,
  season: 2026,
  week: 1,
  // Spread across the day so the kickoff filter has something to bite on
  game_date: `2026-09-13T${String(6 + index * 3).padStart(2, '0')}:00:00Z`,
  home_team: home,
  away_team: away,
  venue: `${home} Stadium`,
  is_dome: false
}));

const predictionFor = (gameId) => ({
  game_id: gameId,
  overall_winner: games[gameId - 1].home_team,
  overall_confidence: 0.5 + gameId * 0.05,
  consensus_reasoning: 'Weighted consensus.',
  consensus_method: 'weighted',
  weighted_scores: { [games[gameId - 1].home_team]: 0.08 },
  agent_predictions: [{
    agent_name: 'Market Odds', predicted_winner: games[gameId - 1].home_team,
    confidence: 0.64, reasoning: 'Closing line.', weight: 0.164,
    contribution: 0.023, has_data: true
  }]
});

let requested;

const mockApi = () => {
  requested = [];
  global.fetch = jest.fn((url, options) => {
    const href = String(url);
    requested.push(href);
    if (href.includes('/games/week/')) {
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({ games }) });
    }
    if (href.includes('/predict')) {
      const body = JSON.parse(options.body);
      return Promise.resolve({
        ok: true, status: 200,
        json: () => Promise.resolve(predictionFor(body.game_data.game_id))
      });
    }
    return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({ games: [] }) });
  });
};

beforeEach(() => {
  window.localStorage.clear();
  delete document.documentElement.dataset.theme;
  mockApi();
});

afterEach(() => {
  jest.restoreAllMocks();
});

const nav = () => screen.getByRole('navigation', { name: /primary/i });
const openRegularSeason = () => fireEvent.click(within(nav()).getByText('Regular Season'));
const listLoaded = () => waitFor(() => expect(screen.getByText(/of 6$/)).toBeInTheDocument());
/**
 * Render kicks off the schedule fetch and a prediction per game. A test that
 * asserts synchronously and returns leaves those resolving into an unmounted
 * tree, which React reports as an act() warning - noise that buries real
 * failures. Waiting for the landing page to paint settles them.
 */
const settle = () =>
  waitFor(() => expect(screen.getByText(/Don't just predict the game/i)).toBeInTheDocument());

describe('theme toggle', () => {
  const toggle = () => screen.getByRole('button', { name: /switch to (light|dark) theme/i });

  test('actually changes the theme, and is not just an icon that flips', async () => {
    render(<App />);
    await settle();
    // The bug: isDarkMode moved, every surface stayed hardcoded dark.
    expect(document.documentElement.dataset.theme).toBe('dark');
    expect(toggle()).toHaveAccessibleName(/switch to light theme/i);

    fireEvent.click(toggle());
    expect(document.documentElement.dataset.theme).toBe('light');
    expect(toggle()).toHaveAccessibleName(/switch to dark theme/i);

    fireEvent.click(toggle());
    expect(document.documentElement.dataset.theme).toBe('dark');
  });

  test('remembers the choice', async () => {
    const { unmount } = render(<App />);
    await settle();
    fireEvent.click(toggle());
    expect(window.localStorage.getItem('nfl-predictor-theme')).toBe('light');
    unmount();

    render(<App />);
    await settle();
    expect(document.documentElement.dataset.theme).toBe('light');
  });

  test('survives storage being unavailable', async () => {
    // Safari private mode throws on both read and write.
    const getItem = jest.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('denied');
    });
    const setItem = jest.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('denied');
    });
    render(<App />);
    await settle();
    expect(document.documentElement.dataset.theme).toBe('dark');
    fireEvent.click(toggle());
    expect(document.documentElement.dataset.theme).toBe('light');
    getItem.mockRestore();
    setItem.mockRestore();
  });
});

describe('navigation', () => {
  test('every sidebar item reaches its view', async () => {
    render(<App />);
    await waitFor(() => expect(screen.getByText(/Don't just predict the game/i)).toBeInTheDocument());

    fireEvent.click(within(nav()).getByText('Regular Season'));
    await listLoaded();

    fireEvent.click(within(nav()).getByText('Playoffs'));
    expect(screen.getByText(/Playoff bracket/i)).toBeInTheDocument();

    fireEvent.click(within(nav()).getByText('Overview'));
    expect(screen.getByText(/Don't just predict the game/i)).toBeInTheDocument();
  });
});

describe('landing page buttons', () => {
  test('"Explore predictions" opens the games view', async () => {
    render(<App />);
    await waitFor(() => expect(screen.getByText('Explore predictions')).toBeInTheDocument());
    fireEvent.click(screen.getByText('Explore predictions'));
    await listLoaded();
  });

  test('"View Week N predictions" opens the games view', async () => {
    render(<App />);
    await waitFor(() => expect(screen.getByText(/View Week 1 predictions/i)).toBeInTheDocument());
    fireEvent.click(screen.getByText(/View Week 1 predictions/i));
    await listLoaded();
  });

  test('"View full analysis" opens the game it was advertising', async () => {
    // It used to switch view and abandon the reader in the list, with no game
    // selected and nothing to say which one had been featured.
    render(<App />);
    await waitFor(() => expect(screen.getByText(/View full analysis/i)).toBeInTheDocument());
    fireEvent.click(screen.getByText(/View full analysis/i));
    await waitFor(() =>
      expect(screen.getByText(/Predicted winner/i)).toBeInTheDocument()
    );
    // The featured game is the first in the list - its detail, not a prompt to pick one
    expect(screen.queryByText(/Select a game to see the breakdown/i)).not.toBeInTheDocument();
  });

  test('the source link points somewhere real', async () => {
    render(<App />);
    await waitFor(() => expect(screen.getByText('Source')).toBeInTheDocument());
    const link = screen.getByText('Source').closest('a');
    expect(link).toHaveAttribute('href', expect.stringContaining('github.com'));
    expect(link).toHaveAttribute('rel', expect.stringContaining('noreferrer'));
  });
});

describe('games view controls', () => {
  test('search narrows the list', async () => {
    render(<App />);
    openRegularSeason();
    await listLoaded();
    fireEvent.change(screen.getByLabelText('Search'), { target: { value: 'Packers' } });
    await waitFor(() => expect(screen.getByText(/of 1$/)).toBeInTheDocument());
  });

  test('the team filter narrows the list', async () => {
    render(<App />);
    openRegularSeason();
    await listLoaded();
    fireEvent.change(screen.getByLabelText('Team'), { target: { value: 'Chicago Bears' } });
    await waitFor(() => expect(screen.getByText(/of 1$/)).toBeInTheDocument());
  });

  test('the kickoff filter narrows the list', async () => {
    render(<App />);
    openRegularSeason();
    await listLoaded();
    // Derive the expected bucket the same way the app does, so this holds in
    // whatever timezone the suite happens to run in.
    const bucketOf = (iso) => {
      const hour = new Date(iso).getHours();
      return hour < 12 ? 'morning' : hour < 18 ? 'afternoon' : 'evening';
    };
    const buckets = games.map((game) => bucketOf(game.game_date));
    const target = buckets[0];
    const expected = buckets.filter((bucket) => bucket === target).length;
    fireEvent.change(screen.getByLabelText('Kickoff'), { target: { value: target } });
    await waitFor(() =>
      expect(screen.getByText(new RegExp(`of ${expected}$`))).toBeInTheDocument()
    );
  });

  test('sorting by confidence reorders the list', async () => {
    render(<App />);
    openRegularSeason();
    await listLoaded();
    await waitFor(() => expect(screen.getAllByText(/%$/).length).toBeGreaterThan(1));
    const firstBefore = screen.getAllByRole('button', { name: /@|vs/i })[0];
    fireEvent.change(screen.getByLabelText('Sort'), { target: { value: 'confidence' } });
    // Highest confidence is the last game in the fixture, so the top card changes
    await waitFor(() => {
      const firstAfter = screen.getAllByRole('button', { name: /@|vs/i })[0];
      expect(firstAfter.textContent).not.toBe(firstBefore.textContent);
    });
  });

  test('the week select refetches for that week', async () => {
    render(<App />);
    openRegularSeason();
    await listLoaded();
    fireEvent.change(screen.getByLabelText('Week'), { target: { value: '7' } });
    await waitFor(() =>
      expect(requested.some((url) => url.includes('/games/week/7'))).toBe(true)
    );
  });

  test('the season select refetches for that season', async () => {
    render(<App />);
    openRegularSeason();
    await listLoaded();
    fireEvent.change(screen.getByLabelText('Season'), { target: { value: '2023' } });
    await waitFor(() =>
      expect(requested.some((url) => url.includes('season=2023'))).toBe(true)
    );
  });

  test('refresh refetches the current week', async () => {
    render(<App />);
    openRegularSeason();
    await listLoaded();
    const before = requested.filter((url) => url.includes('/games/week/')).length;
    fireEvent.click(screen.getByRole('button', { name: /refresh/i }));
    await waitFor(() =>
      expect(requested.filter((url) => url.includes('/games/week/')).length)
        .toBeGreaterThan(before)
    );
  });

  test('pagination moves through the pages and stops at the ends', async () => {
    render(<App />);
    openRegularSeason();
    await listLoaded();
    const prev = screen.getByRole('button', { name: /previous page/i });
    const next = screen.getByRole('button', { name: /next page/i });

    expect(prev).toBeDisabled();          // page 1 of 2, six games at four a page
    expect(screen.getByText('1-4 of 6')).toBeInTheDocument();

    fireEvent.click(next);
    await waitFor(() => expect(screen.getByText('5-6 of 6')).toBeInTheDocument());
    expect(next).toBeDisabled();

    fireEvent.click(prev);
    await waitFor(() => expect(screen.getByText('1-4 of 6')).toBeInTheDocument());
  });

  test('selecting a game opens its breakdown', async () => {
    render(<App />);
    openRegularSeason();
    await listLoaded();
    expect(screen.getByText(/Select a game to see the breakdown/i)).toBeInTheDocument();
    fireEvent.click(screen.getAllByRole('button', { name: /@/ })[0]);
    await waitFor(() => expect(screen.getByText(/Predicted winner/i)).toBeInTheDocument());
  });
});

describe('playoffs view controls', () => {
  test('the season select refetches that postseason', async () => {
    render(<App />);
    fireEvent.click(within(nav()).getByText('Playoffs'));
    await waitFor(() => expect(screen.getByLabelText('Playoff season')).toBeInTheDocument());
    fireEvent.change(screen.getByLabelText('Playoff season'), { target: { value: '2022' } });
    await waitFor(() =>
      expect(requested.some((url) => url.includes('/playoffs/2022'))).toBe(true)
    );
  });
});

describe('no dead controls', () => {
  const sweep = async (view) => {
    render(<App />);
    await settle();
    if (view) fireEvent.click(within(nav()).getByText(view));
    await waitFor(() => expect(screen.getAllByRole('button').length).toBeGreaterThan(0));
    return screen.getAllByRole('button');
  };

  test.each([[undefined], ['Regular Season'], ['Playoffs']])(
    'every button on %s has an accessible name and a handler',
    async (view) => {
      const buttons = await sweep(view);
      buttons.forEach((button) => {
        const name = button.getAttribute('aria-label') || button.textContent.trim();
        expect(name).not.toBe('');
        // React attaches listeners at the root, so a handler is not visible on
        // the node. What is visible is the prop React records on the fiber.
        const fiberKey = Object.keys(button).find((key) => key.startsWith('__reactProps$'));
        expect(button[fiberKey].onClick).toBeInstanceOf(Function);
      });
    }
  );

  test('the Settings buttons that did nothing are gone', async () => {
    render(<App />);
    await settle();
    expect(screen.queryByRole('button', { name: /settings/i })).not.toBeInTheDocument();
  });
});
