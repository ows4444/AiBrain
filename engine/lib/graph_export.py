"""Export the brain's wikilink graph as CSV edges or GraphML.

Usage:
    brain graph [out] [--format csv|graphml] [--json]

Default output is motor/graph/edges.csv (or graph.graphml), which git ignores.
CSV loads into NetworkX, Kuzu, Neo4j or a spreadsheet. GraphML opens in Gephi.
Node ids are root-relative paths, so two pages with the same name never merge.
An edge carries its relation when the link is typed (`(supports:: [[X]])`).
No dependencies.
"""
import csv
import os
import sys
from xml.sax.saxutils import escape, quoteattr

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vaultlib import Vault  # noqa: E402


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


def arguments(ap):
    ap.add_argument("out", nargs="?")
    ap.add_argument("--format", choices=["csv", "graphml"], default="csv")


def run(root, args):
    out = args.out or os.path.join(root, "motor", "graph", "edges.csv" if args.format == "csv" else "graph.graphml")
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    vault = Vault(root)
    pages, edges, relations = vault.knowledge, vault.knowledge_edges(), relation_of(vault)
    if args.format == "csv":
        write_csv(out, edges, relations)
    else:
        write_graphml(out, pages, edges, relations)
    return {"nodes": len(pages), "edges": len(edges), "format": args.format, "out": out}


def render(result, args):
    return f"{result['nodes']} nodes, {result['edges']} edges -> {result['out']}"
