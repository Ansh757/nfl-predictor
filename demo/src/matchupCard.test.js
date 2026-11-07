import { render, screen, within } from '@testing-library/react';
import MatchupCard from './components/predictions/MatchupCard';
import { formatKickoff } from './utils/time';

/**
 * The matchup card, after the redesign that made the pick the loudest thing on
 * it. These pin the parts of that change that are easy to undo by accident.
 */
const GAME = {
  game_id: 1,
  game_date: '2026-09-13T17:00:00Z',
  home_team: 'Seattle Seahawks',
  away_team: 'New England Patriots',
};

const SUMMARY = {
  winner: 'Seattle Seahawks',
  confidence: 0.55,
  consensus: { count: 3, total: 5, label: '3/5 agents' },
};

const draw = (props = {}) => render(
  <MatchupCard
    game={GAME}
    summary={SUMMARY}
    isPredicting={false}
    isSelected={false}
    onSelect={() => {}}
    formatTime={formatKickoff}
    {...props}
  />
);

const card = () => screen.getByRole('button');

describe('the pick is the thing you see first', () => {
  test('the picked side is tagged, and the pick is named by nickname', () => {
    draw();
    // The PICK tag sits beside the picked team's abbreviation, and only there.
    expect(within(card()).getAllByText('Pick')).toHaveLength(1);
    expect(within(card()).getByText('SEA').parentElement).toHaveTextContent('Pick');
    expect(within(card()).getByText('NE').parentElement).not.toHaveTextContent('Pick');
    expect(within(card()).getByText('Model takes', { exact: false }).parentElement)
      .toHaveTextContent('Model takes Seahawks');
  });

  test('both teams stay legible, and a finished loser is stepped down', () => {
    // This is a matchup card: a reader still has to see who is playing.
    draw();
    expect(within(card()).getByText('NE')).toBeInTheDocument();
    expect(within(card()).getByText('Patriots')).toBeInTheDocument();
    expect(within(card()).getByText('NE').className).toMatch(/text-content\b/);
    document.body.innerHTML = '';
    draw({ game: { ...GAME, home_score: 30, away_score: 10 } });
    expect(within(card()).getByText('NE').className).toMatch(/text-content-muted/);
    expect(within(card()).getByText('SEA').className).toMatch(/text-content\b/);
  });

  test('both probabilities are shown, and the bar carries a coin-flip mark', () => {
    draw();
    expect(within(card()).getByText('45%')).toBeInTheDocument();
    expect(within(card()).getByText('55%')).toBeInTheDocument();
    // A 55% pick reads as decisive until you can see how close to 50 it sits.
    expect(card().querySelector('[data-probability-bar] .left-1\\/2')).toBeInTheDocument();
  });
});

describe('the probability bar', () => {
  /**
   * The two fills, in document order: away side then home side. Scoped to the
   * bar rather than the card - the agreement dots are also bg-accent.
   */
  const fills = () =>
    [...card().querySelector('[data-probability-bar]').children].filter((el) => el.style.width);
  const fill = (el) => (el.className.includes('bg-accent') ? 'bg-accent' : 'bg-opposing');

  test('the accent marks the picked side when the home team is picked', () => {
    draw();
    expect(fills().map(fill)).toEqual(['bg-opposing', 'bg-accent']);
  });

  test('the accent follows the pick to the away team', () => {
    // The regression this exists for: colouring by home/away looked correct on
    // every game the home side was favoured in and was backwards on the rest,
    // lighting up the team the model did not pick.
    draw({ summary: { ...SUMMARY, winner: 'New England Patriots' } });
    expect(fills().map(fill)).toEqual(['bg-accent', 'bg-opposing']);
  });

  test('the accent follows the pick on either side', () => {
    for (const winner of ['Seattle Seahawks', 'New England Patriots']) {
      const { unmount } = draw({ summary: { ...SUMMARY, winner } });
      const [away] = fills();
      expect(fill(away)).toBe(winner === GAME.home_team ? 'bg-opposing' : 'bg-accent');
      unmount();
    }
  });

  test('the widths are the probabilities', () => {
    draw();
    const [away, home] = fills();
    expect(parseFloat(away.style.width)).toBeCloseTo(45, 6);
    expect(parseFloat(home.style.width)).toBeCloseTo(55, 6);
  });
});

describe('the card is a solid surface', () => {
  test('no gradient, no translucent overlay, no glow', () => {
    /*
     * The card used to tint its winning half with an accent gradient. It was
     * asked for and then asked to be taken out, and the second call is the
     * right one: a large surface brightening toward one team is the loudest
     * argument on the page for a pick the model makes at 55%, and it reads as
     * product styling rather than as data.
     */
    draw();
    expect(card().querySelector('[class*="bg-gradient"]')).toBeNull();
    expect(card().className).not.toMatch(/bg-gradient|backdrop|shadow/);
    expect(card().className).toContain('bg-surface');
  });

  test('the surface does not change with the pick', () => {
    // Whichever side is picked, the card is the same colour.
    const home = (draw(), card().className);
    document.body.innerHTML = '';
    const away = (draw({ summary: { ...SUMMARY, winner: 'New England Patriots' } }),
      card().className);
    expect(home).toBe(away);
  });

  test('a finished card and an open one are the same surface too', () => {
    const open = (draw(), card().className);
    document.body.innerHTML = '';
    const done = (draw({ game: { ...GAME, home_score: 17, away_score: 24 } }),
      card().className);
    expect(done).toBe(open);
  });

  test('the card responds to hover, because the whole card is the button', () => {
    // It always was, but with no hover response it did not look like one, so
    // "View analysis" read as the only way in. Solid border, a 1px rise - no
    // glow.
    draw();
    const className = card().className;
    expect(className).toContain('cursor-pointer');
    expect(className).toMatch(/hover:-translate-y-px/);
    expect(className).toMatch(/hover:border-accent/);
    expect(className).not.toMatch(/hover:shadow/);
  });
});

describe('what a screen reader gets', () => {
  test('the card announces one sentence, not every number twice', () => {
    draw();
    const name = card().getAttribute('aria-label');
    expect(name).toMatch(/New England Patriots at Seattle Seahawks/);
    expect(name).toMatch(/Model picks Seattle Seahawks, 55 percent/);
    expect(name).toMatch(/3 of 5 agents agree/);
  });

  test('the label carries the caveat, not just the pick', () => {
    // The band is what a sighted reader gets from the muted word beside the
    // confidence. Dropping it here would leave a screen reader user with a
    // barer, more certain-sounding claim than the card actually makes - and it
    // is spelled out, because "lean" on its own carries its meaning from
    // sitting next to a percentage.
    expect(draw() && card().getAttribute('aria-label'))
      .toMatch(/lean confidence in that pick/i);
  });

  test('a final score and the outcome are in the label', () => {
    draw({ game: { ...GAME, home_score: 30, away_score: 10 } });
    expect(card().getAttribute('aria-label')).toMatch(/Final 10 to 30, model correct/i);
  });

  test('"View analysis" is an affordance, not a nested button', () => {
    // The whole card is the button. A <button> inside it would be invalid and
    // unreachable.
    draw();
    expect(screen.getAllByRole('button')).toHaveLength(1);
    expect(screen.getByText('View analysis').closest('button')).toBe(card());
  });
});

describe('states other than a completed prediction', () => {
  test('says so while the agents are running', () => {
    draw({ summary: null, isPredicting: true });
    expect(screen.getByText('Running agents…')).toBeInTheDocument();
    expect(card().getAttribute('aria-label')).toMatch(/Prediction running/);
  });

  test('says so when the prediction failed', () => {
    draw({ summary: { error: 'boom' } });
    expect(screen.getByText('Prediction unavailable')).toBeInTheDocument();
  });

  test('a tie is neither correct nor wrong', () => {
    // Comparing the pick against a null winner scores every drawn game a miss.
    draw({ game: { ...GAME, home_score: 20, away_score: 20 } });
    expect(screen.queryByText(/Model (correct|wrong)/)).not.toBeInTheDocument();
    expect(card().getAttribute('aria-label')).toMatch(/Final 20 to 20\. View analysis/);
  });
});
