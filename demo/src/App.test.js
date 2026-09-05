import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import App from './App';
import ErrorBoundary from './components/ErrorBoundary';

/**
 * These replace create-react-app's "renders learn react link" placeholder,
 * which tested nothing about this dashboard and had been failing since the app
 * was written.
 *
 * The cases below are the ones that would have caught real incidents: a render
 * error blanking the page, and an API outage being indistinguishable from a
 * quiet week.
 */

const week = {
  games: [
    {
      game_id: 1,
      season: 2026,
      week: 1,
      game_date: '2026-09-13T17:00:00Z',
      home_team: 'Buffalo Bills',
      away_team: 'New England Patriots',
      venue: 'Highmark Stadium',
      is_dome: false
    }
  ]
};

const prediction = {
  game_id: 1,
  overall_winner: 'Buffalo Bills',
  overall_confidence: 0.67,
  consensus_reasoning: 'Weighted consensus favors Buffalo Bills.',
  consensus_method: 'weighted',
  home_votes: 4,
  away_votes: 1,
  weighted_scores: { 'Buffalo Bills': 0.08, 'New England Patriots': 0.001 },
  agent_predictions: [
    {
      agent_name: 'Market Odds', predicted_winner: 'Buffalo Bills',
      confidence: 0.64, reasoning: 'Closing line.', weight: 0.164,
      contribution: 0.023, has_data: true
    },
    {
      agent_name: 'Injury Impact', predicted_winner: 'New England Patriots',
      confidence: 0.5, reasoning: 'No injury edge.', weight: 0.02,
      contribution: 0, has_data: false
    }
  ]
};

function mockApi({ weekOk = true, predictOk = true } = {}) {
  global.fetch = jest.fn((url, options) => {
    if (String(url).includes('/games/week/')) {
      return Promise.resolve({
        ok: weekOk, status: weekOk ? 200 : 503,
        json: () => Promise.resolve(week)
      });
    }
    if (String(url).includes('/predict')) {
      return Promise.resolve({
        ok: predictOk, status: predictOk ? 200 : 503,
        json: () => Promise.resolve(prediction)
      });
    }
    return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({ games: [] }) });
  });
}

afterEach(() => {
  jest.restoreAllMocks();
});

/**
 * Overview is the landing page, so the prediction views need a click first.
 * Navigation renders twice - header on desktop, bottom bar on mobile - and both
 * are in the DOM, so target the first.
 */
const openPredictions = () =>
  fireEvent.click(
    within(screen.getAllByRole('navigation', { name: /primary/i })[0]).getByText('Predictions')
  );

describe('dashboard', () => {
  test('renders without crashing and shows the week of games', async () => {
    mockApi();
    render(<App />);
    openPredictions();
    // The team name also appears in the filter dropdown, so assert on the
    // range the games list renders rather than the name alone
    await waitFor(() => expect(screen.getByText('1-1 of 1')).toBeInTheDocument());
  });

  test('navigation offers only views that actually render something', async () => {
    mockApi();
    render(<App />);
    const nav = screen.getAllByRole('navigation', { name: /primary/i })[0];
    expect(within(nav).getByText('Overview')).toBeInTheDocument();
    expect(within(nav).getByText('Predictions')).toBeInTheDocument();
    expect(within(nav).getByText('Playoffs')).toBeInTheDocument();
    // Exactly three sections. A simulator or performance tab would show here.
    expect(within(nav).queryByText(/simulator/i)).not.toBeInTheDocument();
    expect(within(nav).queryByText(/performance/i)).not.toBeInTheDocument();
  });

  test('every filter control is reachable by its label', async () => {
    mockApi();
    render(<App />);
    openPredictions();
    // getByLabelText only resolves when htmlFor/id actually pair up, so this
    // fails if the association regresses. None of these were associated before.
    await waitFor(() => expect(screen.getByLabelText('Search')).toBeInTheDocument());
    // Week lives in the navigator, not the filter bar - one control per
    // breakpoint - so it is looked up on its own.
    ['Team', 'Season', 'Kickoff', 'Sort'].forEach((name) =>
      expect(screen.getByLabelText(name)).toBeInTheDocument()
    );
    expect(screen.getByLabelText('Week')).toBeInTheDocument();
  });

  test('overview is a distinct landing page, not a copy of regular season', async () => {
    mockApi();
    render(<App />);
    // Landing content, and no games list
    await waitFor(() =>
      expect(screen.getByText(/Don't just predict the game/i)).toBeInTheDocument()
    );
    expect(screen.queryByText('1-1 of 1')).not.toBeInTheDocument();

    openPredictions();
    await waitFor(() => expect(screen.getByText('1-1 of 1')).toBeInTheDocument());
    expect(screen.queryByText(/Don't just predict the game/i)).not.toBeInTheDocument();
  });

  test('the landing page quotes measured numbers, not invented ones', async () => {
    mockApi();
    render(<App />);
    await waitFor(() => expect(screen.getByText(/Historical backtest performance/i)).toBeInTheDocument());
    // Real backtest figures; the design mockup showed 74.2% and 6,128 games.
    // 874: the neutral-site correction moved 2021 down, then calibrating the
    // injury agent from nflverse reports moved 2022-2024.
    expect(screen.getByText('1,359')).toBeInTheDocument();
    expect(screen.getByText('874')).toBeInTheDocument();
    expect(screen.queryByText(/74\.2%/)).not.toBeInTheDocument();
    expect(screen.queryByText('6,128')).not.toBeInTheDocument();
  });

  test('tells the user when the schedule service fails', async () => {
    // A 5xx is retried through the cold-start backoff before it is reported,
    // so drive the clock rather than sitting through eleven real seconds.
    jest.useFakeTimers();
    try {
      mockApi({ weekOk: false });
      render(<App />);
      openPredictions();
      // waitFor's timeout is measured in fake time too, so it has to cover the
      // whole backoff (3s + 8s) rather than the default one second.
      await waitFor(
        () => expect(screen.getByText(/Could not load games/i)).toBeInTheDocument(),
        { timeout: 20000 }
      );
      // The failure must not be mistaken for an empty week
      expect(screen.queryByText(/No games found/i)).not.toBeInTheDocument();
    } finally {
      jest.useRealTimers();
    }
  });

  test('a rate-limited prediction retries instead of showing a failure', async () => {
    // A week loads all its games at once, so a burst is normal traffic. The
    // first version rendered a red "Prediction unavailable · returned 429" for
    // something that clears on its own.
    let predictCalls = 0;
    global.fetch = jest.fn((url) => {
      if (String(url).includes('/games/week/')) {
        return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(week) });
      }
      if (String(url).includes('/predict')) {
        predictCalls += 1;
        if (predictCalls === 1) {
          return Promise.resolve({
            ok: false, status: 429,
            headers: { get: () => '1' },
            json: () => Promise.resolve({})
          });
        }
        return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(prediction) });
      }
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({ games: [] }) });
    });

    render(<App />);
    openPredictions();
    await waitFor(() => expect(screen.getByText('1-1 of 1')).toBeInTheDocument());
    await waitFor(() => expect(predictCalls).toBeGreaterThan(1), { timeout: 8000 });
    expect(screen.queryByText(/returned 429/)).not.toBeInTheDocument();
  }, 15000);

  test('a 4xx is reported at once instead of sitting through the retries', async () => {
    // The cold-start backoff exists for a service that is still booting. A
    // 404 is an answer, so waiting on it would only make the page look hung.
    global.fetch = jest.fn((url) => {
      if (String(url).includes('/games/week/')) {
        return Promise.resolve({ ok: false, status: 404, json: () => Promise.resolve({}) });
      }
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({ games: [] }) });
    });
    render(<App />);
    openPredictions();
    await waitFor(() => expect(screen.getByText(/Could not load games/i)).toBeInTheDocument());
    expect(screen.getByText(/returned 404/i)).toBeInTheDocument();
    const weekCalls = global.fetch.mock.calls.filter(([url]) =>
      String(url).includes('/games/week/')
    );
    expect(weekCalls).toHaveLength(1);
  });

  test('kickoff times carry a timezone', async () => {
    mockApi();
    render(<App />);
    openPredictions();
    // A bare "1:00 PM" is unreadable to anyone who cannot tell which zone
    // resolved it, and looks factually wrong to everyone else.
    await waitFor(() => expect(screen.getByText('1-1 of 1')).toBeInTheDocument());
    const kickoff = screen.getAllByText(/\d{1,2}:\d{2}\s?(AM|PM)/i)[0];
    expect(kickoff.textContent).toMatch(/(AM|PM)\s+[A-Z]{2,5}$/);
  });

  test('carries the prediction disclaimer sitewide', async () => {
    mockApi();
    render(<App />);
    await waitFor(() =>
      expect(
        screen.getAllByText(/Not financial or betting advice/i).length
      ).toBeGreaterThan(0)
    );
  });

  test('labels the headline accuracy as historical, not promised', async () => {
    mockApi();
    render(<App />);
    await waitFor(() => expect(screen.getByText(/2025 backtest accuracy/i)).toBeInTheDocument());
    // Historical and live are labelled as different measurements, side by side.
    expect(screen.getByText('2026 live accuracy')).toBeInTheDocument();
    expect(screen.getByText(/These are two different measurements/i)).toBeInTheDocument();
  });
});

describe('playoffs', () => {
  const completed = { games: [
    { game_id: 1, round: 'Wild Card', away_team: 'Los Angeles Rams', home_team: 'Carolina Panthers',
      away_score: 34, home_score: 31, game_date: '2026-01-10T18:00:00Z' },
    { game_id: 2, round: 'Super Bowl', away_team: 'New England Patriots', home_team: 'Seattle Seahawks',
      away_score: 28, home_score: 31, game_date: '2026-02-08T23:30:00Z' }
  ]};
  const unset = { games: [
    { game_id: 9, round: 'Wild Card', away_team: 'TBD', home_team: 'TBD',
      away_score: null, home_score: null, game_date: '2027-01-09T18:00:00Z' }
  ]};

  const mockPlayoffs = (payload) => {
    global.fetch = jest.fn((url) => Promise.resolve({
      ok: true, status: 200,
      json: () => Promise.resolve(String(url).includes('/playoffs/') ? payload : { games: [] })
    }));
  };

  test('a completed bracket shows real teams and scores', async () => {
    mockPlayoffs(completed);
    render(<App />);
    fireEvent.click(screen.getAllByText('Playoffs')[0]);
    await waitFor(() => expect(screen.getByText('Wild Card')).toBeInTheDocument());
    expect(screen.getByText('LAR')).toBeInTheDocument();
    expect(screen.getByText('34')).toBeInTheDocument();
    // The final used to appear twice, as both "Super Bowl" and "Championship"
    expect(screen.getAllByText('Super Bowl')).toHaveLength(1);
    expect(screen.queryByText('Championship')).not.toBeInTheDocument();
  });

  test('an unset bracket says so instead of listing TBD rows', async () => {
    mockPlayoffs(unset);
    render(<App />);
    fireEvent.click(screen.getAllByText('Playoffs')[0]);
    await waitFor(() =>
      expect(screen.getByText(/Bracket not set yet/i)).toBeInTheDocument()
    );
  });
});

describe('ErrorBoundary', () => {
  const Boom = () => {
    throw new Error('kaboom');
  };

  test('shows the error instead of a blank page', () => {
    jest.spyOn(console, 'error').mockImplementation(() => {});
    render(
      <ErrorBoundary>
        <Boom />
      </ErrorBoundary>
    );
    expect(screen.getByText(/Something broke while rendering/i)).toBeInTheDocument();
    expect(screen.getByText(/kaboom/)).toBeInTheDocument();
  });

  test('renders children when nothing throws', () => {
    render(
      <ErrorBoundary>
        <p>all good</p>
      </ErrorBoundary>
    );
    expect(screen.getByText('all good')).toBeInTheDocument();
  });
});
