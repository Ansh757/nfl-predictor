import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import App from './App';
import { AGENTS } from './utils/performance';

/**
 * The Overview explains the product; it does not document the implementation.
 *
 * The previous version put five equal boxes of prose side by side, each with a
 * blurb, an accuracy and a weight - the whole weighting scheme exposed before
 * anyone had asked how it worked. These pin the replacement: a pipeline first,
 * the mechanics behind a disclosure.
 */
const week = {
  games: [{
    game_id: 1, season: 2026, week: 1, game_date: '2026-09-13T17:00:00Z',
    home_team: 'Buffalo Bills', away_team: 'New England Patriots',
    venue: 'Highmark Stadium', is_dome: false,
  }],
};
const prediction = {
  game_id: 1,
  overall_winner: 'Buffalo Bills',
  overall_confidence: 0.61,
  consensus_reasoning: 'Weighted consensus favours Buffalo Bills.',
  consensus_method: 'weighted',
  weighted_scores: { 'Buffalo Bills': 0.08 },
  agent_predictions: [{
    agent_name: 'Market Odds', predicted_winner: 'Buffalo Bills', confidence: 0.66,
    reasoning: 'Consensus of 9 sportsbooks. Seattle favored by 3.5.',
    weight: 0.164, contribution: 0.026, has_data: true,
  }],
};

beforeEach(() => {
  global.fetch = jest.fn((url) => {
    const href = String(url);
    if (href.includes('/games/week/')) {
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(week) });
    }
    if (href.includes('/predict')) {
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(prediction) });
    }
    return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({ games: [] }) });
  });
});

afterEach(() => jest.restoreAllMocks());

const pipeline = () => screen.getByRole('heading', { name: /how a pick is made/i }).closest('section');

describe('the methodology pipeline', () => {
  test('shows every agent with its measured accuracy', async () => {
    render(<App />);
    await waitFor(() => expect(screen.getByText(/how a pick is made/i)).toBeInTheDocument());
    // Scoped to the diagram itself: the same figures appear again inside the
    // closed detail, which is the point - the disclosure repeats them in full.
    const diagram = pipeline().querySelector('ol');
    for (const agent of AGENTS) {
      expect(within(diagram).getByText(`${(agent.accuracy * 100).toFixed(1)}%`)).toBeInTheDocument();
    }
    expect(within(diagram).getByText('Market')).toBeInTheDocument();
  });

  test('the mechanics are collapsed until asked for', async () => {
    // The whole point of the change: the weighting formula is available, not
    // presented before anyone wanted it.
    render(<App />);
    await waitFor(() => expect(screen.getByText(/how weighting works/i)).toBeInTheDocument());

    const details = screen.getByText(/how weighting works/i).closest('details');
    expect(details.open).toBe(false);
    expect(within(details).getByText(/weight × \(confidence − 0\.5\)/i)).toBeInTheDocument();
  });

  test('the disclosure opens, and is a native summary so it is keyboard operable', async () => {
    render(<App />);
    await waitFor(() => expect(screen.getByText(/how weighting works/i)).toBeInTheDocument());

    const summary = screen.getByText(/how weighting works/i).closest('summary');
    expect(summary).toBeInTheDocument();      // not a div with an onClick

    fireEvent.click(summary);
    expect(summary.closest('details').open).toBe(true);
  });

  test('the outcome node shows a real prediction, not a worked example', async () => {
    // An invented "SEA 55%" would be the only fabricated number on the page.
    render(<App />);
    await waitFor(() => expect(screen.getByText(/how a pick is made/i)).toBeInTheDocument());
    const section = pipeline();

    await waitFor(() => expect(within(section).getByText('NE @ BUF')).toBeInTheDocument());
    expect(within(section).getByText('BUF')).toBeInTheDocument();
    expect(within(section).getByText('61%')).toBeInTheDocument();
  });

  test('no agent blurb is shown before the disclosure is opened', async () => {
    render(<App />);
    await waitFor(() => expect(screen.getByText(/how a pick is made/i)).toBeInTheDocument());
    const section = pipeline();
    // Blurbs still exist - inside the closed <details> - but the collapsed
    // section must not be five paragraphs of prose.
    const details = within(section).getByText(/how weighting works/i).closest('details');
    for (const agent of AGENTS.slice(0, 2)) {
      expect(within(details).getByText(agent.blurb)).toBeInTheDocument();
    }
    expect(details.open).toBe(false);
  });
});
