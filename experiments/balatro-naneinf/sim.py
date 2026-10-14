"""Monte Carlo of a Balatro run's item supply, for two naneinf plans (game version 1.0.1).

A  Perkeo, Ghost Deck: Perkeo makes a Negative Cryptid every shop (plus one per Blueprint/
   Brainstorm copying it). Cryptids add Red Seal Steel Kings to hand without scoring, so the
   naneinf hand can be played on any blind once enough are stockpiled. Traditional scoring.
B  Plasma Deck, Baron + Mime + 4 copiers + Burglar against The Serpent (wiki Guide: naneinf).
H  Plasma Deck, B's plan, but switch to A's Cryptid finish if Perkeo turns up (seed Cryptid
   from Sixth Sense, since Plasma has no Spectral cards in the shop).

What is modelled exactly (odds from the 1.0.1 code as documented on balatrowiki.org):
shop card weights, joker rarity 70/25/5 and pool sizes 61/64/20, no duplicates without Showman,
Negative edition 0.3%, pack weights and sizes, The Soul at 0.3% per Arcana/Spectral card,
Omen Globe 20%, 24 skip tags (15 in ante 1), 1 voucher per ante from the 32-voucher tree,
reroll prices, blind sizes (verified against the wiki's table), Plasma balancing,
Baron/Mime/Steel/Red Seal arithmetic, Burglar copies, Serpent draws, Ectoplasm's growing cost.

What is a stand-in (see PARAMS): money for rerolls (three economy scenarios), the scoring of
whatever engine carries the run before Baron + Mime (BRIDGE), deck building (assumed done
on time), boss risk other than The Serpent (ignored), player mistakes (none).
"""
import math, random

LOG15 = math.log10(1.5)
MAXLOG = math.log10(1.7976931348623157e308)          # 308.2547: score that overflows
NAN_PLASMA_M = math.log10(2) + MAXLOG / 2            # Plasma: ((c+m)/2)^2 overflows when m >= 2*sqrt(max)
CHIPS_LOG = math.log10(115)   # High Card lvl 10 (95 chips) + a Red Seal King scored twice
BASEMULT_LOG = 1.0            # High Card lvl 10 = 10 Mult

AMOUNTS = [300, 800, 2000, 5000, 11000, 20000, 35000, 50000]


def base_amount(a):
    if a <= 8:
        return AMOUNTS[a - 1]
    c, d = a - 8, 1 + 0.2 * (a - 8)
    x = (1.6 + (0.75 * c) ** d) ** c
    amt = math.floor(50000 * x)
    return amt - amt % (10 ** math.floor(math.log10(amt) - 1))


def req_log(a, blind, plasma):
    if a >= 39:
        return float('inf')
    mult = {'small': 1, 'big': 1.5, 'boss': 2}[blind]
    return math.log10(base_amount(a) * mult * (2 if plasma else 1))


def S(k):
    """X1.5 triggers per held Red Seal Steel King with Baron, Mime and k extra copies."""
    return max((3 + m) * (2 + (k - m)) for m in range(k + 1))


def kings_needed(k, plasma):
    s = S(k) * LOG15
    if plasma:
        return math.ceil((NAN_PLASMA_M - BASEMULT_LOG) / s)
    return math.ceil((MAXLOG - CHIPS_LOG - BASEMULT_LOG) / s)


def cryptids_needed(k, plasma, hand_size):
    # start with a full hand of kings, add 2 per Cryptid, then play 1 card and hold the rest
    return max(0, math.ceil((kings_needed(k, plasma) + 1 - hand_size) / 2))


def score_log(mult_log, plasma):
    return 2 * (mult_log - math.log10(2)) if plasma else mult_log + CHIPS_LOG


# ---------------------------------------------------------------- item tables
RARES = 20
UNCOMMONS = 64
RARE_KEYS = {'Baron', 'Blueprint', 'Brainstorm', 'Invisible', 'DNA'}
UNC_KEYS = {'Mime', 'Showman', 'Burglar', 'TurtleBean', 'SixthSense'}
PACKS = [('Standard', 'normal', 4), ('Standard', 'jumbo', 2), ('Standard', 'mega', .5),
         ('Arcana', 'normal', 4), ('Arcana', 'jumbo', 2), ('Arcana', 'mega', .5),
         ('Celestial', 'normal', 4), ('Celestial', 'jumbo', 2), ('Celestial', 'mega', .5),
         ('Buffoon', 'normal', 1.2), ('Buffoon', 'jumbo', .6), ('Buffoon', 'mega', .15),
         ('Spectral', 'normal', .6), ('Spectral', 'jumbo', .3), ('Spectral', 'mega', .07)]
PACK_W = [p[2] for p in PACKS]
PACK_CARDS = {('Arcana', 'normal'): (3, 1), ('Arcana', 'jumbo'): (5, 1), ('Arcana', 'mega'): (5, 2),
              ('Buffoon', 'normal'): (2, 1), ('Buffoon', 'jumbo'): (4, 1), ('Buffoon', 'mega'): (4, 2),
              ('Spectral', 'normal'): (2, 1), ('Spectral', 'jumbo'): (4, 1), ('Spectral', 'mega'): (4, 2)}
SPECTRALS = 16  # in shop/packs (The Soul and Black Hole are separate 0.3% rolls)
TAGS_ANTE1 = ['Uncommon', 'Rare', 'Foil', 'Holo', 'Poly', 'Investment', 'Voucher', 'Boss', 'Charm',
              'Coupon', 'Double', 'Juggle', 'D6', 'Speed', 'Economy']
TAGS_ALL = TAGS_ANTE1 + ['Negative', 'Standard', 'Meteor', 'Buffoon', 'Handy', 'Garbage',
                         'Ethereal', 'Topup', 'Orbital']
VOUCHER_PAIRS = [('Overstock', 'Overstock Plus'), ('Clearance Sale', 'Liquidation'), ('Hone', 'Glow Up'),
                 ('Reroll Surplus', 'Reroll Glut'), ('Crystal Ball', 'Omen Globe'), ('Telescope', 'Observatory'),
                 ('Grabber', 'Nacho Tong'), ('Wasteful', 'Recyclomancy'), ('Tarot Merchant', 'Tarot Tycoon'),
                 ('Planet Merchant', 'Planet Tycoon'), ('Seed Money', 'Money Tree'), ('Blank', 'Antimatter'),
                 ('Magic Trick', 'Illusion'), ('Hieroglyph', 'Petroglyph'), ("Director's Cut", 'Retcon'),
                 ('Paint Brush', 'Palette')]
UPGRADE_OF = {b: u for b, u in VOUCHER_PAIRS}
AVOID = {
    'A': {'Tarot Merchant', 'Tarot Tycoon', 'Planet Merchant', 'Planet Tycoon', 'Magic Trick', 'Hieroglyph'},
    'B': {'Tarot Tycoon', 'Planet Merchant', 'Planet Tycoon', 'Hieroglyph'},
}
AVOID['H'] = AVOID['B']
NON_SHOWDOWN_BOSSES_ANTE5 = 22   # boss pool The Serpent is drawn from (ante 5+)

ECONOMY = {  # $ per shop spent on rerolls, by ante band (upper bound, dollars)
    'lean':    [(4, 0), (8, 5), (12, 15), (16, 40), (24, 100), (99, 200)],
    'typical': [(4, 5), (8, 15), (12, 40), (16, 100), (24, 250), (99, 500)],
    'rich':    [(4, 10), (8, 25), (12, 100), (16, 300), (24, 750), (99, 1500)],
}

PARAMS = dict(
    bridge=12.0,          # log10 Mult of the pre-Baron engine (Idol/glass/retriggers) from ante 9 on
    max_ecto=None,        # Ectoplasms a player will use (None: 2 on the Perkeo plan, 1 on Plasma, per the guide)
    skip_hunt=False,      # skip Small/Big blinds in antes 2-12 for useful tags
    sixth_sense_hit=0.5,  # chance a round's first hand can be a lone 6 (Sixth Sense)
    diet_cola=True,       # buy and sell every Diet Cola seen for a Double Tag, cash them in on a key tag
)


def geometric_count(rng, n, p, cap):
    """Successes in n Bernoulli(p) trials, stopping at cap."""
    if p <= 0 or n <= 0 or cap <= 0:
        return 0
    if p >= 1:
        return min(n, cap)
    count, pos, lq = 0, 0, math.log(1 - p)
    while count < cap:
        pos += int(math.log(1 - rng.random()) / lq) + 1
        if pos > n:
            break
        count += 1
    return count


class Run:
    def __init__(self, strat, econ, rng, params, immortal=False):
        self.s, self.rng, self.p = strat, rng, params
        self.plasma = strat in ('B', 'H')
        self.ghost = strat == 'A'
        self.econ = ECONOMY[econ]
        self.immortal = immortal
        if self.p['max_ecto'] is None:
            self.p = dict(self.p, max_ecto=2 if strat == 'A' else 1)
        self.own = {k: 0 for k in ['Baron', 'Mime', 'Blueprint', 'Brainstorm', 'Showman', 'Invisible', 'Burglar',
                                   'TurtleBean', 'DNA', 'Perkeo', 'SixthSense']}
        self.V = set()
        self.neg = 0
        self.ecto_used = 0
        self.inv_rounds = None    # rounds held for Invisible Joker
        self.inv_dup = 0
        self.seed = False         # holds a Cryptid for Perkeo to copy
        self.cryptids = 0         # Negative Cryptids stockpiled
        self.ecto_held = 0
        self.juggle = 0
        self.doubles = 0
        self.first_shop = True
        self.first = {}           # first ante each milestone was reached
        self.ante = 1
        self.result = None

    # ------------------------------------------------------------ derived state
    def slots(self):
        return 5 + ('Antimatter' in self.V) + self.neg + self.ecto_used

    def copiers(self):
        return self.own['Blueprint'] + self.own['Brainstorm']

    def boost(self):
        """Extra Baron/Mime effects beyond the first of each: copiers, duplicates, Invisible copies."""
        return (self.copiers() + max(0, self.own['Baron'] - 1) + max(0, self.own['Mime'] - 1) + self.inv_dup)

    def engine(self):
        return self.own['Baron'] >= 1 and self.own['Mime'] >= 1

    def hand_size(self):
        n = self.ecto_used
        return 8 + ('Paint Brush' in self.V) + ('Palette' in self.V) - n * (n + 1) // 2

    def perkeo_route(self):
        return self.s in ('A', 'H') and self.own['Perkeo'] > 0

    def k_cap(self):
        """Copies the slots allow alongside the jokers the plan must hold."""
        if self.perkeo_route():
            return self.slots() - 3          # Perkeo, Baron, Mime
        if self.s in ('B', 'H'):
            return self.slots() - 2          # Baron, Mime (Burglar needs one more at the end)
        return self.slots() - 3

    def k_used(self):
        return max(0, min(self.boost(), self.k_cap()))

    def mark(self, key):
        if key not in self.first:
            self.first[key] = self.ante

    def note_milestones(self):
        if self.own['Perkeo']: self.mark('Perkeo')
        if self.own['Baron']: self.mark('Baron')
        if self.own['Mime']: self.mark('Mime')
        if self.engine(): self.mark('Baron+Mime')
        if self.own['Burglar']: self.mark('Burglar')
        if self.own['Showman']: self.mark('Showman')
        for k in (1, 2, 3, 4):
            if self.boost() >= k: self.mark(f'copies>={k}')
        if self.seed: self.mark('seed Cryptid')
        for v in ('Antimatter', 'Retcon', "Director's Cut", 'Palette', 'Paint Brush', 'Nacho Tong', 'Grabber',
                  'Omen Globe', 'Reroll Glut'):
            if v in self.V: self.mark(v)
        if self.slots() >= 7: self.mark('7 slots')

    # ------------------------------------------------------------ wants
    def ecto_limit(self):
        lim = self.p['max_ecto']
        if self.s in ('B', 'H') and self.p.get('smart_ecto', True) and self.own['Showman'] and self.boost() >= self.k_cap():
            lim = max(lim, 2)
        return lim

    def want_ecto(self):
        target = 8 if self.ecto_limit() >= 2 and self.s in ('B', 'H') else 7
        return self.ecto_used + self.ecto_held < self.ecto_limit() and self.slots() + self.ecto_held < target

    def wants(self):
        w = {}
        room = self.boost() < self.k_cap()
        for j in ('Baron', 'Mime'):
            if self.own[j] == 0:
                w[j] = 1
            elif self.own['Showman'] and room:
                w[j] = 1
        for j in ('Blueprint', 'Brainstorm'):
            if (self.own[j] == 0 or self.own['Showman']) and room:
                w[j] = 1
        if self.own['Showman'] == 0 and self.copiers() >= 1 and room:
            w['Showman'] = 1
        if room and self.own['Invisible'] == 0 and self.inv_dup == 0:
            w['Invisible'] = 1
        if self.s in ('B', 'H') and self.own['Burglar'] == 0:
            w['Burglar'] = 1
        if self.s in ('B', 'H') and self.ante >= 18 and not (self.own['TurtleBean'] or self.own['DNA']):
            w['TurtleBean'] = 1
            w['DNA'] = 1
        if self.s == 'H' and self.own['Perkeo'] and not self.seed and not self.own['SixthSense']:
            w['SixthSense'] = 1
        return w

    def owned_rares(self):
        return sum(1 for j in RARE_KEYS if self.own[j])

    def owned_uncs(self):
        return sum(1 for j in UNC_KEYS if self.own[j])

    def gain(self, j):
        self.own[j] += 1
        if self.rng.random() < 0.003:
            self.neg += 1
        if j == 'Invisible':
            self.inv_rounds = 0

    # ------------------------------------------------------------ vouchers
    def voucher_draw(self):
        pool = []
        for b, u in VOUCHER_PAIRS:
            if b not in self.V:
                pool.append(b)
            elif u not in self.V:
                pool.append(u)
        if not pool:
            return
        v = self.rng.choice(pool)
        if v not in AVOID[self.s]:
            self.V.add(v)

    # ------------------------------------------------------------ shop
    def shop_weights(self):
        tarot = 32 if 'Tarot Tycoon' in self.V else 9.6 if 'Tarot Merchant' in self.V else 4
        planet = 32 if 'Planet Tycoon' in self.V else 9.6 if 'Planet Merchant' in self.V else 4
        spec = 2 if self.ghost else 0
        play = 4 if 'Magic Trick' in self.V else 0
        return 20 + tarot + planet + spec + play, spec

    def budget(self):
        for top, d in self.econ:
            if self.ante <= top:
                return d
        return self.econ[-1][1]

    def rerolls(self):
        c0 = max(1, 5 - 2 * ('Reroll Surplus' in self.V) - 2 * ('Reroll Glut' in self.V))
        b, n = self.budget(), 0
        while b >= c0 + n:
            b -= c0 + n
            n += 1
        return n

    def joker_p(self, j, pjoker):
        if j in RARE_KEYS:
            avail = RARES if self.own['Showman'] else RARES - self.owned_rares()
            return pjoker * 0.05 / max(avail, 1)
        avail = UNCOMMONS if self.own['Showman'] else UNCOMMONS - self.owned_uncs()
        return pjoker * 0.25 / max(avail, 1)

    def random_joker(self, rarity_roll=None):
        r = self.rng.random() if rarity_roll is None else rarity_roll
        w = self.wants()
        if r < 0.70:
            return None
        if r < 0.95:
            avail = UNCOMMONS if self.own['Showman'] else UNCOMMONS - self.owned_uncs()
            cands = [j for j in w if j in UNC_KEYS]
        else:
            avail = RARES if self.own['Showman'] else RARES - self.owned_rares()
            cands = [j for j in w if j in RARE_KEYS]
        if cands and self.rng.random() < len(cands) / max(avail, 1):
            return self.rng.choice(cands)
        return None

    PRIORITY = ['Perkeo', 'Baron', 'Mime', 'Blueprint', 'Brainstorm', 'Burglar', 'Showman', 'Invisible',
                'Ectoplasm', 'SixthSense', 'TurtleBean', 'DNA']

    def open_pack(self, kind, size):
        n, choose = PACK_CARDS[(kind, size)]
        found = []
        if kind == 'Buffoon':
            if not self.wants():
                return
            for _ in range(n):
                j = self.random_joker()
                if j and j not in found:
                    found.append(j)
        else:
            soul = False
            for _ in range(n):
                if not soul and self.rng.random() < 0.003:
                    soul = True
                    found.append('Soul')
                    continue
                spectral = kind == 'Spectral' or ('Omen Globe' in self.V and self.rng.random() < 0.2)
                if spectral and self.rng.random() < 1 / SPECTRALS and self.want_ecto():
                    if 'Ectoplasm' not in found:
                        found.append('Ectoplasm')
        found.sort(key=lambda x: 0 if x == 'Soul' else self.PRIORITY.index(x))
        for f in found[:choose]:
            if f == 'Soul':
                self.mark('a Soul')
                if self.s in ('A', 'H') and not self.own['Perkeo'] and self.rng.random() < 0.2:
                    self.own['Perkeo'] = 1
            elif f == 'Ectoplasm':
                self.ecto_held += 1
            else:
                if f in self.wants():
                    self.gain(f)
        self.use_ecto()

    def use_ecto(self):
        target = 8 if self.ecto_limit() >= 2 and self.s in ('B', 'H') else 7
        while self.ecto_held and self.ecto_used < self.ecto_limit() and self.slots() < target:
            self.ecto_held -= 1
            self.ecto_used += 1

    def shop(self):
        W, spec = self.shop_weights()
        pjoker = 20 / W
        slots = 2 + ('Overstock' in self.V) + ('Overstock Plus' in self.V)
        w = self.wants()
        shop_wants = dict(w)
        if self.ghost:
            if self.own['Perkeo'] and not self.seed:
                shop_wants['Cryptid'] = 1
            if self.want_ecto():
                shop_wants['Ectoplasm'] = 1
        n = slots * (1 + (self.rerolls() if shop_wants else 0))
        order = [j for j in self.PRIORITY if j in shop_wants] + [j for j in shop_wants if j not in self.PRIORITY]
        for j in order:
            if j == 'Cryptid':
                if geometric_count(self.rng, n, spec / W / SPECTRALS, 1):
                    self.seed = True
                continue
            if j == 'Ectoplasm':
                self.ecto_held += geometric_count(self.rng, n, spec / W / SPECTRALS, 1)
                self.use_ecto()
                continue
            if j not in self.wants():
                continue
            dup_ok = self.own['Showman'] and j in ('Baron', 'Mime', 'Blueprint', 'Brainstorm')
            cap = max(1, self.k_cap() - self.boost()) if dup_ok else 1
            got = geometric_count(self.rng, n, self.joker_p(j, pjoker), cap)
            for _ in range(got):
                if j in self.wants():
                    self.gain(j)
        if self.p['diet_cola'] and shop_wants:
            avail = UNCOMMONS if self.own['Showman'] else UNCOMMONS - self.owned_uncs()
            self.doubles += geometric_count(self.rng, n, pjoker * 0.25 / avail, 50)
        # booster packs
        packs = []
        if self.first_shop:
            packs.append(('Buffoon', 'normal'))
            self.first_shop = False
        while len(packs) < 2:
            kind, size, _ = self.rng.choices(PACKS, PACK_W)[0]
            packs.append((kind, size))
        for kind, size in packs:
            if kind in ('Buffoon', 'Arcana', 'Spectral'):
                self.open_pack(kind, size)
        # leaving the shop: Perkeo and its copies
        if self.perkeo_route() and self.seed:
            self.cryptids += 1 + min(self.copiers(), max(self.k_cap(), 0))
        self.note_milestones()

    def round_played(self):
        if self.inv_rounds is not None and self.own['Invisible']:
            self.inv_rounds += 1
            if self.inv_rounds >= 2 and self.boost() < self.k_cap():
                self.own['Invisible'] = 0
                self.inv_dup += 1
                self.inv_rounds = None
        if self.s == 'H' and self.own['SixthSense'] and self.own['Perkeo'] and not self.seed:
            if self.rng.random() < self.p['sixth_sense_hit'] / SPECTRALS:
                self.seed = True

    # ------------------------------------------------------------ tags
    def take_tag(self, tag):
        copies = 1 + self.doubles if tag != 'Double' else 1
        if tag != 'Double':
            self.doubles = 0
        for _ in range(copies):
            if tag == 'Double':
                self.doubles += 1
            elif tag == 'Charm':
                self.open_pack('Arcana', 'mega')
            elif tag == 'Ethereal':
                self.open_pack('Spectral', 'normal')
            elif tag == 'Buffoon':
                self.open_pack('Buffoon', 'mega')
            elif tag in ('Rare', 'Uncommon'):
                j = self.random_joker(0.99 if tag == 'Rare' else 0.80)
                if j and j in self.wants():
                    self.gain(j)
            elif tag == 'Voucher':
                self.voucher_draw()
            elif tag == 'Juggle':
                self.juggle += 3
        self.note_milestones()

    def missing_vouchers(self):
        need = {'Antimatter', 'Retcon'} | ({'Palette', 'Nacho Tong'} if self.s in ('B', 'H') else set())
        return bool(need - self.V)

    def cash_in(self, tag):
        """Skip a Small/Big blind to spend stored Double Tags on a tag that supplies a missing piece."""
        if not self.p['diet_cola'] or self.doubles < 1:
            return False
        if tag == 'Voucher':
            return self.missing_vouchers()
        if tag == 'Rare':
            return any(j in RARE_KEYS for j in self.wants())
        if tag == 'Charm':
            return self.s in ('A', 'H') and not self.own['Perkeo']
        if tag == 'Juggle':
            return self.s in ('B', 'H') and self.ante >= 24 and self.own['Burglar'] and not self.burglar_attempt(float('inf'))
        if tag == 'Ethereal':
            return self.want_ecto() or (self.s in ('A', 'H') and not self.own['Perkeo'])
        return False

    def offered_tag(self):
        return self.rng.choice(TAGS_ANTE1 if self.ante == 1 else TAGS_ALL)

    # ------------------------------------------------------------ scoring
    def mult_log(self, serpent=False, extra_held=0, burglar_hands=False):
        """Best log10 Mult the run can put up on one blind."""
        best = self.p['bridge'] if self.ante >= 9 else 99
        if not self.engine():
            return best
        k = self.k_used()
        hs = self.hand_size() + extra_held
        held = hs - 1
        if serpent:
            hands = 4 + ('Grabber' in self.V) + ('Nacho Tong' in self.V)
            discards = 3 + ('Wasteful' in self.V) + ('Recyclomancy' in self.V)
            held = hs - 1 + 2 * (hands + discards - 1)
        options = [held * LOG15 * S(k)]
        helper = self.own['TurtleBean'] or self.own['DNA']
        if helper and not serpent:   # +5 cards in hand, costs a slot
            k2 = max(0, min(self.boost(), self.k_cap() - 1))
            options.append((held + 5) * LOG15 * S(k2))
        return max(best, max(options) + BASEMULT_LOG)

    def serpent_available(self):
        if self.ante % 8 == 0 or self.ante < 5:
            return False
        if 'Retcon' in self.V:
            return True
        draws = 2 if "Director's Cut" in self.V else 1
        return self.rng.random() < 1 - (1 - 1 / NON_SHOWDOWN_BOSSES_ANTE5) ** draws

    # ------------------------------------------------------------ finishes
    def perkeo_ready(self):
        if not (self.perkeo_route() and self.engine()):
            return False
        k = max(0, min(self.boost(), self.slots() - 3))
        return self.cryptids >= cryptids_needed(k, self.plasma, self.hand_size())

    def burglar_attempt(self, R_boss):
        """Plasma + Serpent + Burglar finish on this boss, if the pieces and the timing allow."""
        if not (self.s in ('B', 'H') and self.engine() and self.own['Burglar']):
            return False
        best = False
        hs = self.hand_size() + self.juggle
        for k in range(0, min(self.boost(), self.slots() - 3) + 1):
            cop = min(self.copiers(), k)
            hands = 4 + ('Grabber' in self.V) + ('Nacho Tong' in self.V) + 3 * (1 + cop)
            K = kings_needed(k, True)
            j = next((j for j in range(1, hands + 1) if hs + 2 * (j - 1) - 1 >= K), None)
            if j is None:
                continue
            # build-up hands score with copiers parked on Burglar; they must not win the blind early
            dupB, dupM = max(0, self.own['Baron'] - 1), max(0, self.own['Mime'] - 1)
            s_build = (3 + dupM) * (2 + dupB)
            total = 0.0
            for i in range(1, j):
                held = hs + 2 * (i - 1) - 1
                total += 10 ** (score_log(held * LOG15 * s_build + BASEMULT_LOG, True) - 200)
            premature = total > 0 and math.log10(total) + 200 >= R_boss
            if not premature:
                best = True
                break
        return best

    # ------------------------------------------------------------ survival
    def beat(self, blind, mandatory):
        """Try to beat a blind; returns 'play', 'skip' or 'dead'."""
        if self.ante <= 8 or self.immortal:
            return 'play'
        R = req_log(self.ante, blind, self.plasma)
        ex = self.juggle
        cap = score_log(self.mult_log(extra_held=ex), self.plasma)
        if cap >= R:
            self.juggle = 0
            return 'play'
        if blind == 'boss' and self.serp:
            cap = score_log(self.mult_log(serpent=True, extra_held=ex), self.plasma)
            if cap >= R:
                self.juggle = 0
                return 'play'
        # Perkeo route: spend Cryptids to add held kings
        if self.perkeo_route() and self.engine() and self.cryptids:
            per = 2 * LOG15 * S(self.k_used()) * (2 if self.plasma else 1)
            need = math.ceil((R - cap) / per)
            worth = mandatory or need <= 1 + min(self.copiers(), max(self.k_cap(), 0))
            if need <= self.cryptids and worth:
                self.cryptids -= need
                self.juggle = 0
                return 'play'
        if not mandatory:
            return 'skip'
        return 'play' if self.immortal else 'dead'

    # ------------------------------------------------------------ main loop
    def run(self):
        hunt_tags = {'Rare', 'Buffoon', 'Uncommon'} | ({'Charm', 'Ethereal'} if self.s in ('A', 'H') else set())
        while self.ante <= 38:
            self.voucher_draw()
            self.note_milestones()
            for blind in ('small', 'big', 'boss'):
                if not self.immortal and self.perkeo_ready():
                    self.result = ('naneinf', self.ante, 'Perkeo')
                    return self
                tag = self.offered_tag() if blind != 'boss' else None
                if blind == 'boss':
                    self.serp = self.serpent_available()
                if blind == 'boss' and not self.immortal and self.ante >= 9:
                    R = req_log(self.ante, 'boss', self.plasma)
                    if self.s in ('B', 'H') and self.own['Burglar'] and self.serp:
                        if self.burglar_attempt(R):
                            self.result = ('naneinf', self.ante, 'Burglar')
                            return self
                if blind != 'boss' and ((self.p['skip_hunt'] and 2 <= self.ante <= 12 and tag in hunt_tags)
                                        or self.cash_in(tag)):
                    self.take_tag(tag)
                    continue
                outcome = self.beat(blind, mandatory=(blind == 'boss'))
                if outcome == 'dead':
                    self.result = ('dead', self.ante, self.why())
                    return self
                if outcome == 'skip':
                    self.take_tag(tag)
                    continue
                self.round_played()
                self.shop()
            self.ante += 1
        self.result = ('dead', 39, self.why()) if not self.immortal else ('immortal', 39, '')
        return self

    def why(self):
        if self.s == 'A' or (self.s == 'H' and self.own['Perkeo']):
            if not self.own['Perkeo']:
                return 'no Perkeo'
            if not self.seed:
                return 'Perkeo but no Cryptid to copy'
        if not self.engine():
            return 'no Baron+Mime'
        if self.s in ('B', 'H') and not self.own['Perkeo']:
            if self.boost() < 4:
                return 'fewer than 4 copies'
            if self.slots() < 7:
                return 'fewer than 7 joker slots'
            if not self.own['Burglar']:
                return 'no Burglar'
            if not self.burglar_attempt(-1e9 + 1e9 * 0 + float('inf')):
                return 'too few hands or hand size'
            if 'Retcon' not in self.V:
                return 'no Retcon (no Serpent on demand)'
            return 'pieces in hand, died first'
        return 'too few Cryptids in time'


def simulate(strat, econ, n, seed=0, params=None, immortal=False):
    p = dict(PARAMS)
    if params:
        p.update(params)
    rng = random.Random(seed)
    return [Run(strat, econ, rng, p, immortal).run() for _ in range(n)]
