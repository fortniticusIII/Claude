"""Which countries a headline is about, by name, demonym, capital or a few stable stand-ins.

    from wire.places import tag, NAMES
    tag("Russian drones hit Kharkiv as Kyiv seeks more air defence")   -> {"RU", "UA"}
    tag("drone-strike-on-power-facility-in-poltava", slug=True)         -> {"UA"}

Rules, chosen for consistency over time rather than perfect recall:
- Places only: country names, demonyms (plural too), capitals and well-known cities or regions that
  belong unambiguously to one country (Kharkiv, Gaza, Xinjiang). No leader names: leaders change,
  and a gauge compared against its own past must tag the same way every week.
- A handful of stable institutional stand-ins: Kremlin, Pentagon, White House, Downing Street, IDF,
  Knesset, and the armed groups most tied to one territory (Hamas, Hezbollah, Houthis, Taliban).
- Longest match first, so "South Sudan" never also counts "Sudan", and "Papua New Guinea" never
  counts "Guinea". Seas and regions named after a country ("South China Sea", "Indian Ocean",
  "Gulf of Mexico", "Latin America") are consumed and count as nothing.
- Ambiguities: bare "Korea"/"Korean" counts as neither Korea. "Georgia" counts as the country unless
  the same headline has a US-state signal (Atlanta, a US marker, county, governor...). In real
  titles "US"/"U.S." must be upper case; in URL slugs (all lower case) the word "us" counts as the
  United States, which over-counts slightly where a headline uses the pronoun.
Codes are ISO 3166 alpha-2, plus XK (Kosovo).
"""
from __future__ import annotations

import re
import unicodedata

# code: (display name, [aliases]). Aliases are lower case words; plurals are added automatically.
COUNTRIES = {
    "AF": ("Afghanistan", ["afghanistan", "afghan", "kabul", "taliban"]),
    "AL": ("Albania", ["albania", "albanian", "tirana"]),
    "DZ": ("Algeria", ["algeria", "algerian", "algiers"]),
    "AD": ("Andorra", ["andorra"]),
    "AO": ("Angola", ["angola", "angolan", "luanda"]),
    "AG": ("Antigua and Barbuda", ["antigua"]),
    "AR": ("Argentina", ["argentina", "argentine", "argentinian", "buenos aires"]),
    "AM": ("Armenia", ["armenia", "armenian", "yerevan"]),
    "AU": ("Australia", ["australia", "australian", "canberra", "sydney", "melbourne"]),
    "AT": ("Austria", ["austria", "austrian", "vienna"]),
    "AZ": ("Azerbaijan", ["azerbaijan", "azerbaijani", "azeri", "baku"]),
    "BS": ("Bahamas", ["bahamas", "bahamian"]),
    "BH": ("Bahrain", ["bahrain", "bahraini", "manama"]),
    "BD": ("Bangladesh", ["bangladesh", "bangladeshi", "dhaka"]),
    "BB": ("Barbados", ["barbados"]),
    "BY": ("Belarus", ["belarus", "belarusian", "minsk", "lukashenko"]),
    "BE": ("Belgium", ["belgium", "belgian"]),
    "BZ": ("Belize", ["belize"]),
    "BJ": ("Benin", ["benin", "beninese"]),
    "BT": ("Bhutan", ["bhutan"]),
    "BO": ("Bolivia", ["bolivia", "bolivian", "la paz"]),
    "BA": ("Bosnia and Herzegovina", ["bosnia", "bosnian", "herzegovina", "sarajevo", "republika srpska"]),
    "BW": ("Botswana", ["botswana"]),
    "BR": ("Brazil", ["brazil", "brazilian", "brasilia", "rio de janeiro", "sao paulo"]),
    "BN": ("Brunei", ["brunei"]),
    "BG": ("Bulgaria", ["bulgaria", "bulgarian"]),
    "BF": ("Burkina Faso", ["burkina faso", "burkina", "burkinabe", "ouagadougou"]),
    "BI": ("Burundi", ["burundi", "burundian"]),
    "CV": ("Cabo Verde", ["cabo verde", "cape verde"]),
    "KH": ("Cambodia", ["cambodia", "cambodian", "phnom penh"]),
    "CM": ("Cameroon", ["cameroon", "cameroonian", "yaounde"]),
    "CA": ("Canada", ["canada", "canadian", "ottawa", "toronto", "montreal", "vancouver"]),
    "CF": ("Central African Republic", ["central african republic", "bangui"]),
    "TD": ("Chad", ["chad", "chadian", "n djamena", "ndjamena"]),
    "CL": ("Chile", ["chile", "chilean"]),
    "CN": ("China", ["china", "chinese", "beijing", "shanghai", "xinjiang", "uyghur", "uighur", "prc", "tibet", "tibetan"]),
    "CO": ("Colombia", ["colombia", "colombian", "bogota"]),
    "KM": ("Comoros", ["comoros"]),
    "CG": ("Republic of the Congo", ["republic of the congo", "republic of congo", "congo brazzaville", "brazzaville"]),
    "CD": ("DR Congo", ["democratic republic of the congo", "democratic republic of congo", "dr congo", "drc", "congo",
                        "congolese", "kinshasa", "goma", "kivu"]),
    "CR": ("Costa Rica", ["costa rica", "costa rican"]),
    "CI": ("Côte d'Ivoire", ["cote d ivoire", "ivory coast", "ivorian", "abidjan"]),
    "HR": ("Croatia", ["croatia", "croatian", "zagreb"]),
    "CU": ("Cuba", ["cuba", "cuban", "havana"]),
    "CY": ("Cyprus", ["cyprus", "cypriot", "nicosia"]),
    "CZ": ("Czechia", ["czechia", "czech republic", "czech", "prague"]),
    "DK": ("Denmark", ["denmark", "danish", "copenhagen", "dane"]),
    "DJ": ("Djibouti", ["djibouti"]),
    "DM": ("Dominica", ["dominica"]),
    "DO": ("Dominican Republic", ["dominican republic", "dominican", "santo domingo"]),
    "EC": ("Ecuador", ["ecuador", "ecuadorian", "ecuadorean", "quito"]),
    "EG": ("Egypt", ["egypt", "egyptian", "cairo", "sinai"]),
    "SV": ("El Salvador", ["el salvador", "salvadoran", "salvadorean", "san salvador"]),
    "GQ": ("Equatorial Guinea", ["equatorial guinea"]),
    "ER": ("Eritrea", ["eritrea", "eritrean", "asmara"]),
    "EE": ("Estonia", ["estonia", "estonian", "tallinn"]),
    "SZ": ("Eswatini", ["eswatini", "swaziland"]),
    "ET": ("Ethiopia", ["ethiopia", "ethiopian", "addis ababa", "tigray", "amhara"]),
    "FJ": ("Fiji", ["fiji", "fijian"]),
    "FI": ("Finland", ["finland", "finnish", "helsinki"]),
    "FR": ("France", ["france", "french", "paris", "elysee"]),
    "GA": ("Gabon", ["gabon", "gabonese"]),
    "GM": ("Gambia", ["gambia", "gambian"]),
    "GE": ("Georgia", ["georgia", "georgian", "tbilisi"]),
    "DE": ("Germany", ["germany", "german", "berlin", "bundeswehr"]),
    "GH": ("Ghana", ["ghana", "ghanaian", "accra"]),
    "GR": ("Greece", ["greece", "greek", "athens"]),
    "GD": ("Grenada", ["grenada"]),
    "GT": ("Guatemala", ["guatemala", "guatemalan"]),
    "GN": ("Guinea", ["guinea", "guinean", "conakry"]),
    "GW": ("Guinea-Bissau", ["guinea bissau", "bissau"]),
    "GY": ("Guyana", ["guyana", "guyanese", "georgetown"]),
    "HT": ("Haiti", ["haiti", "haitian", "port au prince"]),
    "HN": ("Honduras", ["honduras", "honduran", "tegucigalpa"]),
    "HU": ("Hungary", ["hungary", "hungarian", "budapest"]),
    "IS": ("Iceland", ["iceland", "icelandic", "reykjavik"]),
    "IN": ("India", ["india", "indian", "new delhi", "delhi", "mumbai"]),
    "ID": ("Indonesia", ["indonesia", "indonesian", "jakarta"]),
    "IR": ("Iran", ["iran", "iranian", "tehran", "irgc"]),
    "IQ": ("Iraq", ["iraq", "iraqi", "baghdad", "erbil", "mosul"]),
    "IE": ("Ireland", ["ireland", "irish", "dublin"]),
    "IL": ("Israel", ["israel", "israeli", "jerusalem", "tel aviv", "idf", "knesset"]),
    "IT": ("Italy", ["italy", "italian", "rome"]),
    "JM": ("Jamaica", ["jamaica", "jamaican", "kingston"]),
    "JP": ("Japan", ["japan", "japanese", "tokyo", "okinawa"]),
    "JO": ("Jordan", ["jordan", "jordanian", "amman"]),
    "KZ": ("Kazakhstan", ["kazakhstan", "kazakh", "astana", "almaty"]),
    "KE": ("Kenya", ["kenya", "kenyan", "nairobi"]),
    "KI": ("Kiribati", ["kiribati"]),
    "KP": ("North Korea", ["north korea", "north korean", "dprk", "pyongyang"]),
    "KR": ("South Korea", ["south korea", "south korean", "seoul", "rok"]),
    "XK": ("Kosovo", ["kosovo", "kosovar", "pristina"]),
    "KW": ("Kuwait", ["kuwait", "kuwaiti"]),
    "KG": ("Kyrgyzstan", ["kyrgyzstan", "kyrgyz", "bishkek"]),
    "LA": ("Laos", ["laos", "laotian", "vientiane"]),
    "LV": ("Latvia", ["latvia", "latvian", "riga"]),
    "LB": ("Lebanon", ["lebanon", "lebanese", "beirut", "hezbollah"]),
    "LS": ("Lesotho", ["lesotho"]),
    "LR": ("Liberia", ["liberia", "liberian", "monrovia"]),
    "LY": ("Libya", ["libya", "libyan", "tripoli", "benghazi"]),
    "LI": ("Liechtenstein", ["liechtenstein"]),
    "LT": ("Lithuania", ["lithuania", "lithuanian", "vilnius"]),
    "LU": ("Luxembourg", ["luxembourg"]),
    "MG": ("Madagascar", ["madagascar", "malagasy", "antananarivo"]),
    "MW": ("Malawi", ["malawi", "malawian", "lilongwe"]),
    "MY": ("Malaysia", ["malaysia", "malaysian", "kuala lumpur"]),
    "MV": ("Maldives", ["maldives", "maldivian"]),
    "ML": ("Mali", ["mali", "malian", "bamako"]),
    "MT": ("Malta", ["malta", "maltese"]),
    "MH": ("Marshall Islands", ["marshall islands"]),
    "MR": ("Mauritania", ["mauritania", "mauritanian", "nouakchott"]),
    "MU": ("Mauritius", ["mauritius", "mauritian"]),
    "MX": ("Mexico", ["mexico", "mexican", "mexico city", "sinaloa", "tijuana", "jalisco"]),
    "FM": ("Micronesia", ["micronesia"]),
    "MD": ("Moldova", ["moldova", "moldovan", "chisinau", "transnistria"]),
    "MC": ("Monaco", ["monaco"]),
    "MN": ("Mongolia", ["mongolia", "mongolian", "ulaanbaatar"]),
    "ME": ("Montenegro", ["montenegro", "montenegrin", "podgorica"]),
    "MA": ("Morocco", ["morocco", "moroccan", "rabat"]),
    "MZ": ("Mozambique", ["mozambique", "mozambican", "maputo", "cabo delgado"]),
    "MM": ("Myanmar", ["myanmar", "burma", "burmese", "yangon", "naypyidaw", "rakhine"]),
    "NA": ("Namibia", ["namibia", "namibian", "windhoek"]),
    "NR": ("Nauru", ["nauru"]),
    "NP": ("Nepal", ["nepal", "nepali", "nepalese", "kathmandu"]),
    "NL": ("Netherlands", ["netherlands", "dutch", "holland", "amsterdam"]),
    "NZ": ("New Zealand", ["new zealand", "wellington", "auckland"]),
    "NI": ("Nicaragua", ["nicaragua", "nicaraguan", "managua"]),
    "NE": ("Niger", ["niger", "nigerien", "niamey"]),
    "NG": ("Nigeria", ["nigeria", "nigerian", "abuja", "lagos"]),
    "MK": ("North Macedonia", ["north macedonia", "macedonia", "macedonian", "skopje"]),
    "NO": ("Norway", ["norway", "norwegian", "oslo"]),
    "OM": ("Oman", ["oman", "omani", "muscat"]),
    "PK": ("Pakistan", ["pakistan", "pakistani", "islamabad", "karachi", "lahore", "balochistan"]),
    "PW": ("Palau", ["palau"]),
    "PS": ("Palestine", ["palestine", "palestinian", "gaza", "gazan", "west bank", "ramallah", "hamas"]),
    "PA": ("Panama", ["panama", "panamanian"]),
    "PG": ("Papua New Guinea", ["papua new guinea"]),
    "PY": ("Paraguay", ["paraguay", "paraguayan", "asuncion"]),
    "PE": ("Peru", ["peru", "peruvian"]),
    "PH": ("Philippines", ["philippines", "philippine", "filipino", "manila"]),
    "PL": ("Poland", ["poland", "polish", "warsaw"]),
    "PT": ("Portugal", ["portugal", "portuguese", "lisbon"]),
    "QA": ("Qatar", ["qatar", "qatari", "doha"]),
    "RO": ("Romania", ["romania", "romanian", "bucharest"]),
    "RU": ("Russia", ["russia", "russian", "moscow", "kremlin", "st petersburg", "saint petersburg"]),
    "RW": ("Rwanda", ["rwanda", "rwandan", "kigali"]),
    "KN": ("Saint Kitts and Nevis", ["saint kitts", "st kitts"]),
    "LC": ("Saint Lucia", ["saint lucia", "st lucia"]),
    "VC": ("Saint Vincent", ["saint vincent", "st vincent"]),
    "WS": ("Samoa", ["samoa", "samoan"]),
    "SM": ("San Marino", ["san marino"]),
    "ST": ("Sao Tome and Principe", ["sao tome"]),
    "SA": ("Saudi Arabia", ["saudi arabia", "saudi", "riyadh", "jeddah"]),
    "SN": ("Senegal", ["senegal", "senegalese", "dakar"]),
    "RS": ("Serbia", ["serbia", "serbian", "belgrade"]),
    "SC": ("Seychelles", ["seychelles"]),
    "SL": ("Sierra Leone", ["sierra leone", "sierra leonean", "freetown"]),
    "SG": ("Singapore", ["singapore", "singaporean"]),
    "SK": ("Slovakia", ["slovakia", "slovak", "bratislava"]),
    "SI": ("Slovenia", ["slovenia", "slovenian", "ljubljana"]),
    "SB": ("Solomon Islands", ["solomon islands"]),
    "SO": ("Somalia", ["somalia", "somali", "mogadishu", "somaliland", "al shabaab", "puntland"]),
    "ZA": ("South Africa", ["south africa", "south african", "pretoria", "johannesburg", "cape town"]),
    "SS": ("South Sudan", ["south sudan", "south sudanese", "juba"]),
    "ES": ("Spain", ["spain", "spanish", "madrid", "barcelona", "catalonia"]),
    "LK": ("Sri Lanka", ["sri lanka", "sri lankan", "colombo"]),
    "SD": ("Sudan", ["sudan", "sudanese", "khartoum", "darfur", "el fasher", "port sudan"]),
    "SR": ("Suriname", ["suriname"]),
    "SE": ("Sweden", ["sweden", "swedish", "stockholm", "swede"]),
    "CH": ("Switzerland", ["switzerland", "swiss", "bern"]),
    "SY": ("Syria", ["syria", "syrian", "damascus", "aleppo", "idlib"]),
    "TW": ("Taiwan", ["taiwan", "taiwanese", "taipei", "kaohsiung"]),
    "TJ": ("Tajikistan", ["tajikistan", "tajik", "dushanbe"]),
    "TZ": ("Tanzania", ["tanzania", "tanzanian", "dodoma", "dar es salaam", "zanzibar"]),
    "TH": ("Thailand", ["thailand", "thai", "bangkok"]),
    "TL": ("Timor-Leste", ["timor leste", "east timor"]),
    "TG": ("Togo", ["togo", "togolese", "lome"]),
    "TO": ("Tonga", ["tonga", "tongan"]),
    "TT": ("Trinidad and Tobago", ["trinidad"]),
    "TN": ("Tunisia", ["tunisia", "tunisian", "tunis"]),
    "TR": ("Turkey", ["turkey", "turkiye", "turkish", "ankara", "istanbul"]),
    "TM": ("Turkmenistan", ["turkmenistan", "turkmen", "ashgabat"]),
    "TV": ("Tuvalu", ["tuvalu"]),
    "UG": ("Uganda", ["uganda", "ugandan", "kampala"]),
    "UA": ("Ukraine", ["ukraine", "ukrainian", "kyiv", "kiev", "kharkiv", "odesa", "odessa", "zaporizhzhia", "kherson",
                       "dnipro", "donbas", "donetsk", "luhansk", "crimea", "crimean", "lviv", "sumy", "poltava", "mykolaiv",
                       "chernihiv", "pokrovsk"]),
    "AE": ("United Arab Emirates", ["united arab emirates", "uae", "emirati", "emirates", "abu dhabi", "dubai"]),
    "GB": ("United Kingdom", ["united kingdom", "britain", "great britain", "british", "uk", "england", "english channel",
                              "scotland", "scottish", "wales", "welsh", "northern ireland", "london", "downing street"]),
    "US": ("United States", ["united states", "unitedstates", "american", "washington", "pentagon", "white house",
                             "usa", "uss"]),
    "UY": ("Uruguay", ["uruguay", "uruguayan", "montevideo"]),
    "UZ": ("Uzbekistan", ["uzbekistan", "uzbek", "tashkent"]),
    "VU": ("Vanuatu", ["vanuatu"]),
    "VA": ("Vatican", ["vatican", "holy see"]),
    "VE": ("Venezuela", ["venezuela", "venezuelan", "caracas"]),
    "VN": ("Vietnam", ["vietnam", "vietnamese", "hanoi", "ho chi minh city"]),
    "YE": ("Yemen", ["yemen", "yemeni", "sanaa", "aden", "houthi", "houthis"]),
    "ZM": ("Zambia", ["zambia", "zambian", "lusaka"]),
    "ZW": ("Zimbabwe", ["zimbabwe", "zimbabwean", "harare"]),
    # territories that news treats separately
    "HK": ("Hong Kong", ["hong kong"]),
    "GL": ("Greenland", ["greenland", "greenlandic", "nuuk"]),
    "PR": ("Puerto Rico", ["puerto rico", "puerto rican"]),
    "EH": ("Western Sahara", ["western sahara", "sahrawi", "polisario"]),
}

# Phrases that contain a country word but name a sea, region or something else: consumed, count as nothing.
NOTHING = [
    "south china sea", "east china sea", "sea of japan", "indian ocean", "native american", "american indian",
    "gulf of mexico", "gulf of america", "new mexico", "latin america", "latin american", "south america",
    "south american", "central america", "central american", "north america", "north american", "washington post",
    "new jersey", "new guinea", "persian gulf", "gulf of aden", "red sea", "arabian sea", "west indies",
    "jordan river", "american samoa", "english language", "french fries", "turkey day", "chinese new year",
    "american express", "american airlines", "air india", "turkish airlines", "qatar airways", "emirates airline",
    "korean air", "united states of america",  # last one is re-mapped below
    "russian roulette", "spanish flu", "rome statute", "paris agreement", "paris climate",
    "brussels", "geneva", "the hague", "kosovo force",
]
REMAP_NOTHING = {"united states of america": "US", "kosovo force": "XK"}

# A headline mentioning Georgia with any of these is about the US state, not the country.
US_STATE_SIGNS = re.compile(r"\b(atlanta|savannah|county|governor|gov|six flags|bulldogs|braves|falcons|kemp|ossoff|warnock|"
                            r"unitedstates|us|u s|american|state senate|primary|sheriff|georgia tech)\b")

def _alias_table():
    table = {}
    for code, (_, aliases) in COUNTRIES.items():
        for a in aliases:
            table[a] = code
            if " " not in a and not a.endswith("s") and a not in ("uss", "usa", "uae", "drc", "prc", "rok", "dprk", "idf", "irgc"):
                table[a + "s"] = code       # Russians, Israelis, Afghans
    for p in NOTHING:
        table[p] = REMAP_NOTHING.get(p)
    return table


ALIASES = _alias_table()
_RE = re.compile(r"\b(" + "|".join(re.escape(a) for a in sorted(ALIASES, key=len, reverse=True)) + r")\b")
NAMES = {code: name for code, (name, _) in COUNTRIES.items()}


def normalize(text: str, slug: bool = False) -> str:
    """Lower case ASCII words separated by single spaces. Upper-case US/U.S./UK in real titles become words first."""
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    if not slug:
        text = re.sub(r"\bU\.\s?S\.(?=\W|$)|\bU\.S\b|\bUS\b", " unitedstates ", text)
        text = re.sub(r"\bU\.\s?K\.(?=\W|$)|\bUK\b", " united kingdom ", text)
    text = re.sub(r"[^A-Za-z0-9]+", " ", text).lower().strip()
    return text


def tag(text: str, slug: bool = False) -> set[str]:
    """Country codes a headline (or URL slug, with slug=True) mentions."""
    t = normalize(text, slug)
    if slug:
        t = re.sub(r"\bus\b", "unitedstates", t)
        t = re.sub(r"\bu s\b", "unitedstates", t)
    else:
        t = re.sub(r"\bus\b", " ", t)          # lower-case 'us' in a real title is the pronoun
    found = set()
    for m in _RE.finditer(t):
        code = ALIASES[m.group(1)]
        if code:
            found.add(code)
    if "GE" in found and re.search(r"\bgeorgia\b", t) and not re.search(r"\b(georgian|tbilisi)\b", t) and US_STATE_SIGNS.search(t):
        found.discard("GE")
    return found


def slug_text(url: str) -> str:
    """The headline words in a news URL's last path segment, without ids or extensions."""
    seg = url.split("?")[0].rstrip("/").rsplit("/", 1)[-1]
    seg = re.sub(r"\.(html?|php|aspx)$", "", seg)
    seg = re.sub(r"^\d+-", "", seg)                # ukrinform: 4171022-drone-strike-...
    return seg.replace("-", " ").replace("_", " ")


if __name__ == "__main__":
    import sys
    for line in sys.argv[1:] or ["Russian drones hit Kharkiv as Kyiv seeks more U.S. air defence",
                                  "South Sudan and Sudan trade accusations", "Papua New Guinea quake",
                                  "One killed after roller coaster incident in Georgia, US", "Georgia's ruling party bans opposition",
                                  "Houthis claim strike on Saudi airport", "Chinese ships in the South China Sea",
                                  "Let us talk about it", "USS Klakring sunk in SINKEX"]:
        print(sorted(tag(line)), "|", line)
    print(sorted(tag(slug_text("https://www.aljazeera.com/news/2026/10/13/one-dead-after-roller-coaster-incident-in-george-us"), slug=True)))
