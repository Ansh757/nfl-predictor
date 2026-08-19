import { render, screen, waitFor } from '@testing-library/react';
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

describe('dashboard', () => {
  test('renders without crashing and shows the week of games', async () => {
    mockApi();
    render(<App />);
    // The team name also appears in the filter dropdown, so assert on the
    // matchup count the games list renders rather than the name alone
    await waitFor(() =>
      expect(screen.getByText(/Showing 1-1 of 1 matchups/i)).toBeInTheDocument()
    );
  });

  test('offers only tabs that actually render something', async () => {
    mockApi();
    render(<App />);
    expect(screen.getByText('Regular Season')).toBeInTheDocument();
    expect(screen.getByText('Playoffs')).toBeInTheDocument();
    // Both of these were selectable and rendered a blank page
    expect(screen.queryByText('Trends')).not.toBeInTheDocument();
    expect(screen.queryByText('Compare')).not.toBeInTheDocument();
  });

  test('every filter control is reachable by its label', async () => {
    mockApi();
    render(<App />);
    // getByLabelText only resolves when htmlFor/id actually pair up, so this
    // fails if the association regresses. None of these were associated before.
    await waitFor(() => expect(screen.getByLabelText('Search')).toBeInTheDocument());
    ['Team', 'Season', 'Week', 'Kickoff', 'Sort'].forEach((name) =>
      expect(screen.getByLabelText(name)).toBeInTheDocument()
    );
  });

  test('tells the user when the schedule service fails', async () => {
    mockApi({ weekOk: false });
    render(<App />);
    await waitFor(() =>
      expect(screen.getByText(/Could not load games/i)).toBeInTheDocument()
    );
    // The failure must not be mistaken for an empty week
    expect(screen.queryByText(/No games found/i)).not.toBeInTheDocument();
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
