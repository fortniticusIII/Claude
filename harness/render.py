"""Render a database-backed page against real data, without publishing it.

    python3 harness/render.py <page.html> <mock.json> <output prefix>

mock.json maps collection names to lists of {"id": ..., "data": {...}}, e.g. built from an
ArtifactData list with out_dir. The script wraps the page in the publish skeleton, stubs
window.claude.use('db') with that data, and saves phone (light) and desktop (dark)
screenshots. It prints scrollWidth per viewport (should equal the width) and any script errors.
Needs Playwright's Chromium (in this sandbox: /opt/pw-browsers).
"""
import json, sys
from playwright.sync_api import sync_playwright
page_path, mock_path, prefix = sys.argv[1:4]
data = json.load(open(mock_path))
mock = """<script>
window.__DATA__ = %s;
window.claude = { use: async n => n !== 'db' ? null : ({
  collection: name => { let ord=null, wh=[];
    const q = { orderBy(f,d){ord=[f,d];return q;}, limit(){return q;}, where(f,op,v){wh.push([f,op,v]);return q;},
      onSnapshot(cb){ setTimeout(()=>{ let docs=(window.__DATA__[name]||[]).map(x=>({id:x.id,data:()=>x.data}));
        if(ord) docs.sort((a,b)=>String(a.data()[ord[0]]).localeCompare(String(b.data()[ord[0]]))*(ord[1]==='desc'?-1:1));
        cb({docs,size:docs.length,empty:!docs.length}); },30); return ()=>{}; } };
    return q; },
  doc: path => ({ onSnapshot(cb){ setTimeout(()=>{ const [c,id]=path.split('/'); const x=(window.__DATA__[c]||[]).find(d=>d.id===id); cb({id, exists:!!x, data:()=>x&&x.data}); },30); return ()=>{}; } })
}) };
</script>""" % json.dumps(data)
skel = '<!doctype html><html><head><meta charset=utf8><meta name=viewport content="width=device-width,initial-scale=1,viewport-fit=cover"><style>:root{color-scheme:light}body{margin:0;padding:0;font:14px sans-serif}img{max-width:100%}[hidden]{display:none!important}</style></head><body>'
out = page_path.rsplit('/',1)[0] + '/harness.html'
open(out,'w').write(skel + mock + open(page_path).read() + '</body></html>')
with sync_playwright() as p:
    b = p.chromium.launch(); errs=[]
    for name,w,scheme in [("phone-light",390,"light"),("desktop-dark",1000,"dark")]:
        pg = b.new_page(viewport={"width":w,"height":900}, color_scheme=scheme)
        pg.on("pageerror", lambda e, n=name: errs.append(f"{n}: pageerror {e}"))
        pg.on("console", lambda m, n=name: errs.append(f"{n}: {m.text}") if m.type=="error" and "ERR_FAILED" not in m.text else None)
        pg.route("**/fonts.googleapis.com/**", lambda r: r.abort())
        pg.goto("file://"+out); pg.wait_for_timeout(500)
        print(name, "scrollWidth", pg.evaluate("document.documentElement.scrollWidth"), "of", w)
        pg.screenshot(path=f"{prefix}-{name}.png", full_page=True)
    print("\n".join(errs) or "no script errors"); b.close()
