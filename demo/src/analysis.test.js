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
  consensus: { count: 2, total: 3, label: '2/3 agents', winnerInfluence: 0.6 },
  agentInsights: {
    market: {
      label: 'Market Odds',
      predictedWinner: 'Seattle Seahawks',
      confidence: 0.63,
      reasoning: 'Consensus of 9 sportsbooks. Seattle Seahawks favored by 3.5. '
        + 'Fair moneyline gives Seattle Seahawks a 63% win probability. Vig removed (overround 1.043).',
      weight: 0.164, contribution: 0.0213, influenceShare: 0.6, hasData: true,
    },
    stats: {
      label: 'Basic Predictor',
      predictedWinner: 'New England Patriots',
      confidence: 0.625,
      reasoning: 'Using real game_log data. New England Patriots on a 3-game run.',
      weight: 0.111, contribution: 0.0139, influenceShare: 0.4, hasData: true,
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

/**
 * An agent's card in the grid. Scoped, because each agent's name also appears
 * in the consensus panel's "What drove this pick" ranking.
 */
const agentGrid = () => document.querySelector('.grid.items-start');
const cardFor = (label) =>
  within(agentGrid()).getByText(label).closest('div.rounded-lg');
const consensusPanel = () => screen.getByText('Official model pick').closest('aside');

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
    expect(within(card).getByText('60%')).toBeInTheDocument();
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
    expect(agentGrid()).toBeInTheDocument();
    expect(agentGrid().className).toContain('items-start');
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

describe('the consensus panel', () => {
  test('leads with the pick and its win probability, not a list of rows', () => {
    draw();
    const panel = consensusPanel();
    expect(within(panel).getByText('Seattle Seahawks')).toBeInTheDocument();
    // 55% appears as the hero number and again in the Win prob metric card.
    expect(within(panel).getAllByText('55%').length).toBeGreaterThanOrEqual(1);
    expect(within(panel).getByText('LEAN')).toBeInTheDocument();
  });

  test('draws the vote as two sides, so the disagreement is the first thing seen', () => {
    // Five agents reading the same game and not agreeing is the product. It was
    // previously the string "2/3 agents" in a definition list.
    draw();
    const panel = consensusPanel();
    expect(within(panel).getByText('Agent vote')).toBeInTheDocument();
    const vote = within(panel).getByText('Agent vote').parentElement;
    // Two backing Seattle, one backing New England.
    expect(within(vote).getByText('2')).toBeInTheDocument();
    expect(within(vote).getByText('1')).toBeInTheDocument();
    expect(within(vote).getByText('SEA')).toBeInTheDocument();
    expect(within(vote).getByText('NE')).toBeInTheDocument();
  });

  test('reads headcount, then weight, then the published number', () => {
    // Reading down these rows is the whole architecture, which is why the
    // headcount sits above the weighted figure rather than replacing it.
    draw();
    const panel = consensusPanel();
    const weighted = within(panel).getByText('Weighted consensus').closest('div');
    expect(weighted.textContent).toContain('SEA 60%');
    const final = within(panel).getByText('Final win probability').closest('div');
    expect(final.textContent).toContain('SEA 55%');
  });

  test('says so in words when the weighting overrides the headcount', () => {
    // A minority of agents carrying the call is the clearest demonstration of
    // what weighting by measured accuracy does, so it is stated, not implied.
    draw({
      summary: {
        ...SUMMARY,
        winner: 'New England Patriots',
        consensus: { ...SUMMARY.consensus, count: 1, total: 3, winnerInfluence: 0.55 },
      },
    });
    expect(screen.getByText(/weighting overrode the headcount/i)).toBeInTheDocument();
  });

  test('does not cry override when the majority agrees', () => {
    draw();
    expect(screen.queryByText(/weighting overrode the headcount/i)).not.toBeInTheDocument();
  });

  test('an agent that returned no data is drawn hollow and explained', () => {
    draw();
    expect(screen.getByText(/reported no data, returned exactly\s+0\.50 and moved nothing/i))
      .toBeInTheDocument();
    const vote = within(consensusPanel()).getByText('Agent vote').parentElement;
    expect(vote.querySelectorAll('.border-content-muted')).toHaveLength(1);
  });

  test('ranks the agents by how much they moved the vote', () => {
    // The product's own claim is "not just the winner but which signal drove
    // it". The agent grid is in fixed order, so until now nothing answered it.
    draw();
    const rows = within(consensusPanel()).getByRole('list');
    const names = within(rows).getAllByRole('listitem')
      .map((li) => li.textContent.replace(/[A-Z]{2,3}\d+%$/, '').trim());
    expect(names[0]).toContain('Market Odds');
    expect(names[names.length - 1]).toContain('Injury Impact');
  });

  test('says which side each agent was on, not only in colour', () => {
    draw();
    const rows = within(consensusPanel()).getAllByRole('listitem');
    const stats = rows.find((li) => li.textContent.includes('Basic Predictor'));
    expect(stats.textContent).toContain('NE');
    expect(within(stats).getByText('NE').className).toMatch(/text-content-secondary/);
    const market = rows.find((li) => li.textContent.includes('Market Odds'));
    expect(within(market).getByText('SEA').className).toMatch(/text-accent/);
  });

  test('the breakdown reconciles with the weighted figure above it', () => {
    // The aligned shares must add up to the "Weighted" metric, or the panel is
    // quietly disagreeing with itself.
    const aligned = Object.values(SUMMARY.agentInsights)
      .filter((i) => i.predictedWinner === SUMMARY.winner)
      .reduce((sum, i) => sum + i.influenceShare, 0);
    expect(Math.round(aligned * 100))
      .toBe(Math.round(SUMMARY.consensus.winnerInfluence * 100));
  });

  test('does not restate the vote in prose, or touch the truncated string', () => {
    /*
     * The panel used to render consensus_reasoning, which the API builds by
     * appending each agent's reasoning cut to ~50 characters - so it ended on
     * "Seattle Seah...", a mid-word cut of text shown in full in an agent card
     * beside it. With the vote drawn, the sentence is also a restatement: the
     * winner, the confidence and the headcount are all above it.
     */
    draw({
      summary: {
        ...SUMMARY,
        reasoning: 'Weighted consensus favours Seattle Seahawks (2/3 agents). '
          + 'Market Odds: Consensus of 9 sportsbooks. Seattle Seah...',
      },
    });
    const panel = consensusPanel();
    expect(panel.textContent).not.toMatch(/\.\.\./);
    expect(panel.textContent).not.toMatch(/Weighted consensus favours/);
  });

  test('the vote is stated for a reader who cannot see the dots', () => {
    // The dots carry no text of their own.
    draw();
    expect(within(consensusPanel()).getByText(/2 of 3 agents picked SEA, 1 picked NE\./))
      .toBeInTheDocument();
  });

  test('the panel does not stretch to the height of the agent grid', () => {
    draw();
    expect(consensusPanel().className).toContain('self-start');
  });
});
