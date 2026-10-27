import React from 'react';
import { render, screen, within } from '@testing-library/react';
import LiveRecord from './components/overview/LiveRecord';
import { outcomeOf, summarizeByWeek, totals } from './utils/liveRecord';

/**
 * The live record is the one measurement on the page that cannot have been
 * tuned on the games it is scored against, so its arithmetic has to be right:
 * a tie is not a miss and an unplayed game is not a miss.
 */
const pick = (week, gameId, extra) => ({
  game_id: gameId,
  week,
  home_team: 'Seattle Seahawks',
  away_team: 'New England Patriots',
  predicted_winner: 'Seattle Seahawks',
  confidence: 0.547,
  settled: true,
  was_correct: true,
  tie: false,
  ...extra,
});

const season = [
  pick(1, 1),
  pick(1, 2, { was_correct: false }),
  pick(5, 3, { was_correct: null, tie: true }),
  pick(5, 4),
  pick(6, 5, { settled: false, was_correct: null }),
];

describe('outcomes', () => {
  test('each state reads as its own outcome', () => {
    expect(season.map(outcomeOf)).toEqual(['correct', 'wrong', 'tie', 'correct', 'pending']);
  });
});

describe('weekly tally', () => {
  test('newest week first', () => {
    expect(summarizeByWeek(season).map((w) => w.week)).toEqual([6, 5, 1]);
  });

  test('a tie and an unplayed game are not in the denominator', () => {
    const [week6, week5, week1] = summarizeByWeek(season);
    expect(week1).toMatchObject({ correct: 1, scored: 2, accuracy: 0.5 });
    expect(week5).toMatchObject({ correct: 1, scored: 1, ties: 1, accuracy: 1 });
    expect(week6).toMatchObject({ correct: 0, scored: 0, pending: 1, accuracy: null });
  });

  test('season totals add up the same way', () => {
    expect(totals(summarizeByWeek(season))).toEqual({
      correct: 2, scored: 3, pending: 1, ties: 1, accuracy: 2 / 3,
    });
  });
});

describe('LiveRecord', () => {
  test('renders nothing until the record has been asked for', () => {
    const { container } = render(<LiveRecord record={null} season={2026} />);
    expect(container).toBeEmptyDOMElement();
  });

  test('says so when the record cannot be loaded, rather than showing zeros', () => {
    render(<LiveRecord record={{ status: 'unavailable' }} season={2026} />);
    expect(screen.getByText(/could not be loaded/i)).toBeInTheDocument();
    expect(screen.queryByText('0 of 0')).not.toBeInTheDocument();
  });

  test('shows the season tally and each outcome as a word', () => {
    render(<LiveRecord record={{ status: 'ok', data: { predictions: season } }} season={2026} />);
    const section = screen.getByRole('region', { name: /2026 live record/i });
    expect(within(section).getByText('2 of 3')).toBeInTheDocument();
    expect(within(section).getByText('66.7%')).toBeInTheDocument();
    expect(within(section).getAllByText('Model correct')).toHaveLength(2);
    expect(within(section).getByText('Model wrong')).toBeInTheDocument();
    expect(within(section).getByText(/Tie - not scored/)).toBeInTheDocument();
  });
});
