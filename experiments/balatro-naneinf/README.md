# Balatro naneinf: which plan is easier? (Oct 14, 2026)

Monte Carlo of a run's item supply (shops, rerolls, packs, tags, vouchers) with the 1.0.1 odds
documented on balatrowiki.org, plus the scoring arithmetic of each finish, to compare:

- **A** Perkeo on Ghost Deck: Perkeo copies a held Cryptid every shop; the Cryptids add Red Seal Steel
  Kings to hand on any blind (traditional scoring: 87 kings with 4 copies, 40 Cryptids).
- **B** Plasma Deck, Baron + Mime + 4 copies + Burglar on The Serpent (the wiki's Guide: naneinf):
  44 kings, 7 joker slots, ~19-21 hands, window ante 26-31.
- **H** B's plan, switching to A's Cryptid finish if Perkeo shows up.

Result (20,000 runs per cell, typical economy, pre-Baron engine log10 Mult 12):
A 1.5%, B 9.0%, H 9.2%. Across lean/rich economy and engine 10-14: A 0.2-3.4%, B 2.2-17.5%.
A is capped by Perkeo: about 0.145% per shop (Soul 0.3% per Arcana/Spectral card, 1 in 5 legendaries),
roughly 690 shops per Perkeo, and rerolls don't help. Even with Perkeo by ante 8, A converts ~30%.

Files: `sim.py` (model), `grid.py` (scenario grid, cached in results/), `summarize.py`, `diag.py`
(supply curves), `deaths.py` (outcome breakdown), `cond.py` (A given Perkeo), `sens.py` (robustness).
Stand-ins, not measured: money for rerolls, the scoring of the pre-Baron engine, deck building on time,
no misplays, bosses other than The Serpent ignored.

## Version check and 1.1 projection (Oct 14, 2026, `v11.py`)

Latest playable build is still 1.0.1o (Friends of Jimbo 4, Feb 24 2025): Steam's news feed has no patch
since, and 1.1 exists only as LocalThunk's Sept 2026 Discord preview. The wiki odds above are 1.0.1o's.
1.1 as previewed: at least 4 new jokers (rarities unknown), a tier 2 voucher "Lunker" (a 17th set),
a voucher rule "N tier 1s of M incomplete sets -> N in M chance of a tier 2" (the same odds as today's
uniform draw, so unmodelled), all behind an opt-in profile toggle.

| Typical economy, 40k runs | Perkeo Ghost | Plasma Burglar |
|---|---|---|
| 1.0.1o (current) | 1.56% | 8.87% |
| 1.1, new jokers common | 1.51% | 7.20% |
| 1.1, 2 uncommon + 2 rare | 1.19% | 6.15% |
| 1.1, all 4 rare | 1.08% | 5.53% |

Lean/rich, 20k runs: 1.0.1o A 0.39/3.52%, B 2.81/16.32%; 1.1 mixed A 0.29/3.29%, B 1.74/11.77%.
The extra voucher set alone costs B ~1.7 points: it needs Antimatter, Retcon and Palette or Nacho Tong.

## Reset strategies: hours per naneinf (`timing.py`, Oct 14, 2026)

Time model (typical): 4 / 7 / 10 / 14 minutes per ante for antes 1-8 / 9-16 / 17-24 / 25+; a reset-and-look
takes 10 s, skipping for a Charm Tag and opening its Mega Arcana 30 s. Reset rules found by optimal
stopping (backward induction + Dinkelbach), fitted on half of 40k runs and scored on the other half.

| Plan | Hours per naneinf (typical) | fast / slow model |
|---|---|---|
| Perkeo Ghost, play every run out | 90 | 65 / 115 |
| Perkeo Ghost, best reset rule (reset unless Perkeo early) | 53 | 39 / 66 |
| Perkeo Ghost, Charm Tag resets at ante 1 | 34 | 22 / 50 |
| Plasma Burglar, play every run out | 29 | 21 / 39 |
| Plasma Burglar, best reset rule | 28 | 20 / 38 |

Charm resets: P(Perkeo) 0.041% per reset (~2,430 resets per Perkeo); a run that starts with Perkeo wins
32.8%. 85% of the plan's time is resetting, so it beats the Plasma plan when a look takes under ~8 s,
or when deep antes take 20+ minutes (results/timing_breakeven.json). Resetting barely helps the Plasma
plan: its failures (no Baron+Mime by 17, slots/hands by 24-26) are not visible early.

## The simulated Plasma player, a weaker early game, and how many seeds hold the pieces (`weak.py`)

What the simulated player does: antes 1-8 are assumed won (their shops, packs, tags and vouchers count).
From ante 9 each blind is scored: the best of a fixed pre-Baron engine ("bridge", log10 Mult) and the held
Red Seal Steel King engine (Baron and/or Mime plus copies, exact arithmetic). It skips Small/Big blinds it
can't beat; bosses are mandatory, using The Serpent when Retcon (or a Director's Cut reroll) allows. Shops:
rerolls with the economy scenario's budget while hunting; buys Baron, Mime, Blueprint, Brainstorm (more with
Showman, up to its slots), Showman, Invisible Joker, Burglar, Turtle Bean or DNA from ante 18; buys and sells
Diet Cola for Double Tags and skips for Voucher/Rare tags with them; opens every Buffoon, Arcana and Spectral
pack; one Ectoplasm (two if every slot already holds a copy). Vouchers: everything except Tarot Tycoon,
Planet Merchant/Tycoon and Hieroglyph. Money is an input (gold-king economy is not simulated), and so is
deck building.

Since this change, Baron alone or Mime alone also scores off held kings (it raised B at bridge 12 from 9.0%
to 10.1%; the earlier tables predate it). Typical economy, 20k runs:

| Pre-Baron engine (log10 Mult) | dies without Baron at (Plasma) | Plasma Burglar | Perkeo Ghost |
|---|---|---|---|
| 3.5 | ante 11 | 5.83% | 0.78% |
| 5 | ante 13 | 6.73% | |
| 8 | ante 15 | 7.41% | |
| 12 | ante 17 | 10.12% | 1.76% |

Supply if the run never dies (every blind played): every Burglar-finish piece (Baron, Mime, 4 copies,
Burglar, 7 slots, enough hands and hand size) by ante 24 / 26 / 31 in 19.6 / 28.7 / 47.7% of seeds;
with Retcon as well, 11.9 / 19.8 / 39.8%.
