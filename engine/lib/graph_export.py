"""Export the brain's wikilink graph: CSV edges, GraphML, or one HTML page to look at.

Usage:
    brain graph [out] [--format csv|graphml|html] [--json]

Default output is motor/graph/edges.csv (or graph.graphml, graph.html), which git ignores.
CSV loads into NetworkX, Kuzu, Neo4j or a spreadsheet. GraphML opens in Gephi.
Node ids are root-relative paths, so two pages with the same name never merge.
An edge carries its relation when the link is typed (`(supports:: [[X]])`).

--format html writes a single file that opens in a browser from the disk: the
pages as marks (the hue is the stage of memory, the shape the type of page),
the links between them, a search, the types as switches, each page's summary
and links on selection, and the same pages as a table. It holds its own
script and styles and a policy that refuses every request, so it needs no
network and makes no call. It also holds every page's title and summary:
it is the brain in one file, to be shared no more freely than the pages.
No dependencies.
"""
import csv
import datetime
import json
import os
import sys
from xml.sax.saxutils import escape, quoteattr

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vaultlib import Vault  # noqa: E402

FILES = {"csv": "edges.csv", "graphml": "graph.graphml", "html": "graph.html"}  # a format's default file
TEMPLATE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates", "graph.html")


def relation_of(vault):
    """(source, target) -> relation; several relations on one edge are joined with ';'."""
    out = {}
    for a, rel, b in vault.typed_edges():
        out.setdefault((a, b), set()).add(rel)
    return {k: ";".join(sorted(v)) for k, v in out.items()}


def write_csv(path, edges, relations):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["source", "target", "relation"])
        w.writerows(sorted((a.rel, b.rel, relations.get((a, b), "")) for a, b in edges))


def write_graphml(path, pages, edges, relations):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        fh.write('<graphml xmlns="http://graphml.graphdrawing.org/xmlns">\n')
        fh.write('<key id="type" for="node" attr.name="type" attr.type="string"/>\n')
        fh.write('<key id="title" for="node" attr.name="title" attr.type="string"/>\n')
        fh.write('<key id="relation" for="edge" attr.name="relation" attr.type="string"/>\n')
        fh.write('<graph edgedefault="directed">\n')
        for p in pages:
            fh.write(f'<node id={quoteattr(p.rel)}><data key="type">{escape(p.type)}</data>'
                     f'<data key="title">{escape(p.title)}</data></node>\n')
        for i, (a, b) in enumerate(sorted(edges, key=lambda e: (e[0].rel, e[1].rel))):
            rel = relations.get((a, b))
            data = f'<data key="relation">{escape(rel)}</data>' if rel else ""
            fh.write(f'<edge id="e{i}" source={quoteattr(a.rel)} target={quoteattr(b.rel)}>{data}</edge>\n')
        fh.write("</graph>\n</graphml>\n")


def write_html(path, pages, edges, relations, title, made):
    """The template with the graph in it as data. A page's words are data there, never markup."""
    pages = sorted(pages, key=lambda p: p.rel)
    at = {p: i for i, p in enumerate(pages)}
    graph = {"title": title, "made": made,
             "nodes": [{"id": p.rel, "title": p.title, "type": p.type, "summary": p.summary,
                        "status": p.fields.get("status") if isinstance(p.fields.get("status"), str) else ""}
                       for p in pages],
             "edges": sorted([at[a], at[b], relations.get((a, b), "")] for a, b in edges)}
    # `<` is written as an escape, so no title or summary can close the data block it sits in.
    data = json.dumps(graph, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    with open(TEMPLATE, encoding="utf-8") as fh:
        page = fh.read()
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(page.replace("__TITLE__", escape(title)).replace("__DATA__", data))


def arguments(ap):
    ap.add_argument("out", nargs="?")
    ap.add_argument("--format", choices=sorted(FILES), default="csv")


def run(root, args):
    out = args.out or os.path.join(root, "motor", "graph", FILES[args.format])
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    vault = Vault(root)
    pages, edges, relations = vault.knowledge, vault.knowledge_edges(), relation_of(vault)
    if args.format == "csv":
        write_csv(out, edges, relations)
    elif args.format == "graphml":
        write_graphml(out, pages, edges, relations)
    else:
        write_html(out, pages, edges, relations, f"{os.path.basename(os.path.realpath(root))}: the graph",
                   datetime.date.today().isoformat())
    return {"nodes": len(pages), "edges": len(edges), "format": args.format, "out": out}


def render(result, args):
    return f"{result['nodes']} nodes, {result['edges']} edges -> {result['out']}" + (
        "\n  open it in a browser: it needs no network, and holds every page's title and summary"
        if result["format"] == "html" else "")
