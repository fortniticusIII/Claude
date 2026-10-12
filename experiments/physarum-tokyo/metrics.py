"""Network metrics following Tero et al. (2010):
TL  total length (cost); MD mean shortest-path distance over all FS pairs (transport); both normalised by the MST.
FT  fault tolerance = 1 - P(a single random failure disconnects some FS from another).
    FT_len : failure at a uniformly random point along the network (P = bridge length / TL).
    FT_link: failure of a uniformly random link between junctions (P = bridge links / links).
"""
import numpy as np, networkx as nx, scipy.sparse as sp, scipy.sparse.csgraph as cg

def mesh_graph(m):
    n = len(m["xy"]); e = m["edges"]
    return sp.coo_matrix((m["L"], (e[:, 0], e[:, 1])), shape=(n, n)).tocsr()

def geodesics(m):
    """FS x FS land distances and predecessors on the full mesh."""
    A = mesh_graph(m)
    dist, pred = cg.dijkstra(A, directed=False, indices=m["fs"], return_predecessors=True)
    return dist[:, m["fs"]], pred

def path_nodes(pred_row, src, dst):
    p = [dst]
    while p[-1] != src:
        p.append(pred_row[p[-1]])
    return p[::-1]

def prune(G, keep):
    """Strip everything that serves no food source: on the bridge tree (2-edge-connected blocks joined by
    bridges), repeatedly drop leaf blocks without a food source. Unlike leaf-stripping, this also removes
    dead-end spurs that end in a small loop."""
    G = G.copy()
    G.remove_nodes_from([v for v in list(G) if G.degree(v) == 0 and v not in keep])
    br = list(nx.bridges(G))
    H = G.copy(); H.remove_edges_from(br)
    comp = {}
    for k, c in enumerate(nx.connected_components(H)):
        for v in c: comp[v] = k
    has_fs = {}
    for v in keep:
        if v in comp: has_fs[comp[v]] = True
    T = nx.MultiGraph(); T.add_nodes_from(set(comp.values()))
    for a, b in br: T.add_edge(comp[a], comp[b])
    while True:
        leaves = [c for c in T if T.degree(c) <= 1 and not has_fs.get(c)]
        if not leaves: break
        T.remove_nodes_from(leaves)
    alive = set(T)
    return G.subgraph([v for v in G if comp[v] in alive]).copy()

def contract(G, keep):
    """Collapse chains of degree-2 non-FS nodes into single links; returns MultiGraph of links."""
    H = nx.MultiGraph(); junction = {v for v in G if G.degree(v) != 2 or v in keep}
    seen = set()
    for a in junction:
        for b in G.neighbors(a):
            if (a, b) in seen: continue
            length = G[a][b]["weight"]; prev, cur = a, b; seen.add((a, b)); seen.add((b, a))
            while cur not in junction:
                nxt = [w for w in G.neighbors(cur) if w != prev][0]
                length += G[cur][nxt]["weight"]; seen.add((cur, nxt)); seen.add((nxt, cur)); prev, cur = cur, nxt
            seen.add((cur, prev)); H.add_edge(a, cur, weight=length)
    if not junction and len(G):  # pure cycle (not expected)
        H.add_edge(0, 0, weight=sum(d["weight"] for *_, d in G.edges(data=True)))
    return H

def evaluate(G, terminals, return_graph=False):
    """G: nx.Graph with 'weight'; terminals: list of node ids (FS)."""
    terminals = list(terminals); keep = set(terminals)
    G = prune(G, keep)
    connected = all(t in G for t in terminals) and \
        set(terminals) <= nx.node_connected_component(G, terminals[0])
    if not connected:
        return dict(connected=False)
    G = G.subgraph(nx.node_connected_component(G, terminals[0])).copy()
    G = prune(G, keep)
    TL = G.size(weight="weight")
    H = contract(G, keep)
    # bridges on the multigraph: a link is a bridge if removing it disconnects; parallel links protect each other
    simple = nx.Graph()
    for a, b, d in H.edges(data=True):
        if simple.has_edge(a, b): simple[a][b]["mult"] += 1; simple[a][b]["w"] += d["weight"]
        else: simple.add_edge(a, b, mult=1, w=d["weight"])
    bridges = [(a, b) for a, b in nx.bridges(simple) if simple[a][b]["mult"] == 1]
    blen = sum(simple[a][b]["w"] for a, b in bridges)
    nlinks = H.number_of_edges()
    ts = set(terminals); idx = {t: i for i, t in enumerate(terminals)}
    md = []
    for i, t in enumerate(terminals):
        dist = nx.single_source_dijkstra_path_length(G, t, weight="weight")
        md.extend(dist[u] for u in terminals[i + 1:])
    out = dict(connected=True, TL=TL, MD=float(np.mean(md)), FT_len=1 - blen / TL, FT_link=1 - len(bridges) / nlinks,
               links=nlinks, junctions=H.number_of_nodes(), bridges=len(bridges))
    if return_graph:
        out["graph"] = G; out["bridge_links"] = bridges; out["links_graph"] = H
    return out

def physarum_graph(m, D, thr=1e-3):
    e = m["edges"]; alive = D > thr
    G = nx.Graph()
    G.add_weighted_edges_from((int(a), int(b), float(l)) for (a, b), l in zip(e[alive], m["L"][alive]))
    return G

def abstract_graph(edges, W):
    """Graph on FS indices with geodesic weights; edges list of (i,j)."""
    G = nx.Graph(); G.add_nodes_from(range(len(W)))
    G.add_weighted_edges_from((i, j, float(W[i, j])) for i, j in edges)
    return G

def mst_edges(W):
    T = cg.minimum_spanning_tree(sp.csr_matrix(np.triu(W, 1)))
    r, c = T.nonzero(); return list(zip(r.tolist(), c.tolist()))
