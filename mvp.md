# CricDisco - IPL Auction & Match Simulator – MVP Spec

## 1. Overview

This MVP is a **local Python console game** that simulates:

1. A mini IPL-style **player auction** between 2–4 human managers.
2. A short-format **match** (5 overs per side) between any two drafted teams.

All player data (roles, base prices, stats, ratings) comes from `unified_players.json`.

No Discord, no web UI in v1. Everything is on the terminal, turn-based.

---

## 2. Scope & Constraints (MVP)

### 2.1 Players & teams

- **Human managers**: 2–4.
- **Teams per session**: equal to the number of managers.
- **Squad size (MVP)**: 6–8 players per team (keep it short for testing).
- **Auction pool size**: ~30–40 players selected from `unified_players.json`.

No foreign/domestic distinction, no salary caps in v1. Just an abstract “credits” system matching base prices.

### 2.2 Match format

- 1 match per session.
- Each team bats once:
  - **5 overs (30 balls)** per innings.
- **Ball-by-ball simulation internally**, but output is grouped per over:
  - Display every ball’s outcome within that over.
  - After each over, show score summary.

---

## 3. Data Model

### 3.1 Source: `assets/unified_players.json`

Each entry looks broadly like (simplified):

```json
{
  "full_name": "Shivam Dube",
  "role": "ar",
  "ipl_team_2025": "CSK",
  "source_prices": {
    "base": "-",
    "sold": "12"
  },
  "career_summary": {
    "matches": 53,
    "runs": 1176,
    "wickets": 4,
    "avg_bat": 27.35,
    "sr_bat": 143.07,
    "econ_bowl": 9.4,
    "sr_bowl": 26.5,
    "6s": 78,
    "4s": 63,
    "catches": 17
  },
  "yearly_stats": [
    {
      "Year": "2024",
      "Runs_Scored": "70",
      "Batting_Strike_Rate": "166.67",
      "...": "..."
    },
    "... more years ..."
  ],
  "calculated_ratings": {
    "batting": 50,
    "bowling": 1,
    "overall": 30
  },
  "final_base_price_crore": 2.0
}
```

Key fields used in the MVP:

- `full_name` – player identity for UI.
- `role` – `"bat"`, `"bowl"`, `"ar"`, `"wk"`.
- `calculated_ratings.overall` – single strength number for simulation.
- `calculated_ratings.batting`, `calculated_ratings.bowling` – optional refinements.
- `final_base_price_crore` – auction base price.

### 3.2 Python data structures

Define a minimal `Player` dataclass:

```python
@dataclass
class Player:
    id: int                 # index in list or UUID
    name: str
    role: str               # "bat" | "bowl" | "ar" | "wk"
    batting_rating: float
    bowling_rating: float
    overall_rating: float
    base_price: float       # in crore
```

Team representation:

```python
@dataclass
class Team:
    manager_name: str
    budget: float           # optional in MVP, can be very large
    players: list[Player]
```

Game/session state:

```python
@dataclass
class GameState:
    teams: list[Team]
    auction_pool: list[Player]
    sold_players: dict[int, str]  # player_id -> manager_name
```

---

## 4. CLI Flow (End-to-End)

### 4.1 Start session

1. **Load players**
   - Read `unified_players.json`.
   - Map to `Player` objects.
   - Filter to a subset for the auction:
     - Option A: random `N` players (e.g., 30).
     - Option B: top `N` by `overall_rating`.

2. **Ask for managers**
   - Prompt:
     - “How many managers (2–4)?”
     - “Enter manager 1 name:”
     - etc.
   - Initialize teams with empty player lists.

### 4.2 Auction phase

#### Per-player auction

For each player in `auction_pool`:

1. Show player card:

   ```text
   Player 5/30
   Name: Shivam Dube
   Role: AR
   Base Price: 2.0 Cr
   Rating: 30 (Bat 50, Bowl 1)
   ```

2. Initialize:

   - `current_price = player.base_price`
   - `current_winner = None`
   - `active_bidders = set(all managers)`

3. Bidding loop (round-robin):

   For each manager in order:

   - Ask:  
     `Rudra (team RCB): enter bid >= current_price or 'p' to pass:`
   - If they pass:
     - `active_bidders.remove(manager)`.
   - If they bid (number >= `current_price`):
     - `current_price = bid`
     - `current_winner = manager`

   Stop when:

   - Only one manager remains in `active_bidders`, or
   - All pass without any opening bid (player unsold).

4. Resolution:

   - If `current_winner` is not `None`:
     - Assign player to that team’s `players`.
     - Optionally subtract from budget.
   - Otherwise:
     - Mark as unsold (ignored in MVP).

5. Continue to next player until:
   - All players in pool processed, or
   - All teams reach desired squad size (e.g., 6–8 players).

### 4.3 Post-auction summary

Print squads:

```text
=== Team Rudra ===
1. Virat Kohli (BAT, 90)
2. Bumrah (BOWL, 92)
...

=== Team Friend ===
...
```

Then ask which two teams will play the match:

- List team indices; user chooses Team A and Team B.

---

## 5. Match Simulation (MVP)

### 5.1 Basic rules

- **Format**: 5 overs per innings (30 balls).
- **Playing XI**:
  - If squad has more than 11, select the best 11 by `overall_rating`.
  - Otherwise, use entire squad.

- **Batting order**:
  - Sort players by `batting_rating` (desc); break ties by `overall_rating`.
- **Bowling order**:
  - Sort by `bowling_rating` (desc); rotate through top 4–5 bowlers.

### 5.2 Outcome model per ball

Given batter `B` and bowler `O`:

1. Compute an **advantage score**, e.g.:

   ```python
   advantage = B.batting_rating - O.bowling_rating
   ```

2. Map advantage to probabilities:

   - Base probabilities (example):

     ```text
     dot:   0.25
     1 run: 0.30
     2 runs:0.10
     4 runs:0.12
     6 runs:0.08
     wicket:0.15
     ```

   - Modify:
     - If `advantage` very positive (batter strong), increase 4/6 probability, decrease wicket.
     - If very negative (bowler strong), increase dot/wicket, reduce 4/6.

3. Sample one outcome with `random.random()`.

4. Update:
   - Score, wickets, batter runs, etc.
   - If wicket: next batter in.

### 5.3 Display format

For each over:

- Print ball-by-ball:

  ```text
  Over 1 – Bumrah to Jaiswal
  1.1: 1 run
  1.2: 0
  1.3: 4
  1.4: W (caught at midwicket)
  1.5: 2
  1.6: 6

  End of over 1: 13/1 (Target: 80)
  ```

- Track full innings, then second innings with target.

At end:

- Print result:

  ```text
  Team Rudra: 78/4 in 5 overs
  Team Friend: 75/6 in 5 overs

  Result: Team Rudra wins by 3 runs.
  ```

No run rate, strike rate, or advanced stats are necessary in MVP, but they can be derived from ball log later.

---

## 6. Code Structure (MVP)

Project layout:

```text
ipl-sim/
├── unified_players.json     # your existing data file
├── main.py                  # CLI entrypoint
├── data.py                  # loading/filtering players
├── auction.py               # auction logic
├── match.py                 # match simulation
└── models.py                # dataclasses: Player, Team, GameState
```

### 6.1 `data.py`

- `load_players(path) -> list[Player]`
- `select_auction_pool(players, n=30) -> list[Player]`

### 6.2 `auction.py`

- `run_auction(players, managers) -> list[Team]`
  - Handles full auction flow and returns finalized teams.

### 6.3 `match.py`

- `simulate_match(team_a: Team, team_b: Team) -> MatchResult`
- `simulate_innings(batting_team, bowling_team) -> InningsResult`

Simple dataclasses for results:

```python
@dataclass
class InningsResult:
    runs: int
    wickets: int
    balls: int
    ball_log: list[str]

@dataclass
class MatchResult:
    team_a_result: InningsResult
    team_b_result: InningsResult
    winner: str | None
    margin: str
```

### 6.4 `main.py`

High-level orchestration:

1. Load players.
2. Ask for manager names.
3. Select auction pool.
4. Call `run_auction`.
5. Show squads.
6. Ask for two teams.
7. Call `simulate_match`.
8. Print result.

---

## 7. Future Extensions (For Later, Not MVP)

- **Discord bot wrapper**:
  - Convert auction prompts to Discord messages and commands.
  - Persist `GameState` in a small DB or JSON per guild/channel.

- **Real IPL rules**:
  - Purse limits, overseas player caps, role constraints.
  - Retentions, RTM cards.

- **Richer simulation**:
  - Use yearly stats (e.g., last 3 seasons) to weight performance more realistically.
  - Phase-based scoring (powerplay vs middle vs death overs).

- **UI polish**:
  - Rich-based TUI like your Duggu Code UI for better auction and match visualization.

---

## 8. Immediate Next Step

Implement the **data layer first**:

- `load_players` from `unified_players.json`.
- Print:
  - total players,
  - count per `role`,
  - top 10 by `overall_rating`.

This will confirm your player pool is big and balanced enough for the planned auction size before writing any game logic.
