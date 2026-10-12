"""kit.scholar: find and read the research literature, with real metadata.

    from kit import scholar
    hits = scholar.find("physarum transport network", n=8)      # Crossref + arXiv + Europe PMC, merged
    scholar.show(hits)                                           # compact table
    p = scholar.doi("10.1126/science.1177894")                   # one paper: authors, venue, citations, abstract
    scholar.crossref("...", n=10, since="2023", kind="journal-article")
    scholar.arxiv("all:diffusion AND cat:cs.LG", n=10, sort="submittedDate")
    scholar.europepmc("GLP-1 AND cardiovascular", n=10, oa_only=True)   # biomed, abstracts, OA full text links
    scholar.pubmed("semaglutide[ti] AND randomized controlled trial[pt]", n=10)
    scholar.cited_by("10.1126/science.1177894")                  # DOIs citing it (OpenCitations)

Every function returns a list of Paper. Citation counts are from the named source and differ
between sources; say which one when quoting a count. OpenAlex and Semantic Scholar need keys or
hit shared-IP limits from here (2026-10-12), so they are not used by default.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field

from . import http


@dataclass
class Paper:
    source: str
    title: str
    authors: list[str] = field(default_factory=list)
    year: int | None = None
    venue: str = ""
    doi: str = ""
    cited_by: int | None = None
    abstract: str = ""
    url: str = ""
    pdf: str = ""
    kind: str = ""
    extra: dict = field(default_factory=dict)

    @property
    def byline(self) -> str:
        a = self.authors
        names = ", ".join(a[:3]) + (" et al." if len(a) > 3 else "")
        return f"{names} ({self.year or 'n.d.'})"

    def cite(self) -> str:
        """One-line citation with a link."""
        link = f"https://doi.org/{self.doi}" if self.doi else self.url
        venue = f" {self.venue}." if self.venue else ""
        return f"{self.byline}. {self.title}.{venue} {link}".strip()

    def dict(self) -> dict:
        return asdict(self)


def _clean(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s or "")
    return re.sub(r"\s+", " ", s).strip()


# ---------- Crossref: everything with a DOI ----------
def _cr_item(it: dict) -> Paper:
    year = None
    for k in ("published", "issued", "published-print", "published-online", "created"):
        dp = (it.get(k) or {}).get("date-parts")
        if dp and dp[0] and dp[0][0]:
            year = int(dp[0][0])
            break
    authors = [" ".join(x for x in (a.get("given"), a.get("family")) if x) or a.get("name", "")
               for a in it.get("author", [])]
    pdf = next((l["URL"] for l in it.get("link", []) if "pdf" in l.get("content-type", "")), "")
    return Paper("crossref", _clean((it.get("title") or [""])[0]), authors, year,
                 _clean((it.get("container-title") or [""])[0]), it.get("DOI", "").lower(),
                 it.get("is-referenced-by-count"), _clean(it.get("abstract", "")),
                 it.get("URL", ""), pdf, it.get("type", ""))


def crossref(query: str, n: int = 10, since: str | None = None, until: str | None = None,
             kind: str | None = None, sort: str = "relevance") -> list[Paper]:
    """Search Crossref. since/until 'YYYY[-MM[-DD]]'; kind e.g. 'journal-article'; sort relevance|published|is-referenced-by-count."""
    filt = []
    if since:
        filt.append(f"from-pub-date:{since}")
    if until:
        filt.append(f"until-pub-date:{until}")
    if kind:
        filt.append(f"type:{kind}")
    params = {"query.bibliographic": query, "rows": n, "sort": sort, "order": "desc"}
    if filt:
        params["filter"] = ",".join(filt)
    j = http.get_json("https://api.crossref.org/works", params)
    return [_cr_item(it) for it in j["message"]["items"]]


def doi(d: str, abstract: bool = True) -> Paper:
    """One paper by DOI from Crossref; fills the abstract from Europe PMC when Crossref lacks it."""
    d = re.sub(r"^(https?://(dx\.)?doi\.org/|doi:)", "", d.strip(), flags=re.I)
    p = _cr_item(http.get_json(f"https://api.crossref.org/works/{d}")["message"])
    if abstract and not p.abstract:
        try:
            hits = europepmc(f'DOI:"{d}"', n=1)
            if hits and hits[0].abstract:
                p.abstract = hits[0].abstract
                p.extra["abstract_from"] = "europepmc"
        except Exception:
            pass
    return p


# ---------- arXiv: preprints in physics, CS, maths, stats, q-bio, econ ----------
_A = {"a": "http://www.w3.org/2005/Atom", "x": "http://arxiv.org/schemas/atom"}


def arxiv(query: str, n: int = 10, sort: str = "relevance") -> list[Paper]:
    """arXiv API query syntax: 'all:term', 'ti:...', 'au:...', 'cat:cs.LG', AND/OR. sort relevance|submittedDate|lastUpdatedDate."""
    if ":" not in query:  # plain words: AND them together, minus stopwords (arXiv returns nothing for 'all:of')
        stop = {"a", "an", "and", "the", "of", "in", "on", "for", "to", "with", "by", "is", "are", "from", "at", "as", "or"}
        words = [w for w in re.findall(r"[\w-]+", query) if w.lower() not in stop]
        query = " AND ".join(f"all:{w}" for w in words)
    r = http.get("https://export.arxiv.org/api/query",
                 {"search_query": query, "max_results": n, "sortBy": sort, "sortOrder": "descending"})
    root = ET.fromstring(r.content)
    out = []
    for e in root.findall("a:entry", _A):
        link = e.findtext("a:id", "", _A)
        pdf = next((l.get("href") for l in e.findall("a:link", _A) if l.get("title") == "pdf"), "")
        cat = e.find("x:primary_category", _A)
        out.append(Paper("arxiv", _clean(e.findtext("a:title", "", _A)),
                         [a.findtext("a:name", "", _A) for a in e.findall("a:author", _A)],
                         int(e.findtext("a:published", "0000", _A)[:4]) or None,
                         "arXiv" + (f" [{cat.get('term')}]" if cat is not None else ""),
                         (e.findtext("x:doi", "", _A) or "").lower(), None,
                         _clean(e.findtext("a:summary", "", _A)), link, pdf, "preprint",
                         {"updated": e.findtext("a:updated", "", _A)[:10]}))
    return out


# ---------- Europe PMC: biomedicine and life sciences, abstracts and OA full text ----------
def europepmc(query: str, n: int = 10, oa_only: bool = False, sort: str = "") -> list[Paper]:
    """Europe PMC search syntax (TITLE:, AUTH:, PUB_YEAR:[2020 TO 2026], OPEN_ACCESS:y). sort e.g. 'CITED desc'."""
    q = f"({query}) AND OPEN_ACCESS:y" if oa_only else query
    params = {"query": q, "format": "json", "pageSize": n, "resultType": "core"}
    if sort:
        params["sort"] = sort
    j = http.get_json("https://www.ebi.ac.uk/europepmc/webservices/rest/search", params)
    out = []
    for it in j.get("resultList", {}).get("result", []):
        urls = (it.get("fullTextUrlList") or {}).get("fullTextUrl", [])
        pdf = next((u["url"] for u in urls if u.get("documentStyle") == "pdf" and u.get("availabilityCode") in ("OA", "F")), "")
        page = next((u["url"] for u in urls if u.get("documentStyle") == "html"), "")
        src_url = f"https://europepmc.org/article/{it.get('source')}/{it.get('id')}"
        authors = [a.get("fullName", "") for a in (it.get("authorList") or {}).get("author", [])] \
            or [s.strip() for s in it.get("authorString", "").split(",") if s.strip()]
        venue = ((it.get("journalInfo") or {}).get("journal") or {}).get("title", "") or it.get("bookOrReportDetails", {}).get("publisher", "")
        out.append(Paper("europepmc", _clean(it.get("title", "")), authors,
                         int(it["pubYear"]) if str(it.get("pubYear", "")).isdigit() else None,
                         venue, (it.get("doi") or "").lower(), it.get("citedByCount"),
                         _clean(it.get("abstractText", "")), page or src_url, pdf,
                         ", ".join((it.get("pubTypeList") or {}).get("pubType", [])[:2]),
                         {"pmid": it.get("pmid"), "pmcid": it.get("pmcid"), "oa": it.get("isOpenAccess") == "Y"}))
    return out


# ---------- PubMed: NCBI's own ranking and MeSH-aware queries ----------
def pubmed(query: str, n: int = 10, sort: str = "relevance") -> list[Paper]:
    """PubMed query syntax ([ti], [au], [pt], [mh], dates 2020:2026[dp]). sort relevance|pub_date."""
    base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
    ids = http.get_json(base + "esearch.fcgi", {"db": "pubmed", "term": query, "retmode": "json",
                                                 "retmax": n, "sort": sort, "tool": "ClaudeResearchKit"}
                        )["esearchresult"]["idlist"]
    if not ids:
        return []
    r = http.get(base + "efetch.fcgi", {"db": "pubmed", "id": ",".join(ids), "retmode": "xml",
                                        "tool": "ClaudeResearchKit"})
    root = ET.fromstring(r.content)
    out = []
    for art in root.findall(".//PubmedArticle"):
        a = art.find("MedlineCitation/Article")
        pmid = art.findtext("MedlineCitation/PMID", "")
        abst = " ".join(((x.get("Label") + ": ") if x.get("Label") else "") + "".join(x.itertext())
                        for x in a.findall("Abstract/AbstractText"))
        authors = [" ".join(filter(None, (au.findtext("ForeName"), au.findtext("LastName")))) or au.findtext("CollectiveName", "")
                   for au in a.findall("AuthorList/Author")]
        year = a.findtext("Journal/JournalIssue/PubDate/Year") or (a.findtext("Journal/JournalIssue/PubDate/MedlineDate") or "")[:4]
        d = next((x.text for x in art.findall("PubmedData/ArticleIdList/ArticleId") if x.get("IdType") == "doi"), "")
        types = [t.text for t in a.findall("PublicationTypeList/PublicationType")]
        out.append(Paper("pubmed", _clean("".join(a.find("ArticleTitle").itertext()) if a.find("ArticleTitle") is not None else ""),
                         authors, int(year) if str(year).isdigit() else None, a.findtext("Journal/Title", ""),
                         (d or "").lower(), None, _clean(abst), f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/", "",
                         ", ".join(types[:2]), {"pmid": pmid}))
    return out


# ---------- OpenAlex (keyless budget is shared; may be exhausted) ----------
def openalex(query: str, n: int = 10) -> list[Paper]:
    j = http.get_json("https://api.openalex.org/works", {"search": query, "per-page": n})
    out = []
    for w in j.get("results", []):
        inv = w.get("abstract_inverted_index") or {}
        words = sorted(((i, wd) for wd, ix in inv.items() for i in ix))
        loc = w.get("primary_location") or {}
        out.append(Paper("openalex", _clean(w.get("title") or ""),
                         [a["author"]["display_name"] for a in w.get("authorships", [])],
                         w.get("publication_year"), ((loc.get("source") or {}).get("display_name") or ""),
                         (w.get("doi") or "").replace("https://doi.org/", "").lower(), w.get("cited_by_count"),
                         " ".join(wd for _, wd in words), w.get("id", ""),
                         (w.get("best_oa_location") or {}).get("pdf_url") or "", w.get("type", "")))
    return out


# ---------- citations ----------
def cited_by(d: str, limit: int = 200) -> list[str]:
    """DOIs of works citing this DOI (OpenCitations COCI; coverage is partial, newest lags)."""
    d = re.sub(r"^(https?://(dx\.)?doi\.org/)", "", d.strip(), flags=re.I)
    j = http.get_json(f"https://api.opencitations.net/index/v2/citations/doi:{d}")
    out = []
    for row in j[:limit]:
        m = re.search(r"doi:(\S+)", row.get("citing", ""))
        if m:
            out.append(m.group(1).lower())
    return out


def landmarks(query: str, n: int = 10, window: int = 80, since: str | None = None,
              biomed: bool = False) -> list[Paper]:
    """The most-cited papers on a topic: the ones a field actually builds on. Plain relevance
    search surfaces obscure zero-citation work first; use this to orient, then `find` or
    `arxiv(..., sort='submittedDate')` for the newest work.

    biomed=True adds Europe PMC sorted by citations with every word required in the title or
    abstract (tested: returns the landmark trials and reviews). Weak spot: machine learning and
    much of CS, whose key papers often lack DOIs (arXiv, ICLR, JMLR) and so are invisible to
    Crossref's counts. There, name the landmarks with WebSearch, then read them with arxiv()."""
    pool = crossref(query, n=window, since=since, kind="journal-article") + \
        crossref(query, n=window // 2, since=since, kind="proceedings-article")
    if biomed:
        q = query if ":" in query else " AND ".join(f'TITLE_ABS:"{w}"' for w in re.findall(r"[\w-]+", query)
                                                   if len(w) > 2 and w.lower() not in {"and", "the", "for", "with"})
        if since:
            q += f" AND PUB_YEAR:[{since[:4]} TO 2100]"
        pool += europepmc(q, n=max(10, window // 2), sort="CITED desc")
    best: dict[str, Paper] = {}
    for p in pool:
        k = p.doi or _norm(p.title)
        if k and (k not in best or (p.cited_by or 0) > (best[k].cited_by or 0)):
            best[k] = p
    return sorted(best.values(), key=lambda p: p.cited_by or 0, reverse=True)[:n]


# ---------- merged search ----------
def _norm(t: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", t.lower())[:80]


def find(query: str, n: int = 10, sources=("crossref", "europepmc", "arxiv")) -> list[Paper]:
    """Run the same plain-language query on several sources; interleave and drop duplicates.
    Failures in one source are reported in the result's first item's extra['errors'] and skipped."""
    fns = {"crossref": crossref, "europepmc": europepmc, "arxiv": arxiv, "pubmed": pubmed, "openalex": openalex}
    lists, errors = [], {}
    for s in sources:
        try:
            lists.append(fns[s](query, n=n))
        except Exception as e:  # keep going; report which source failed
            errors[s] = f"{type(e).__name__}: {str(e)[:120]}"
    seen, out = set(), []
    for i in range(max((len(l) for l in lists), default=0)):
        for l in lists:
            if i < len(l):
                p = l[i]
                k = p.doi or _norm(p.title)
                if k and k not in seen:
                    seen.add(k)
                    out.append(p)
    if errors and out:
        out[0].extra["errors"] = errors
    elif errors:
        raise RuntimeError(f"every source failed: {errors}")
    return out


def show(papers: list[Paper], abstract: int = 0) -> None:
    """Print a compact list; abstract=N prints the first N characters of each abstract."""
    for i, p in enumerate(papers, 1):
        cites = f" · {p.cited_by} cites ({p.source})" if p.cited_by is not None else f" · {p.source}"
        print(f"{i:>2}. {p.title[:110]}\n    {p.byline} · {p.venue[:60]}{cites}\n    {('https://doi.org/' + p.doi) if p.doi else p.url}")
        if abstract and p.abstract:
            print("    " + p.abstract[:abstract] + ("…" if len(p.abstract) > abstract else ""))
    if papers and papers[0].extra.get("errors"):
        print("  (sources that failed:", papers[0].extra["errors"], ")")
