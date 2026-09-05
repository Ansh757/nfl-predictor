import { fireEvent, render, screen, within } from '@testing-library/react';
import SelectedGameAnalysis from './components/predictions/SelectedGameAnalysis';
import { formatKickoff } from './utils/time';

/**
 * The "Why SEA?" panel - the section that shows the agents disagreeing and the
 * vote resolving it. The redesign's job was to keep all of that available while
 * making the comparison readable without committing to five paragraphs first.
 */
const GAME = {
  game_id: 1,
  game_date: '2026-09-13T17:00:00Z',
  home_team: 'Seattle Seahawks',
  away_team: 'New England Patriots',
  venue: 'Lumen Field',
};

const AGENTS = [
  { key: 'market', label: 'Market Odds' },
  { key: 'stats', label: 'Basic Predictor' },
  { key: 'injuries', label: 'Injury Impact' },
];

const SUMMARY = {
  winner: 'Seattle Seahawks',
  confidence: 0.55,
  reasoning: 'Weighted consensus favours Seattle Seahawks.',
  consensus: { count: 2, total: 3, label: '2/3 agents', winnerInfluence: 0.62 },
  agentInsights: {
    market: {
      label: 'Market Odds',
      predictedWinner: 'Seattle Seahawks',
      confidence: 0.63,
      reasoning: 'Consensus of 9 sportsbooks. Seattle Seahawks favored by 3.5. '
        + 'Fair moneyline gives Seattle Seahawks a 63% win probability. Vig removed (overround 1.043).',
      weight: 0.164, contribution: 0.0213, influenceShare: 0.37, hasData: true,
    },
    stats: {
      label: 'Basic Predictor',
      predictedWinner: 'New England Patriots',
      confidence: 0.625,
      reasoning: 'Using real game_log data. New England Patriots on a 3-game run.',
      weight: 0.111, contribution: 0.0139, influenceShare: 0.24, hasData: true,
    },
    injuries: {
      label: 'Injury Impact',
      predictedWinner: 'Seattle Seahawks',
      confidence: 0.5,
      reasoning: 'Injury feed unavailable. No injury signal applied.',
      weight: 0.055, contribution: 0, influenceShare: 0, hasData: false,
    },
  },
};

const draw = (props = {}) => render(
  <SelectedGameAnalysis
    game={GAME}
    summary={SUMMARY}
    isPredicting={false}
    agentDefinitions={AGENTS}
    formatTime={formatKickoff}
    {...props}
  />
);

const cardFor = (label) =>
  screen.getByText(label).closest('div.rounded-lg');

describe('the agent comparison', () => {
  test('each agent states who it picked, so the disagreement is scannable', () => {
    draw();
    expect(within(cardFor('Market Odds')).getByText('SEA')).toBeInTheDocument();
    expect(within(cardFor('Basic Predictor')).getByText('NE')).toBeInTheDocument();
  });

  test('a dissenting agent is not dressed as an agreeing one', () => {
    draw();
    expect(within(cardFor('Market Odds')).getByText('SEA').className).toMatch(/text-accent/);
    expect(within(cardFor('Basic Predictor')).getByText('NE').className)
      .toMatch(/text-content-secondary/);
  });

  test('confidence and influence are shown as the different measurements they are', () => {
    // The most useful thing this panel says: an agent can be sure and still
    // move nothing, because weight is measured accuracy.
    const card = (draw(), cardFor('Market Odds'));
    expect(within(card).getByText('63%')).toBeInTheDocument();
    expect(within(card).getByText('Influence')).toBeInTheDocument();
    expect(within(card).getByText('37%')).toBeInTheDocument();
  });

  test('the confidence bar is drawn on the scale the number is on', () => {
    // It used to scale (confidence - 0.5) x 200, so a 63% agent drew a bar 26%
    // wide directly beside the number "63%".
    draw();
    const fill = cardFor('Market Odds').querySelector('.bg-accent[style]');
    expect(fill.style.width).toBe('63%');
  });
});

describe('progressive disclosure', () => {
  test('the summary shows at most three factors', () => {
    draw();
    const card = cardFor('Market Odds');
    const summaryList = card.querySelector('ul');
    expect(within(summaryList).getAllByRole('listitem')).toHaveLength(3);
    expect(within(summaryList).getByText('Consensus of 9 sportsbooks')).toBeInTheDocument();
  });

  test('the remaining factors are kept, not dropped', () => {
    // Four factors in, three shown - the fourth has to still be reachable or
    // this is summarisation, which is not what the panel claims to do.
    draw();
    const details = within(cardFor('Market Odds')).getByText('Details').closest('details');
    expect(within(details).getByText('Vig removed (overround 1.043)')).toBeInTheDocument();
  });

  test('the diagnostics start collapsed and open on click', () => {
    draw();
    const details = within(cardFor('Market Odds')).getByText('Details').closest('details');
    expect(details.open).toBe(false);
    expect(within(details).getByText('Weight')).toBeInTheDocument();
    expect(within(details).getByText('0.164')).toBeInTheDocument();

    fireEvent.click(within(details).getByText('Details'));
    expect(details.open).toBe(true);
  });

  test('the control is a real summary element, so it is keyboard operable', () => {
    draw();
    expect(within(cardFor('Market Odds')).getByText('Details').closest('summary'))
      .toBeInTheDocument();
  });
});

describe('layout', () => {
  test('cards size to their own content', () => {
    // With the grid row stretched, opening one card's Details inflated every
    // other card in its row with empty space.
    draw();
    const grid = screen.getByText('Market Odds').closest('.grid');
    expect(grid.className).toContain('items-start');
  });

  test('the coin flip is marked on every confidence bar', () => {
    // 52% and 66% are very different reads, and the distance past this line is
    // the whole of it.
    draw();
    for (const label of ['Market Odds', 'Basic Predictor']) {
      expect(cardFor(label).querySelector('.left-1\\/2')).toBeInTheDocument();
    }
  });
});

describe('an agent with no data', () => {
  test('says so rather than showing a 50% that looks like a read', () => {
    draw();
    const card = cardFor('Injury Impact');
    expect(within(card).getByText('No data')).toBeInTheDocument();
    expect(within(card).getByText('—')).toBeInTheDocument();
    expect(within(card).getByText('none')).toBeInTheDocument();
  });

  test('its factors are not ticked', () => {
    // A tick beside "Injury feed unavailable" reads as confirming it.
    draw();
    const card = cardFor('Injury Impact');
    expect(within(card).getByText('Injury feed unavailable')).toBeInTheDocument();
    expect(card.querySelectorAll('svg.text-accent\\/70')).toHaveLength(0);
  });

  test('its details explain the zero rather than leaving it blank', () => {
    draw();
    const details = within(cardFor('Injury Impact')).getByText('Details').closest('details');
    expect(within(details).getByText(/returned exactly 0\.50 and contributed nothing/i))
      .toBeInTheDocument();
  });
});

describe('the panel around it', () => {
  test('leads with the question the section answers', () => {
    draw();
    expect(screen.getByRole('heading', { name: 'Why SEA?' })).toBeInTheDocument();
  });

  test('says what to do when nothing is selected', () => {
    draw({ game: null });
    expect(screen.getByText(/Select a game to see the multi-agent analysis/i))
      .toBeInTheDocument();
  });

  test('reports a failure instead of an empty panel', () => {
    draw({ summary: { error: 'Prediction service unavailable.' } });
    expect(screen.getByRole('alert')).toHaveTextContent('Prediction service unavailable.');
  });
});
