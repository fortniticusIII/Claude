"""kit.qa: check a page the way viewers will see it, before publishing.

    python3 -m kit.qa page.html [--mock mock.json] [--out qa_out] [--strict]
    from kit import qa; report = qa.check("page.html", mock="mock.json")

Renders the page in Chromium at phone (390) and desktop (1280) widths, light and dark, and reports:
  FAIL  script errors, failed requests, horizontal overflow (with the elements that cause it),
        broken images, artifact-contract breaks (scripts or styles from hosts the artifact
        host won't load, page over 16 MB)
  WARN  text below WCAG contrast (4.5:1, or 3:1 for large text), a dark theme that never
        changes the page, tap targets under 32 px on phone, text under 11 px, a title that
        isn't 2-4 words, localStorage without try/catch
It saves a full-page screenshot per view (Read them to look) and numbers.txt: every figure on
the page with its context, to check each one against the source before publishing.

--mock takes {collection: [{"id": ..., "data": {...}}]} (e.g. from ArtifactData list with out_dir,
converted by qa.mock_from_dump(folder)), and serves it through a stub of claude.use('db').
Other capabilities resolve null, as they would for a viewer who can't run them.
Needs Playwright's Chromium (this sandbox: /opt/pw-browsers).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

SKELETON = ('<!doctype html><html><head><meta charset=utf8><meta name=viewport content="width=device-width,'
            'initial-scale=1,viewport-fit=cover"><style>:root{color-scheme:light;box-sizing:border-box}body{margin:0;'
            'padding:0;font:14px -apple-system,BlinkMacSystemFont,sans-serif;background:#fff;color:#000}img{max-width:100%}'
            '[hidden]:not([hidden=until-found i]){display:none!important}</style></head><body>')
SCRIPT_HOSTS = {"cdnjs.cloudflare.com", "cdn.jsdelivr.net", "unpkg.com", "cdn.tailwindcss.com", "code.jquery.com"}
STYLE_HOSTS = {"fonts.googleapis.com"}
VIEWS = [("phone-light", 390, "light"), ("phone-dark", 390, "dark"),
         ("desktop-light", 1280, "light"), ("desktop-dark", 1280, "dark")]

DB_STUB = r"""<script>
window.__DATA__ = %s;
(function(){
  const cmp = (a, op, v) => ({'==':a===v,'eq':a===v,'!=':a!==v,'ne':a!==v,'<':a<v,'lt':a<v,'<=':a<=v,'lte':a<=v,
    '>':a>v,'gt':a>v,'>=':a>=v,'gte':a>=v,'in':(v||[]).includes(a),'not-in':!(v||[]).includes(a),
    'array-contains':Array.isArray(a)&&a.includes(v)})[op];
  function query(name){ let ord=null, wh=[], lim=1e9;
    const run = () => { let docs=(window.__DATA__[name]||[]).filter(x=>wh.every(([f,op,v])=>cmp(x.data[f],op,v)));
      if(ord) docs.sort((a,b)=>(a.data[ord[0]]>b.data[ord[0]]?1:a.data[ord[0]]<b.data[ord[0]]?-1:0)*(ord[1]==='desc'?-1:1));
      docs = docs.slice(0, lim).map(x=>({id:x.id, exists:true, data:()=>x.data}));
      return {docs, size:docs.length, empty:!docs.length, forEach:f=>docs.forEach(f)}; };
    const q = { orderBy(f,d){ord=[f,d||'asc'];return q;}, limit(n){lim=n;return q;}, where(f,op,v){wh.push([f,op,v]);return q;},
      get: async()=>run(), onSnapshot(cb){ setTimeout(()=>cb(run()),20); return ()=>{}; },
      doc: id => doc(name+'/'+id), add: async()=>({id:'new'}) };
    return q; }
  function doc(path){ const p=path.split('/'), id=p.pop(), c=p.join('/');
    const snap=()=>{ const x=(window.__DATA__[c]||[]).find(d=>d.id===id); return {id, exists:!!x, data:()=>x&&x.data}; };
    return { get: async()=>snap(), onSnapshot(cb){ setTimeout(()=>cb(snap()),20); return ()=>{}; },
      set: async()=>{}, update: async()=>{}, delete: async()=>{}, collection: n=>query(path+'/'+n) }; }
  const db = { collection: query, doc };
  window.claude = { use: async n => (n === 'db' && window.__DATA__ !== null) ? db : null };
})();
</script>"""

PROBE_JS = r"""() => {
  const W = innerWidth, out = {};
  out.scrollWidth = document.documentElement.scrollWidth;
  const path = el => { const p=[]; for (let e=el; e && e!==document.body && p.length<4; e=e.parentElement)
      p.unshift(e.tagName.toLowerCase() + (e.id?'#'+e.id:'') + (e.classList.length?'.'+[...e.classList].slice(0,2).join('.'):''));
    return p.join(' > '); };
  const visible = el => { const r=el.getBoundingClientRect(); const s=getComputedStyle(el);
    return r.width>0 && r.height>0 && s.visibility!=='hidden' && s.display!=='none' && +s.opacity>0.05; };
  const all = [...document.body.querySelectorAll('*')];
  // overflow offenders: deepest elements sticking out past the right edge
  const wide = all.filter(el => visible(el) && el.getBoundingClientRect().right > W + 1);
  out.overflow = wide.filter(el => !wide.some(o => o!==el && el.contains(o))).slice(0,6)
    .map(el => ({el: path(el), right: Math.round(el.getBoundingClientRect().right)}));
  // colours and contrast
  const parse = c => { const m=c.match(/[\d.]+/g); if(!m) return null; return {r:+m[0],g:+m[1],b:+m[2],a:m[3]===undefined?1:+m[3]}; };
  const lum = c => { const f=v=>{v/=255;return v<=0.03928?v/12.92:Math.pow((v+0.055)/1.055,2.4)}; return 0.2126*f(c.r)+0.7152*f(c.g)+0.0722*f(c.b); };
  const blend = (top, bot) => ({r: top.r*top.a+bot.r*(1-top.a), g: top.g*top.a+bot.g*(1-top.a), b: top.b*top.a+bot.b*(1-top.a), a:1});
  const base = matchMedia('(prefers-color-scheme: dark)').matches ? {r:0,g:0,b:0,a:1} : {r:255,g:255,b:255,a:1};
  const bgOf = el => { const layers=[]; let img=false;
    for (let e=el; e; e=e.parentElement) { const s=getComputedStyle(e); if (s.backgroundImage!=='none') img=true;
      const c=parse(s.backgroundColor); if (c && c.a>0) { layers.push(c); if (c.a>=1) break; } }
    let bg = base; for (const l of layers.reverse()) bg = blend(l, bg); return {bg, img}; };
  const low = [], tiny = [];
  const textEls = all.filter(el => visible(el) && [...el.childNodes].some(n => n.nodeType===3 && n.textContent.trim().length>1)).slice(0, 600);
  for (const el of textEls) {
    const s = getComputedStyle(el), bold = +s.fontWeight >= 700;
    // SVG text inside a viewBox reports its size in user units; scale it to screen px.
    const ctm = el instanceof SVGGraphicsElement && el.getScreenCTM ? el.getScreenCTM() : null;
    const fs = parseFloat(s.fontSize) * (ctm ? Math.hypot(ctm.a, ctm.b) : 1);
    if (fs < 10.95) tiny.push({el: path(el), px: +fs.toFixed(1), text: el.textContent.trim().slice(0,40)});
    const {bg, img} = bgOf(el); if (img) continue;
    let fg = parse(s.color); if (!fg) continue; fg = blend(fg, bg);
    const L1=lum(fg), L2=lum(bg), ratio=(Math.max(L1,L2)+0.05)/(Math.min(L1,L2)+0.05);
    const need = (fs>=24 || (fs>=18.66 && bold)) ? 3 : 4.5;
    if (ratio < need) low.push({el: path(el), ratio: +ratio.toFixed(2), need, text: el.textContent.trim().slice(0,40)});
  }
  out.lowContrast = low.slice(0, 8); out.lowContrastCount = low.length;
  out.tinyText = tiny.slice(0, 5); out.tinyTextCount = tiny.length;
  // tap targets
  const targets = [...document.querySelectorAll('button, a[href], input, select, textarea, [role=button], [role=tab]')].filter(visible);
  const small = targets.filter(el => { if (el.type==='range' || el.type==='hidden') return false; const r=el.getBoundingClientRect();
    const inline = el.tagName==='A' && getComputedStyle(el).display==='inline' && el.parentElement && el.parentElement.textContent.trim().length > el.textContent.trim().length + 20;
    return !inline && (r.height < 32 || r.width < 32); });
  out.smallTargets = small.slice(0,5).map(el => ({el: path(el), w: Math.round(el.getBoundingClientRect().width), h: Math.round(el.getBoundingClientRect().height)}));
  out.smallTargetCount = small.length;
  out.brokenImages = [...document.images].filter(i => i.complete && i.naturalWidth===0).map(i => i.src.slice(0,120));
  out.bodyBg = getComputedStyle(document.body).backgroundColor;
  out.bodyFg = getComputedStyle(document.body).color;
  out.title = document.title;
  out.text = document.body.innerText;
  return out;
}"""


def mock_from_dump(folder: str | Path) -> dict:
    """Turn an ArtifactData `list ... out_dir=<folder>` dump into a --mock dict."""
    folder = Path(folder)
    out: dict[str, list] = {}
    for f in sorted(folder.rglob("*.json")):
        coll = str(f.parent.relative_to(folder)) if f.parent != folder else folder.name
        j = json.loads(f.read_text())
        out.setdefault(coll, []).append({"id": f.stem, "data": j.get("data", j) if isinstance(j, dict) else j})
    return out


def _static(html: str) -> list[tuple[str, str]]:
    issues = []
    for m in re.finditer(r"<script[^>]*\bsrc=[\"']([^\"']+)", html, re.I):
        h = urlsplit(m.group(1)).hostname
        if h and h not in SCRIPT_HOSTS:
            issues.append(("FAIL", f"script from {h} won't load in an artifact (allowed: {', '.join(sorted(SCRIPT_HOSTS))})"))
        if h == "cdn.jsdelivr.net" and "/npm/" not in m.group(1):
            issues.append(("WARN", f"jsdelivr script outside /npm/: {m.group(1)[:80]}"))
    for m in re.finditer(r"<link[^>]*rel=[\"']?stylesheet[^>]*>", html, re.I):
        href = re.search(r"href=[\"']([^\"']+)", m.group(0))
        h = urlsplit(href.group(1)).hostname if href else None
        if h and h not in STYLE_HOSTS:
            issues.append(("FAIL", f"stylesheet from {h} won't load in an artifact (only Google Fonts)"))
    for m in re.finditer(r"@import\s+url\([\"']?([^)\"']+)", html):
        h = urlsplit(m.group(1)).hostname
        if h and h not in STYLE_HOSTS:
            issues.append(("FAIL", f"@import from {h} won't load in an artifact"))
    size = len(html.encode())
    if size > 16 * 1024 * 1024:
        issues.append(("FAIL", f"page is {size / 1e6:.1f} MB; the limit is 16 MB including data: URIs"))
    t = re.search(r"<title>(.*?)</title>", html, re.I | re.S)
    if not t:
        issues.append(("WARN", "no <title>; the artifact card and tab need a 2-4 word name"))
    elif not 2 <= len(t.group(1).split()) <= 4:
        issues.append(("WARN", f"title '{t.group(1).strip()}' isn't 2-4 words"))
    if "prefers-color-scheme: dark" not in html and "prefers-color-scheme:dark" not in html:
        issues.append(("WARN", "no prefers-color-scheme: dark rule"))
    elif 'data-theme="dark"' not in html and "data-theme=dark" not in html:
        issues.append(("WARN", "dark theme lacks the :root[data-theme=\"dark\"] override the host toggles"))
    if "localStorage" in html and not re.search(r"try\s*{[^}]*localStorage", html):
        issues.append(("WARN", "localStorage used without try/catch; it throws in some views"))
    return issues


NUM_RE = re.compile(r"(?<![\w.:/–-])[-+−]?(?:\$|€|£)?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?![:\d])"
                    r"(?:\s?(?:%|percent|[kKmMbB]n?\b|million|billion|trillion|x\b|×))?")


def numbers(text: str, width: int = 50) -> list[str]:
    """Every figure in a text with context, skipping bare small integers like list numbers."""
    out, seen = [], set()
    for m in NUM_RE.finditer(text):
        tok = m.group(0).strip()
        digits = re.sub(r"\D", "", tok)
        if len(digits) <= 1 and not re.search(r"[%$€£.]|million|billion|trillion", tok):
            continue
        if len(digits) <= 2 and re.search(r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s$",
                                          text[max(0, m.start() - 10): m.start()]):
            continue  # day of month
        ctx = text[max(0, m.start() - width): m.end() + width].replace("\n", " ")
        key = (tok, ctx)
        if key not in seen:
            seen.add(key)
            out.append(f"{tok:>14}  …{ctx}…")
    return out


def check(page: str | Path, mock: str | Path | dict | None = None, out: str | Path = "qa_out",
          wait_ms: int = 900, views=VIEWS) -> dict:
    from playwright.sync_api import sync_playwright
    page = Path(page)
    html = page.read_text()
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    issues = _static(html)
    data = mock if isinstance(mock, dict) else (json.loads(Path(mock).read_text()) if mock else None)
    stub = DB_STUB % json.dumps(data)
    doc = html if html.lstrip().lower().startswith("<!doctype") else SKELETON + stub + html + "</body></html>"
    if doc is html:  # already a full document: put the stub first in <head>
        doc = re.sub(r"(<head[^>]*>)", r"\1" + stub.replace("\\", "\\\\"), html, count=1, flags=re.I)
    target = out / "_qa_page.html"
    target.write_text(doc)
    results = {}
    with sync_playwright() as p:
        b = p.chromium.launch()
        for name, w, scheme in views:
            pg = b.new_page(viewport={"width": w, "height": 900}, color_scheme=scheme)
            errs, failed = [], []
            pg.on("pageerror", lambda e, errs=errs: errs.append(f"pageerror: {e}"))
            pg.on("console", lambda m, errs=errs: errs.append(f"console: {m.text[:200]}")
                  if m.type == "error" and not m.text.startswith("Failed to load resource") else None)
            pg.on("requestfailed", lambda r, failed=failed: failed.append(f"{r.url[:120]} ({r.failure})"))
            pg.on("response", lambda r, failed=failed: failed.append(f"{r.url[:120]} (HTTP {r.status})") if r.status >= 400 else None)
            try:
                pg.goto(target.resolve().as_uri(), wait_until="networkidle", timeout=20000)
            except Exception:
                pass
            pg.wait_for_timeout(wait_ms)
            r = pg.evaluate(PROBE_JS)
            r["errors"], r["failed"] = errs, failed
            pg.screenshot(path=str(out / f"{name}.png"), full_page=True)
            results[name] = r
            pg.close()
        b.close()
    for name, w, scheme in views:
        r = results[name]
        for e in r["errors"][:5]:
            issues.append(("FAIL", f"[{name}] {e}"))
        for f in r["failed"][:5]:
            issues.append(("FAIL", f"[{name}] request failed: {f}"))
        if r["scrollWidth"] > w + 1:
            where = "; ".join(f"{o['el']} (right edge {o['right']}px)" for o in r["overflow"][:3])
            issues.append(("FAIL", f"[{name}] page scrolls sideways: {r['scrollWidth']}px wide. Culprits: {where}"))
        for i in r["brokenImages"][:3]:
            issues.append(("FAIL", f"[{name}] broken image {i}"))
        if r["lowContrastCount"]:
            ex = "; ".join(f"'{x['text']}' {x['ratio']}:1 (needs {x['need']})" for x in r["lowContrast"][:3])
            issues.append(("WARN", f"[{name}] {r['lowContrastCount']} text elements below contrast: {ex}"))
        if w < 600 and r["smallTargetCount"]:
            ex = "; ".join(f"{x['el']} {x['w']}x{x['h']}" for x in r["smallTargets"][:3])
            issues.append(("WARN", f"[{name}] {r['smallTargetCount']} tap targets under 32px: {ex}"))
        if r["tinyTextCount"] and scheme == "light":
            issues.append(("WARN", f"[{name}] {r['tinyTextCount']} text elements under 11px, e.g. '{r['tinyText'][0]['text']}'"))
    for w in sorted({v[1] for v in views}):
        light = next((results[n] for n, ww, s in views if ww == w and s == "light"), None)
        dark = next((results[n] for n, ww, s in views if ww == w and s == "dark"), None)
        if light and dark and light["bodyBg"] == dark["bodyBg"] and light["bodyFg"] == dark["bodyFg"]:
            issues.append(("WARN", f"[{w}px] dark mode looks identical to light (body {light['bodyBg']})"))
    # dedupe same message across views
    seen, uniq = set(), []
    for lvl, msg in issues:
        k = re.sub(r"^\[[\w-]+\] ", "", msg)
        if k not in seen:
            seen.add(k)
            uniq.append((lvl, msg))
    nums = numbers(results[views[-2][0] if len(views) > 2 else views[0][0]]["text"])
    (out / "numbers.txt").write_text("\n".join(nums))
    report = {"page": str(page), "issues": uniq, "fails": sum(l == "FAIL" for l, _ in uniq),
              "warns": sum(l == "WARN" for l, _ in uniq), "numbers": len(nums),
              "screenshots": [str(out / f"{n}.png") for n, _, _ in views], "out": str(out)}
    (out / "report.json").write_text(json.dumps(report, indent=1))
    return report


def print_report(rep: dict) -> None:
    print(f"QA {rep['page']}: {rep['fails']} fail, {rep['warns']} warn, {rep['numbers']} figures to verify")
    for lvl, msg in rep["issues"]:
        print(f"  {lvl}  {msg}")
    if not rep["issues"]:
        print("  PASS  no issues found")
    print(f"  screenshots + numbers.txt in {rep['out']}/ (Read the PNGs to look; check every figure in numbers.txt)")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("page")
    ap.add_argument("--mock")
    ap.add_argument("--out", default="qa_out")
    ap.add_argument("--strict", action="store_true", help="exit 1 on warnings too")
    a = ap.parse_args()
    rep = check(a.page, a.mock, a.out)
    print_report(rep)
    sys.exit(1 if rep["fails"] or (a.strict and rep["warns"]) else 0)
