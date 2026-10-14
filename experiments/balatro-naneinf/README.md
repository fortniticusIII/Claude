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
