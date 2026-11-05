"""
engine.py - One NFL game, one play at a time.

The game state is possession, down, distance, yard line (yards to the opponent's
goal), clock, score and timeouts. Every snap asks the same three questions:

  1. What does the offence call?  Fourth down goes to a go / punt / field-goal
     table; late-game rules kneel or spike; otherwise a fitted pass/run model on
     down, distance, field position, score and clock (trailing late -> pass).
  2. What happens?  A sack, scramble, interception, completion or incompletion
     for a pass, yards for a run - drawn from real plays in the same situation -
     adjusted for this offence against this defence. Penalties, fumbles, punts,
     field goals, extra points and two-point tries likewise.
  3. How much clock runs?  Real time between snaps for that kind of play at that
     tempo (normal, hurry-up when trailing late, milking when ahead), with the
     two-minute warning and timeouts.

Overtime follows the current rules: ten minutes, both teams get a possession,
then the next score wins, and the game can end tied.

Every player-facing number - who was targeted, who carried, who scored - is
decided inside the play, so a simulated box score is internally consistent: a
receiver's touchdown is his quarterback's touchdown and his team's six points.
"""
import math
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from rotobot.pbp.fit import TOUCHDOWN, dist_bucket, fourth_bucket, pass_features, zone

PICK_SIX = 0.07                 # share of interceptions returned for a touchdown
INT_SPOT_GAIN = 2               # an interception's net field position change vs the line of scrimmage
TIMEOUT_PLAY_SECONDS = 6        # clock used by a play when a timeout follows it
HALF = 1800


@dataclass
class Role:
    """A player the offence can give the ball to."""
    player_id: str
    target: float = 0.0          # share of targets
    carry: float = 0.0           # share of designed runs
    goal_line: float = 0.0       # share of carries inside the 5
    catch_rel: float = 1.0       # completion rate relative to the team's
    ypt_rel: float = 1.0         # yards per catch relative to the team's
    ypc_rel: float = 1.0         # yards per carry relative to the team's


@dataclass
class Side:
    """One team as the engine sees it. Multipliers are 1.0 for a league-average unit."""
    code: str
    qb: Optional[str] = None
    roles: List[Role] = field(default_factory=list)
    positions: Dict[str, str] = field(default_factory=dict)   # player_id -> QB/RB/WR/TE, for reporting
    pass_lean: float = 0.0       # logit shift on pass vs run: pass rate over expected
    efficiency: float = 1.0      # the market calibration lever - see calibrate.py
    pass_off: float = 1.0        # yards per completion
    run_off: float = 1.0         # yards per carry
    comp_off: float = 0.0        # completion logit shift
    sack_off: float = 1.0        # sacks allowed
    int_off: float = 1.0         # interceptions thrown
    pass_def: float = 1.0        # yards per completion allowed
    run_def: float = 1.0
    comp_def: float = 0.0
    sack_def: float = 1.0        # sacks made
    int_def: float = 1.0


def new_box():
    return {"points": 0, "pass_att": 0, "completions": 0, "pass_yds": 0, "pass_td": 0, "int": 0,
            "sacks": 0, "carries": 0, "rush_yds": 0, "rush_td": 0, "plays": 0, "punts": 0,
            "fg_att": 0, "fg_made": 0, "td": 0, "turnovers": 0}


def _new_player():
    return [0.0] * 11


# Player stat indices: compact lists are much faster than dicts in the hot loop
TGT, REC, RECYD, RECTD, CAR, RUSHYD, RUSHTD, ATT, PASSYD, PASSTD, INT = range(11)
FUM = 11


class Game:
    def __init__(self, model: Dict, home: Side, away: Side, rng: random.Random):
        self.m = model
        self.sides = (home, away)
        self.rng = rng
        self.pass_beta = model["pass_beta"]
        self.fg_beta = model["fg_beta"]
        self._prepare_roles()

    def _prepare_roles(self):
        """Cumulative weights for picking a target or a rusher; the last slot is 'someone else'."""
        self.target_cum, self.carry_cum, self.goal_cum = [], [], []
        for side in self.sides:
            for attr, out in (("target", self.target_cum), ("carry", self.carry_cum), ("goal_line", self.goal_cum)):
                weights = [getattr(r, attr) for r in side.roles]
                other = max(0.0, 1.0 - sum(weights))
                total, cum = 0.0, []
                for w in weights + [other]:
                    total += w
                    cum.append(total)
                out.append([c / total for c in cum] if total else [1.0])

    # --- one game ------------------------------------------------------------------

    def play(self) -> Tuple[List[Dict], List[Dict[str, List[float]]]]:
        rng = self.rng
        # Form: how well each team plays *today*. Real teams have good and bad
        # days that lift or sink the whole offence together - a quarterback
        # off his game takes his receivers with him. Mean-preserving, so the
        # market calibration still holds on average. Sized on 2024 (a fitting
        # season), checked on 2025-2026: see backtest_rotobot_pbp.py --form-sd.
        sd = self.m.get("form_sd", 0.0)
        self.eff = [s.efficiency * (math.exp(rng.gauss(0.0, sd) - sd * sd / 2) if sd else 1.0)
                    for s in self.sides]
        self.box = [new_box(), new_box()]
        self.players = [{r.player_id: [0.0] * 12 for r in s.roles} for s in self.sides]
        for i, s in enumerate(self.sides):
            if s.qb and s.qb not in self.players[i]:
                self.players[i][s.qb] = [0.0] * 12
        self.timeouts = [3, 3]
        self.clock = 3600.0
        self.overtime = False
        self.halftime_pending = False
        self.halftime_done = False
        self.ot_completed = [0, 0]          # overtime possessions each side has finished
        self.offence = None
        opening = rng.randrange(2)            # receives the opening kickoff
        self.second_half_receiver = 1 - opening
        self._kickoff(receiver=opening)

        while True:
            if self.halftime_pending:
                # Whatever happened on the last play of the half, the second half
                # starts with the scheduled kickoff
                self.halftime_pending, self.halftime_done = False, True
                self.timeouts = [3, 3]
                self._kickoff(self.second_half_receiver)
            if self.overtime and min(self.ot_completed) >= 1 and \
                    self.box[0]["points"] != self.box[1]["points"]:
                break
            if self.clock <= 0:
                if self.overtime or self._end_of_regulation():
                    break
                continue
            self._snap()
        return self.box, self.players

    def _end_of_regulation(self) -> bool:
        if self.box[0]["points"] != self.box[1]["points"]:
            return True
        self.overtime = True
        self.clock = 600.0
        self.timeouts = [2, 2]
        self.offence = None
        self._kickoff(self.rng.randrange(2))
        return False

    # --- possession changes ----------------------------------------------------------

    def _give_ball(self, team: int, yardline_100: float):
        if self.overtime and self.offence is not None and self.offence != team:
            self.ot_completed[self.offence] += 1
        self.offence = team
        self.yl = min(max(yardline_100, 1.0), 99.0)
        self.down, self.togo = 1, min(10.0, self.yl)

    def _kickoff(self, receiver: int, free_kick: bool = False):
        rng = self.rng
        if not free_kick and rng.random() < self.m["kickoff_return_td"]:
            self._score(receiver, 6, touchdown=True)
            return
        start = rng.choice(self.m["kickoff_start"])
        if free_kick:
            # A free kick after a safety comes from the 20, not the 35
            start = max(start - 10, 20)
        self._give_ball(receiver, start)

    def _score(self, team: int, points: int, touchdown: bool = False):
        """Points, the try after a touchdown, and the kickoff that follows a TD or field goal.
        A safety's free kick is handled by the caller."""
        self.box[team]["points"] += points
        self._tick(6)                        # the scoring play itself, and the try
        if touchdown:
            self.box[team]["td"] += 1
            self._try(team)
        if touchdown or points == 3:
            self.offence = team              # the scoring side kicks off; its possession is over
            self._kickoff(1 - team)

    def _try(self, team: int):
        rng = self.rng
        diff = self.box[team]["points"] - self.box[1 - team]["points"]
        late = "late" if not self.overtime and self.clock <= 900 else "early"
        d = int(diff)
        key = f"{late}|{d}" if -16 <= d <= 16 else f"{late}|{'<-16' if d < -16 else '>16'}"
        go_for_two = rng.random() < self.m["two_point_rate"].get(key, 0.05)
        if go_for_two:
            if rng.random() < self.m["two_point_success"]:
                self.box[team]["points"] += 2
        elif rng.random() < self.m["pat"]:
            self.box[team]["points"] += 1

    def _tick(self, seconds: float):
        """Clock for a play that stops it (a score): no runoff tempo, no timeouts."""
        before = self.clock
        self.clock = max(self.clock - seconds, 0.0)
        if not self.overtime and not self.halftime_done and before > HALF >= self.clock:
            self.clock = float(HALF)
            self.halftime_pending = True

    def _turnover(self, new_yardline_for_opponent: float):
        self.box[self.offence]["turnovers"] += 1
        self._give_ball(1 - self.offence, new_yardline_for_opponent)

    # --- the clock ------------------------------------------------------------------

    def _half_seconds(self) -> float:
        if self.overtime:
            return self.clock
        return self.clock - HALF if self.clock > HALF else self.clock

    def _tempo(self) -> str:
        diff = self._lead()
        if self.overtime:
            # Ten minutes and a tie counts as half a loss: nobody who is level
            # or behind plays at a normal pace
            return "hurry" if diff <= 0 else "milk"
        late = not self.overtime and self.clock <= 300
        if diff < 0 and (late or self._half_seconds() <= 120):
            return "hurry"
        if diff > 0 and late:
            return "milk"
        return "normal"

    def _lead(self) -> int:
        o = self.offence
        return self.box[o]["points"] - self.box[1 - o]["points"]

    def _run_clock(self, cls: str):
        rng = self.rng
        tempo = self._tempo()
        samples = self.m["runoff"].get(f"{cls}|{tempo}") or self.m["runoff"].get(f"{cls}|normal") or [30]
        elapsed = rng.choice(samples)

        # Timeouts: a defence trailing late stops the clock after a running play
        stops = cls in ("inbounds", "sack", "kneel")
        half_left = self._half_seconds()
        d = 1 - self.offence
        if stops and self.timeouts[d] > 0 and self._lead() > 0 and half_left <= 150 and \
                (self.overtime or self.clock <= HALF):
            self.timeouts[d] -= 1
            elapsed = TIMEOUT_PLAY_SECONDS
        elif stops and self.timeouts[self.offence] > 0 and self._lead() < 0 and half_left <= 40:
            self.timeouts[self.offence] -= 1
            elapsed = TIMEOUT_PLAY_SECONDS

        before = self.clock
        after = max(before - elapsed, 0.0)
        # The two-minute warning stops the clock in each half
        for warning in (HALF + 120, 120):
            if before > warning >= after and not self.overtime:
                after = float(warning)
        # Halftime: the kickoff happens at the top of the next loop
        if before > HALF >= after and not self.overtime and not self.halftime_done:
            self.clock = float(HALF)
            self.halftime_pending = True
            return
        self.clock = after

    # --- the snap ---------------------------------------------------------------------

    def _snap(self):
        rng = self.rng
        o = self.offence
        off, de = self.sides[o], self.sides[1 - o]
        self.box[o]["plays"] += 1
        lead = self._lead()
        half_left = self._half_seconds()

        # Take a knee when the game is won
        if lead > 0 and (self.overtime or self.clock <= HALF) and \
                self.clock <= 42 * (4 - self.down + 1) - 38 * self.timeouts[1 - o] and \
                (self.overtime or self.clock <= 130):
            self.yl = min(self.yl + 1, 99)
            self._advance_down(-1)
            self._run_clock("kneel")
            return

        # End of half: kick if in range
        if half_left <= 8 and self.yl + 18 <= 55 and not (lead > 3 and self.clock <= 8):
            self._field_goal()
            return

        if self.down == 4:
            choice = self._fourth_down(lead)
            if choice == 1:
                self._punt()
                return
            if choice == 2:
                self._field_goal()
                return

        # Penalties that wipe out the snap
        r = rng.random()
        rates = self.m["penalty_rate"]
        if r < rates["offence"]:
            yards, _ = rng.choice(self.m["penalty_samples"]["offence"])
            self.yl = min(self.yl + yards, 99)
            self.togo += yards
            self._run_clock("penalty")
            return
        if r < rates["offence"] + rates["defence"]:
            yards, first = rng.choice(self.m["penalty_samples"]["defence"])
            yards = min(yards, self.yl - 1) if self.yl > 1 else 0
            self.yl -= yards
            self.togo -= yards
            if first or self.togo <= 0:
                self.down, self.togo = 1, min(10.0, self.yl)
            self._run_clock("penalty")
            return

        # The call
        x = pass_features(min(self.down, 3), self.togo, self.yl, lead,
                          self.clock if not self.overtime else 0, half_left, 5 if self.overtime else (1 if self.clock > 2700 else 2 if self.clock > HALF else 3 if self.clock > 900 else 4))
        z = sum(b * v for b, v in zip(self.pass_beta, x)) + off.pass_lean
        if rng.random() < 1 / (1 + math.exp(-z)):
            self._pass(off, de)
        else:
            self._run(off, de)

    def _fourth_down(self, lead: int) -> int:
        if self.overtime and lead == 0 and self.yl + 18 <= 55:
            return 2                              # level in overtime: take the makeable kick
        late = (not self.overtime and self.clock <= 600 and lead < 0) or (self.overtime and lead <= 0)
        key = f"{int(late)}|{fourth_bucket(self.togo)}|{min(int(self.yl // 10), 9)}"
        probs = self.m["fourth"].get(key) or self.m["fourth"].get(f"0|{fourth_bucket(self.togo)}|{min(int(self.yl // 10), 9)}") or [0.1, 0.9, 0.0]
        # Down by more than a field goal with little time: kicking does not help
        if late and lead < -3 and self.clock <= 240:
            return 0
        if self.yl + 18 > 62:
            probs = [probs[0], probs[1] + probs[2], 0.0]
        r = self.rng.random()
        return 0 if r < probs[0] else (1 if r < probs[0] + probs[1] else 2)

    def _pick(self, cum: List[float]) -> int:
        r = self.rng.random()
        for i, c in enumerate(cum):
            if r <= c:
                return i
        return len(cum) - 1

    def _player(self, o: int, idx: int) -> Optional[List[float]]:
        roles = self.sides[o].roles
        return self.players[o][roles[idx].player_id] if idx < len(roles) else None

    def _pass(self, off: Side, de: Side):
        rng = self.rng
        o = self.offence
        box = self.box[o]
        key = f"{dist_bucket(self.togo)}|{zone(self.yl)}"
        probs = self.m["pass_outcomes"].get(key) or self.m["pass_outcomes"]["long|field"]
        p_sack = probs["sack"] * off.sack_off * de.sack_def / self.eff[self.offence]
        p_scr = probs["scramble"]
        attempts = 1 - probs["sack"] - probs["scramble"]
        p_int = probs["int"] / attempts * off.int_off * de.int_def / self.eff[self.offence]
        p_comp = probs["complete"] / attempts
        logit = math.log(p_comp / (1 - p_comp)) + off.comp_off + de.comp_def + 2.0 * math.log(self.eff[self.offence])
        qb = self.players[o].get(off.qb) if off.qb else None

        r = rng.random()
        if r < p_sack:
            yards = rng.choice(self.m["sack_yards"])
            box["sacks"] += 1
            self._gain(yards, "sack")
            return
        if r < p_sack + p_scr:
            yards = self._yards(rng.choice(self.m["scramble_yards"]), off.run_off * de.run_def * self.eff[self.offence])
            box["carries"] += 1
            if qb is not None:
                qb[CAR] += 1
            self._gain(yards, "inbounds", rusher=qb, team_rush=True)
            return

        box["pass_att"] += 1
        if qb is not None:
            qb[ATT] += 1
        idx = self._pick(self.target_cum[o])
        receiver = self._player(o, idx)
        role = off.roles[idx] if idx < len(off.roles) else None
        if receiver is not None:
            receiver[TGT] += 1

        if rng.random() < p_int:
            box["int"] += 1
            if qb is not None:
                qb[INT] += 1
            if rng.random() < PICK_SIX:
                box["turnovers"] += 1
                self._score(1 - o, 6, touchdown=True)
                return
            self._turnover(100 - max(self.yl - INT_SPOT_GAIN, 1))
            self._run_clock("incomplete")
            return

        if role is not None:
            logit += math.log(max(role.catch_rel, 0.05))
        if rng.random() < 1 / (1 + math.exp(-logit)):
            yards = self._yards(rng.choice(self.m["completion_yards"].get(key) or self.m["completion_yards"]["long|field"]),
                                off.pass_off * de.pass_def * self.eff[self.offence] * (role.ypt_rel if role else 1.0))
            box["completions"] += 1
            if receiver is not None:
                receiver[REC] += 1
            if rng.random() < self.m["fumble_lost"]["catch"]:
                gained = min(yards, self.yl - 1)
                self._credit_pass(o, qb, receiver, gained, td=False)
                self.yl -= gained
                self._turnover(100 - self.yl)
                self._run_clock("inbounds")
                return
            td = yards >= self.yl
            gained = self.yl if td else yards
            self._credit_pass(o, qb, receiver, gained, td)
            if td:
                self._score(o, 6, touchdown=True)
                return
            self._gain(gained, "inbounds" if rng.random() > 0.18 else "out_of_bounds", already_credited=True)
            return

        # Incomplete
        self._advance_down(0)
        self._run_clock("incomplete")

    def _yards(self, sampled: float, multiplier: float) -> float:
        """A drawn gain, scaled for the matchup. A drawn touchdown reaches the end zone;
        a drawn non-scoring gain stops short of it unless the matchup carries it in."""
        if sampled >= TOUCHDOWN:
            return self.yl
        if sampled <= 0:
            return sampled
        scaled = round(sampled * multiplier)
        # A play that did not score in reality only scores here if the multiplier,
        # not the draw, is what carried it across
        if scaled >= self.yl and sampled < self.yl:
            return scaled if multiplier > 1.0 else self.yl - 1
        return min(scaled, self.yl - 1) if sampled < self.yl else scaled

    def _credit_pass(self, o, qb, receiver, yards, td):
        box = self.box[o]
        box["pass_yds"] += yards
        if qb is not None:
            qb[PASSYD] += yards
        if receiver is not None:
            receiver[RECYD] += yards
        if td:
            box["pass_td"] += 1
            if qb is not None:
                qb[PASSTD] += 1
            if receiver is not None:
                receiver[RECTD] += 1

    def _run(self, off: Side, de: Side):
        rng = self.rng
        o = self.offence
        key = f"{dist_bucket(self.togo)}|{zone(self.yl)}"
        cum = self.goal_cum[o] if self.yl <= 5 else self.carry_cum[o]
        idx = self._pick(cum)
        rusher = self._player(o, idx)
        role = off.roles[idx] if idx < len(off.roles) else None
        yards = self._yards(rng.choice(self.m["run_yards"].get(key) or self.m["run_yards"]["long|field"]),
                            off.run_off * de.run_def * self.eff[self.offence] * (role.ypc_rel if role else 1.0))
        self.box[o]["carries"] += 1
        if rusher is not None:
            rusher[CAR] += 1
        if rng.random() < self.m["fumble_lost"]["run"] / self.eff[self.offence]:
            gained = min(yards, self.yl - 1)
            self.box[o]["rush_yds"] += gained
            if rusher is not None:
                rusher[RUSHYD] += gained
                rusher[FUM] += 1
            self.yl -= gained
            self._turnover(100 - self.yl)
            self._run_clock("inbounds")
            return
        self._gain(yards, "inbounds" if rng.random() > 0.1 else "out_of_bounds", rusher=rusher, team_rush=True)

    def _gain(self, yards: float, cls: str, rusher=None, team_rush=False, already_credited=False):
        o = self.offence
        if team_rush:
            td = yards >= self.yl
            gained = self.yl if td else yards
            self.box[o]["rush_yds"] += gained
            if rusher is not None:
                rusher[RUSHYD] += gained
            if td:
                self.box[o]["rush_td"] += 1
                if rusher is not None:
                    rusher[RUSHTD] += 1
                self._score(o, 6, touchdown=True)
                return
            yards = gained
        new_yl = self.yl - yards
        if new_yl >= 100:                                   # tackled in his own end zone
            self._score(1 - o, 2)
            self.offence = o
            self._kickoff(1 - o, free_kick=True)
            return
        self.yl = new_yl
        self._advance_down(yards)
        self._run_clock(cls)

    def _advance_down(self, yards: float):
        self.togo -= yards
        if self.togo <= 0:
            self.down, self.togo = 1, min(10.0, self.yl)
            return
        self.down += 1
        if self.down > 4:
            self._turnover(100 - self.yl)

    def _punt(self):
        rng = self.rng
        o = self.offence
        self.box[o]["punts"] += 1
        if rng.random() < self.m["punt_return_td"]:
            self._score(1 - o, 6, touchdown=True)
            return
        start = rng.choice(self.m["punt_start"].get(str(min(int(self.yl // 10), 9))) or [80])
        self._give_ball(1 - o, start)
        self._run_clock("inbounds")

    def _field_goal(self):
        rng = self.rng
        o = self.offence
        distance = self.yl + 18
        z = self.fg_beta[0] + self.fg_beta[1] * distance / 10.0
        self.box[o]["fg_att"] += 1
        if rng.random() < 1 / (1 + math.exp(-z)):
            self.box[o]["fg_made"] += 1
            self._score(o, 3)
        else:
            self._tick(6)
            spot = self.yl + 7
            self._give_ball(1 - o, 80 if spot < 20 else 100 - spot)
