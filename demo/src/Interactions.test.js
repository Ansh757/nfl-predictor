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

// Navigation renders twice - header on desktop, bottom bar on mobile - and both
// are in the DOM at once, so target the first.
const nav = () => screen.getAllByRole('navigation', { name: /primary/i })[0];
const openPredictions = () => fireEvent.click(within(nav()).getByText('Predictions'));
const listLoaded = () => waitFor(() => expect(screen.getByText(/of 6$/)).toBeInTheDocument());

/**
 * The matchup cards, by accessible name.
 *
 * These used to be selected with /@|vs/i - matching the "@" between the team
 * abbreviations, which was only ever in the accessible name because the browser
 * concatenated every fragment inside the card into one. That is the behaviour
 * the card now sets out to avoid: it carries an explicit label instead, so a
 * screen reader hears one sentence rather than every number twice.
 *
 * Matching on the label shape asserts the card still has one. "at" pairs the
 * teams and "View analysis" ends it, so a card that lost its aria-label and
 * fell back to concatenation would not match.
 */
const matchupCards = () =>
  screen.getAllByRole('button', { name: /\bat\b.*View analysis/i });
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
    // Light is the default now - the warm paper palette is the design.
    expect(document.documentElement.dataset.theme).toBe('light');
    expect(toggle()).toHaveAccessibleName(/switch to dark theme/i);

    fireEvent.click(toggle());
    expect(document.documentElement.dataset.theme).toBe('dark');
    expect(toggle()).toHaveAccessibleName(/switch to light theme/i);

    fireEvent.click(toggle());
    expect(document.documentElement.dataset.theme).toBe('light');
  });

  test('remembers the choice', async () => {
    const { unmount } = render(<App />);
    await settle();
    fireEvent.click(toggle());
    expect(window.localStorage.getItem('nfl-predictor-theme')).toBe('dark');
    unmount();

    render(<App />);
    await settle();
    expect(document.documentElement.dataset.theme).toBe('dark');
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
    expect(document.documentElement.dataset.theme).toBe('light');
    fireEvent.click(toggle());
    expect(document.documentElement.dataset.theme).toBe('dark');
    getItem.mockRestore();
    setItem.mockRestore();
  });
});

describe('navigation', () => {
  test('every navigation item reaches its view', async () => {
    render(<App />);
    await waitFor(() => expect(screen.getByText(/Don't just predict the game/i)).toBeInTheDocument());

    fireEvent.click(within(nav()).getByText('Predictions'));
    await listLoaded();

    fireEvent.click(within(nav()).getByText('Playoffs'));
    expect(screen.getByText(/Current playoff picture/i)).toBeInTheDocument();

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

  test('the featured matchup opens the game it was advertising', async () => {
    // The featured card is the same MatchupCard the Predictions grid uses, so
    // clicking it must select that game rather than dump the reader in a list.
    render(<App />);
    await waitFor(() =>
      expect(screen.getByText(/Featured matchup/i)).toBeInTheDocument()
    );
    fireEvent.click(matchupCards()[0]);
    await waitFor(() =>
      expect(screen.getByText(/Official model pick/i)).toBeInTheDocument()
    );
    expect(screen.queryByText(/Select a game to see the multi-agent analysis/i))
      .not.toBeInTheDocument();
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
    openPredictions();
    await listLoaded();
    fireEvent.change(screen.getByLabelText('Search'), { target: { value: 'Packers' } });
    await waitFor(() => expect(screen.getByText(/of 1$/)).toBeInTheDocument());
  });

  test('the team filter narrows the list', async () => {
    render(<App />);
    openPredictions();
    await listLoaded();
    fireEvent.change(screen.getByLabelText('Team'), { target: { value: 'Chicago Bears' } });
    await waitFor(() => expect(screen.getByText(/of 1$/)).toBeInTheDocument());
  });

  test('the kickoff filter narrows the list', async () => {
    render(<App />);
    openPredictions();
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
    openPredictions();
    await listLoaded();
    await waitFor(() => expect(screen.getAllByText(/%$/).length).toBeGreaterThan(1));
    const firstBefore = matchupCards()[0];
    fireEvent.change(screen.getByLabelText('Sort'), { target: { value: 'confidence' } });
    // Highest confidence is the last game in the fixture, so the top card changes
    await waitFor(() => {
      const firstAfter = matchupCards()[0];
      expect(firstAfter.textContent).not.toBe(firstBefore.textContent);
    });
  });

  test('the week select refetches for that week', async () => {
    render(<App />);
    openPredictions();
    await listLoaded();
    fireEvent.change(screen.getByLabelText('Week'), { target: { value: '7' } });
    await waitFor(() =>
      expect(requested.some((url) => url.includes('/games/week/7'))).toBe(true)
    );
  });

  test('the season select refetches for that season', async () => {
    render(<App />);
    openPredictions();
    await listLoaded();
    fireEvent.change(screen.getByLabelText('Season'), { target: { value: '2023' } });
    await waitFor(() =>
      expect(requested.some((url) => url.includes('season=2023'))).toBe(true)
    );
  });

  test('refresh refetches the current week', async () => {
    render(<App />);
    openPredictions();
    await listLoaded();
    const before = requested.filter((url) => url.includes('/games/week/')).length;
    fireEvent.click(screen.getByRole('button', { name: /refresh/i }));
    await waitFor(() =>
      expect(requested.filter((url) => url.includes('/games/week/')).length)
        .toBeGreaterThan(before)
    );
  });

  test('a week that fits on one page has both controls disabled', async () => {
    render(<App />);
    openPredictions();
    await listLoaded();
    // Six games, eight to a page.
    expect(screen.getByText('1-6 of 6')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /previous page/i })).toBeDisabled();
    expect(screen.getByRole('button', { name: /next page/i })).toBeDisabled();
  });

  test('pagination moves through the pages and stops at the ends', async () => {
    // Its own fixture: a real week is sixteen games, which is more than one
    // page, and the shared six-game slate no longer exercises paging.
    const many = Array.from({ length: 14 }, (_, index) => ({
      game_id: 500 + index,
      season: 2026,
      week: 1,
      game_date: `2026-09-13T1${index % 8}:00:00Z`,
      home_team: TEAMS[index % TEAMS.length][1],
      away_team: TEAMS[index % TEAMS.length][0],
      venue: 'Stadium',
      is_dome: false,
    }));
    global.fetch = jest.fn((url) => {
      const href = String(url);
      if (href.includes('/games/week/')) {
        return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({ games: many }) });
      }
      if (href.includes('/predict')) {
        return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(predictionFor(1)) });
      }
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({ games: [] }) });
    });

    render(<App />);
    openPredictions();
    await waitFor(() => expect(screen.getByText('1-8 of 14')).toBeInTheDocument());

    const prev = screen.getByRole('button', { name: /previous page/i });
    const next = screen.getByRole('button', { name: /next page/i });
    expect(prev).toBeDisabled();

    fireEvent.click(next);
    await waitFor(() => expect(screen.getByText('9-14 of 14')).toBeInTheDocument());
    expect(next).toBeDisabled();

    fireEvent.click(prev);
    await waitFor(() => expect(screen.getByText('1-8 of 14')).toBeInTheDocument());
  });

  test('selecting a game opens its breakdown', async () => {
    render(<App />);
    openPredictions();
    await listLoaded();
    expect(screen.getByText(/Select a game to see the multi-agent analysis/i)).toBeInTheDocument();
    fireEvent.click(matchupCards()[0]);
    await waitFor(() => expect(screen.getByText(/Official model pick/i)).toBeInTheDocument());
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

  test.each([[undefined], ['Predictions'], ['Playoffs']])(
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

  test('no pick, simulator or scenario control exists anywhere', async () => {
    // The reference layout had PICK NE / PICK SEA buttons, a simulator tab and
    // saved scenarios. None of that belongs here: the model's pick does not
    // respond to a reader, and a control implying otherwise would be a lie
    // about what the application does.
    render(<App />);
    await settle();
    for (const view of ['Predictions', 'Playoffs']) {
      fireEvent.click(within(nav()).getByText(view));
      await waitFor(() => expect(screen.getAllByRole('button').length).toBeGreaterThan(0));
      expect(screen.queryByRole('button', { name: /^pick /i })).not.toBeInTheDocument();
      expect(screen.queryByText(/your pick/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/simulat/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/10,000/)).not.toBeInTheDocument();
    }
  });
});
