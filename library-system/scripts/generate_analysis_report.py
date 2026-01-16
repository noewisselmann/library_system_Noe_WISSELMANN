# scripts/generate_analysis_report.py
# Génère un PDF "Rapport d'Analyse" (5-8 pages) de façon professionnelle,
# en s'appuyant SUR TON schema.cql (pour éviter d'inventer les PK/CK).
#
# Dépendances (déjà dans ton projet normalement) :
#   pip install reportlab
#
# Utilisation :
#   python -m scripts.generate_analysis_report
#
# Entrées attendues (si présentes) :
#   - schema/schema.cql   (recommandé) : pour extraire tables + partition/clustering keys
#
# Sortie :
#   report/rapport_analyse.pdf

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    PageBreak,
    Table,
    TableStyle,
    KeepTogether,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.graphics.shapes import Drawing, Rect, String, Line, Polygon
from reportlab.platypus.flowables import Flowable

GIT_REPO_URL = "https://github.com/noewisselmann/library_system_Noe_WISSELMANN.git"


# ----------------------------
# Data structures
# ----------------------------

@dataclass
class TableInfo:
    name: str
    partition_keys: List[str]
    clustering_keys: List[str]
    raw_primary_key: str
    columns: List[str]  # "col type" strings (best effort)


# ----------------------------
# Helpers: schema parsing
# ----------------------------

CREATE_TABLE_RE = re.compile(
    r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(?P<name>[a-zA-Z0-9_.\"]+)\s*\((?P<body>.*?)\)\s*;",
    re.IGNORECASE | re.DOTALL,
)

PRIMARY_KEY_RE = re.compile(
    r"PRIMARY\s+KEY\s*\((?P<pk>.*?)\)\s*$",
    re.IGNORECASE,
)

def _clean_ident(s: str) -> str:
    s = s.strip()
    if s.startswith('"') and s.endswith('"'):
        return s[1:-1]
    if "." in s:
        # keyspace.table -> table
        return s.split(".")[-1]
    return s

def _split_top_level_commas(s: str) -> List[str]:
    """Split by commas but respect parentheses nesting."""
    parts = []
    buf = []
    depth = 0
    for ch in s:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        if ch == "," and depth == 0:
            parts.append("".join(buf).strip())
            buf = []
        else:
            buf.append(ch)
    if buf:
        parts.append("".join(buf).strip())
    return [p for p in parts if p]

def _parse_primary_key(pk_expr: str) -> Tuple[List[str], List[str]]:
    """
    Examples:
      PRIMARY KEY ((a), b, c)
      PRIMARY KEY (a, b)
      PRIMARY KEY ((a,b), c)
    """
    pk_expr = pk_expr.strip()
    # remove surrounding parentheses if any
    # pk_expr is inside "PRIMARY KEY ( ... )" already extracted without outermost
    items = _split_top_level_commas(pk_expr)
    if not items:
        return [], []

    first = items[0].strip()
    part_keys: List[str] = []
    clust_keys: List[str] = []

    if first.startswith("(") and first.endswith(")"):
        inside = first[1:-1].strip()
        # Could be "(a,b)" or "(a)"
        part_keys = [_clean_ident(x) for x in _split_top_level_commas(inside)]
        clust_keys = [_clean_ident(x) for x in items[1:]]
    else:
        # single partition key
        part_keys = [_clean_ident(first)]
        clust_keys = [_clean_ident(x) for x in items[1:]]

    return part_keys, clust_keys

def parse_schema_cql(schema_path: str) -> List[TableInfo]:
    if not os.path.exists(schema_path):
        return []

    with open(schema_path, "r", encoding="utf-8") as f:
        content = f.read()

    tables: List[TableInfo] = []

    for m in CREATE_TABLE_RE.finditer(content):
        tname = _clean_ident(m.group("name"))
        body = m.group("body")

        # lines/segments inside table definition separated by top-level commas
        segments = _split_top_level_commas(body)

        raw_pk_line = ""
        columns: List[str] = []

        for seg in segments:
            seg_clean = seg.strip().rstrip()
            pk_m = PRIMARY_KEY_RE.search(seg_clean)
            if pk_m:
                raw_pk_line = pk_m.group("pk").strip()
            else:
                # column definition (best effort): ignore WITH options here (should not be inside body)
                # Example: "user_id uuid" or "borrow_date timestamp"
                col = " ".join(seg_clean.split())
                if col:
                    columns.append(col)

        part_keys, clust_keys = ([], [])
        if raw_pk_line:
            part_keys, clust_keys = _parse_primary_key(raw_pk_line)

        tables.append(
            TableInfo(
                name=tname,
                partition_keys=part_keys,
                clustering_keys=clust_keys,
                raw_primary_key=raw_pk_line,
                columns=columns,
            )
        )

    # Stable order
    tables.sort(key=lambda t: t.name.lower())
    return tables


# ----------------------------
# Helpers: styling & layout
# ----------------------------

def try_register_fonts():
    """
    Optionnel : si tu ajoutes des TTF dans assets/fonts.
    Le PDF reste OK sans, on tombe sur Helvetica.
    """
    fonts_dir = os.path.join("assets", "fonts")
    if not os.path.isdir(fonts_dir):
        return

    candidates = [
        ("Inter", "Inter-Regular.ttf"),
        ("Inter-Bold", "Inter-Bold.ttf"),
    ]
    for name, file in candidates:
        path = os.path.join(fonts_dir, file)
        if os.path.exists(path):
            pdfmetrics.registerFont(TTFont(name, path))

def build_styles():
    styles = getSampleStyleSheet()

    base_font = "Helvetica"
    bold_font = "Helvetica-Bold"
    # If you registered "Inter", switch automatically
    if "Inter" in pdfmetrics.getRegisteredFontNames():
        base_font = "Inter"
    if "Inter-Bold" in pdfmetrics.getRegisteredFontNames():
        bold_font = "Inter-Bold"

    styles.add(
        ParagraphStyle(
            name="TitleX",
            parent=styles["Title"],
            fontName=bold_font,
            fontSize=22,
            leading=26,
            alignment=TA_LEFT,
            spaceAfter=12,
        )
    )
    styles.add(
        ParagraphStyle(
            name="H1",
            parent=styles["Heading1"],
            fontName=bold_font,
            fontSize=14,
            leading=18,
            spaceBefore=10,
            spaceAfter=6,
        )
    )
    styles.add(
        ParagraphStyle(
            name="H2",
            parent=styles["Heading2"],
            fontName=bold_font,
            fontSize=12,
            leading=15,
            spaceBefore=8,
            spaceAfter=4,
        )
    )
    styles.add(
        ParagraphStyle(
            name="BodyX",
            parent=styles["BodyText"],
            fontName=base_font,
            fontSize=10.5,
            leading=14,
        )
    )
    styles.add(
        ParagraphStyle(
            name="SmallX",
            parent=styles["BodyText"],
            fontName=base_font,
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#444444"),
        )
    )
    styles.add(
        ParagraphStyle(
            name="CenterSmall",
            parent=styles["BodyText"],
            fontName=base_font,
            fontSize=9,
            leading=12,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#444444"),
        )
    )
    return styles, base_font, bold_font


def make_kv_table(rows: List[Tuple[str, str]]) -> Table:
    t = Table(rows, colWidths=[55 * mm, 125 * mm])
    t.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 9.5),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#222222")),
                ("TEXTCOLOR", (1, 0), (1, -1), colors.HexColor("#222222")),
                ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#DDDDDD")),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return t


def make_tables_summary_table(tables: List[TableInfo]) -> Table:
    data = [["Table", "Partition key(s)", "Clustering key(s)"]]
    for t in tables:
        pk = ", ".join(t.partition_keys) if t.partition_keys else "Non détecté (schema.cql manquant ?)"
        ck = ", ".join(t.clustering_keys) if t.clustering_keys else "-"
        data.append([t.name, pk, ck])

    tbl = Table(data, colWidths=[55 * mm, 70 * mm, 55 * mm])
    tbl.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F172A")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 10),
                ("ALIGN", (0, 0), (-1, 0), "LEFT"),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#E5E7EB")),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 1), (-1, -1), 9),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return tbl


# ----------------------------
# Architecture diagram (vector)
# ----------------------------

def architecture_diagram() -> Drawing:
    """
    Schéma simple et propre, vectoriel (pas d'image externe).
    """
    w = 180 * mm
    h = 85 * mm
    d = Drawing(w, h)

    # Colors
    ink = colors.HexColor("#0F172A")
    soft = colors.HexColor("#E5E7EB")
    card = colors.HexColor("#F8FAFC")

    # Title
    d.add(String(0, h - 10, "Architecture - Application Python + Cluster Cassandra", fontName="Helvetica-Bold", fontSize=12, fillColor=ink))

    # App box
    app_x, app_y, app_w, app_h = 0, 20 * mm, 60 * mm, 45 * mm
    d.add(Rect(app_x, app_y, app_w, app_h, strokeColor=soft, fillColor=card, rx=6, ry=6))
    d.add(String(app_x + 8, app_y + app_h - 14, "Python App", fontName="Helvetica-Bold", fontSize=11, fillColor=ink))
    d.add(String(app_x + 8, app_y + app_h - 28, "- CLI (Click)", fontName="Helvetica", fontSize=9, fillColor=ink))
    d.add(String(app_x + 8, app_y + app_h - 40, "- Web (Flask)", fontName="Helvetica", fontSize=9, fillColor=ink))
    d.add(String(app_x + 8, app_y + app_h - 52, "- Repositories / Models", fontName="Helvetica", fontSize=9, fillColor=ink))

    # Driver arrow
    ax1 = app_x + app_w + 6
    ay1 = app_y + app_h / 2
    ax2 = ax1 + 22 * mm
    ay2 = ay1
    d.add(Line(ax1, ay1, ax2, ay2, strokeColor=ink, strokeWidth=1))
    d.add(Polygon([ax2, ay2, ax2 - 4, ay2 + 2, ax2 - 4, ay2 - 2], fillColor=ink, strokeColor=ink))
    d.add(String(ax1 + 4, ay1 + 6, "cassandra-driver", fontName="Helvetica", fontSize=8, fillColor=ink))

    # Cassandra cluster container
    cl_x, cl_y, cl_w, cl_h = ax2 + 6, 15 * mm, 105 * mm, 55 * mm
    d.add(Rect(cl_x, cl_y, cl_w, cl_h, strokeColor=soft, fillColor=colors.white, rx=6, ry=6))
    d.add(String(cl_x + 8, cl_y + cl_h - 14, "Apache Cassandra Cluster", fontName="Helvetica-Bold", fontSize=11, fillColor=ink))
    d.add(String(cl_x + 8, cl_y + cl_h - 28, "Keyspace: library_system", fontName="Helvetica", fontSize=9, fillColor=ink))
    d.add(String(cl_x + 8, cl_y + cl_h - 40, "Replication factor: 3 (local)", fontName="Helvetica", fontSize=9, fillColor=ink))

    # Nodes
    node_w, node_h = 30 * mm, 18 * mm
    nx1, ny = cl_x + 10 * mm, cl_y + 10 * mm
    gap = 7 * mm

    for i, name in enumerate(["Node 1 (seed)", "Node 2", "Node 3"]):
        x = nx1 + i * (node_w + gap)
        d.add(Rect(x, ny, node_w, node_h, strokeColor=soft, fillColor=card, rx=6, ry=6))
        d.add(String(x + 6, ny + node_h - 12, name, fontName="Helvetica-Bold", fontSize=8.5, fillColor=ink))
        d.add(String(x + 6, ny + 6, "CQL : 9042", fontName="Helvetica", fontSize=8, fillColor=ink))

    return d


# ----------------------------
# Header/footer
# ----------------------------

def add_header_footer(canvas, doc, title: str):
    canvas.saveState()
    w, h = A4

    # Header line
    canvas.setStrokeColor(colors.HexColor("#E5E7EB"))
    canvas.setLineWidth(0.7)
    canvas.line(18 * mm, h - 18 * mm, w - 18 * mm, h - 18 * mm)

    canvas.setFont("Helvetica-Bold", 9)
    canvas.setFillColor(colors.HexColor("#0F172A"))
    canvas.drawString(18 * mm, h - 14 * mm, title)

    # Footer
    canvas.setStrokeColor(colors.HexColor("#E5E7EB"))
    canvas.setLineWidth(0.7)
    canvas.line(18 * mm, 15 * mm, w - 18 * mm, 15 * mm)

    canvas.setFont("Helvetica", 9)
    canvas.setFillColor(colors.HexColor("#475569"))
    canvas.drawString(18 * mm, 10 * mm, f"Généré le {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    canvas.drawRightString(w - 18 * mm, 10 * mm, f"Page {doc.page}")

    canvas.restoreState()


# ----------------------------
# Main PDF builder
# ----------------------------

def build_report(
    out_pdf_path: str = os.path.join("report", "rapport_analyse.pdf"),
    schema_path: str = os.path.join("schema", "schema.cql"),
):
    os.makedirs(os.path.dirname(out_pdf_path), exist_ok=True)

    try_register_fonts()
    styles, base_font, bold_font = build_styles()

    tables = parse_schema_cql(schema_path)

    doc = SimpleDocTemplate(
        out_pdf_path,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=22 * mm,
        bottomMargin=18 * mm,
        title="Rapport d'Analyse - Systeme de Gestion de Bibliotheque Numerique",
        author="Projet Library System",
    )

    story: List = []

    # --- Cover
    story.append(Paragraph("Rapport d'Analyse", styles["TitleX"]))

    story.append(Spacer(1, 12))

    story.append(Paragraph(
        f"<b>Repository Git :</b><br/>{GIT_REPO_URL}",
        styles["Normal"]
    ))
    story.append(Spacer(1, 24))
    story.append(Paragraph("Systeme de Gestion de Bibliotheque Numerique (Python + Apache Cassandra)", styles["BodyX"]))
    story.append(Spacer(1, 10))
    story.append(
        make_kv_table(
            [
                ("Objectif", "Documenter la modelisation Cassandra, justifier les cles (partition/clustering), "
                            "expliquer les compromis coherence/disponibilite, et comparer a une approche SQL."),
                ("Perimetre", "Livres, utilisateurs, emprunts, emprunts actifs, historiques et tables de navigation (denormalisation)."),
                ("Source de verite", f"schema.cql: {'trouve' if os.path.exists(schema_path) else 'absent'}"),
            ]
        )
    )
    story.append(Spacer(1, 14))
    story.append(Paragraph("Architecture", styles["H1"]))
    story.append(Spacer(1, 6))
    story.append(architecture_diagram())
    story.append(Spacer(1, 10))
    story.append(Paragraph(
        "Note: si le fichier schema/schema.cql est absent, le rapport indiquera 'Non detecte' au lieu d'inventer des cles.",
        styles["SmallX"],
    ))
    story.append(PageBreak())

    # --- Section: Data model & query patterns
    story.append(Paragraph("1. Modelisation Cassandra (oriente requetes)", styles["H1"]))
    story.append(Paragraph(
        "Cassandra impose une modelisation par patterns de requetes: une table par besoin de lecture/tri, "
        "avec duplication volontaire des donnees pour eviter joins et scans.",
        styles["BodyX"],
    ))
    story.append(Spacer(1, 8))

    story.append(Paragraph("Tables detectees dans le schema", styles["H2"]))
    if tables:
        story.append(Spacer(1, 6))
        story.append(make_tables_summary_table(tables))
    else:
        story.append(Paragraph(
            "Je ne sais pas lister les cles (PK/CK) car schema/schema.cql est introuvable. "
            "Ajoute le fichier schema.cql et relance la generation.",
            styles["BodyX"],
        ))

    story.append(Spacer(1, 10))
    story.append(Paragraph("Raisons principales de la denormalisation", styles["H2"]))
    story.append(Paragraph(
        "- Lecture rapide par cle de partition (pas de scans).<br/>"
        "- Ordonner les resultats via clustering keys (historique par date, etc.).<br/>"
        "- Eviter ALLOW FILTERING et les index secondaires systematiques.",
        styles["BodyX"],
    ))
    story.append(PageBreak())

    # --- Section: PK/CK justification (auto + narrative)
    story.append(Paragraph("2. Justification des Partition Keys et Clustering Keys", styles["H1"]))
    story.append(Paragraph(
        "Cette section est generee a partir de schema.cql. Pour chaque table, on rappelle la cle primaire et "
        "on explique l'impact sur distribution et tri dans Cassandra.",
        styles["BodyX"],
    ))
    story.append(Spacer(1, 8))

    if tables:
        for t in tables:
            pk = ", ".join(t.partition_keys) if t.partition_keys else "Non detecte"
            ck = ", ".join(t.clustering_keys) if t.clustering_keys else "-"
            story.append(KeepTogether([
                Paragraph(f"Table: <b>{t.name}</b>", styles["H2"]),
                Paragraph(f"Primary key (brut): <font size='9'>{t.raw_primary_key or 'Non detecte'}</font>", styles["BodyX"]),
                Spacer(1, 4),
                make_kv_table([
                    ("Partition key(s)", pk),
                    ("Clustering key(s)", ck),
                    ("But principal", "A completer: decris ici le query pattern principal de la table (lecture/tri)."),
                ]),
                Spacer(1, 8),
            ]))
        story.append(Spacer(1, 6))
        story.append(Paragraph(
            "A completer: remplace les lignes 'But principal' par tes explications exactes (ex: 'recherche par ISBN', "
            "'historique d un utilisateur trie par date', etc.). Le PDF est genere proprement, mais il ne peut pas deviner "
            "tes intentions si elles ne figurent pas explicitement dans le schema ou la doc.",
            styles["SmallX"],
        ))
    else:
        story.append(Paragraph(
            "Je ne sais pas justifier PK/CK car schema/schema.cql est absent. Ajoute-le et relance.",
            styles["BodyX"],
        ))

    story.append(PageBreak())

    # --- Consistency vs Availability
    story.append(Paragraph("3. Coherence vs Disponibilite (CAP) et niveaux de consistency", styles["H1"]))
    story.append(Paragraph(
        "Cassandra privilegie la disponibilite et la tolerance aux partitions. La coherence est ajustable par requete "
        "via les niveaux (ONE, QUORUM, ALL).",
        styles["BodyX"],
    ))
    story.append(Spacer(1, 8))
    story.append(Paragraph("Points a presenter pendant la demo", styles["H2"]))
    story.append(Paragraph(
        "- Lecture/criture en LOCAL (cluster 3 noeuds) : on peut illustrer la haute dispo en arretaient un noeud.<br/>"
        "- QUORUM: compromis classique (majorite) pour limiter les lectures incoherentes.<br/>"
        "- ONE: latence minimale mais risque plus eleve de lire une donnee non encore repliquee.<br/>"
        "- ALL: coherence maximale mais indisponibilite si un noeud est down.",
        styles["BodyX"],
    ))
    story.append(Spacer(1, 10))
    story.append(Paragraph("Recommandation (a adapter)", styles["H2"]))
    story.append(Paragraph(
        "Pour une bibliotheque: ecritures en QUORUM et lectures en QUORUM/ONE selon criticite "
        "(ex: disponibilite d exemplaires peut demander QUORUM).",
        styles["BodyX"],
    ))
    story.append(PageBreak())

    # --- SQL comparison
    story.append(Paragraph("4. Comparaison avec une approche SQL", styles["H1"]))
    story.append(Paragraph(
        "SQL normalise les donnees et repose sur joins et transactions ACID. Cassandra evite joins/subqueries et "
        "accepte la duplication pour obtenir des lectures predecibles a grande echelle.",
        styles["BodyX"],
    ))
    story.append(Spacer(1, 10))

    comp = Table(
        [
            ["Sujet", "SQL (relationnel)", "Cassandra (NoSQL distribue)"],
            ["Modelisation", "Normalisation, joins", "Une table par requete, denormalisation"],
            ["Scalabilite", "Scale-up, sharding complexe", "Scale-out horizontal natif"],
            ["Transactions", "ACID (souvent)", "Pas ACID global, coherence ajustable"],
            ["Requetes", "Flexible (WHERE, joins)", "Doit fournir partition key pour perf optimale"],
        ],
        colWidths=[35 * mm, 70 * mm, 70 * mm],
    )
    comp.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F172A")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 10),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#E5E7EB")),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 1), (-1, -1), 9),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(comp)

    story.append(PageBreak())

    # --- Performance tests (optional)
    story.append(Paragraph("5. Tests de performance (optionnel)", styles["H1"]))
    story.append(Paragraph(
        "Cette section est un gabarit: tu peux ajouter des mesures (latence moyenne, throughput) "
        "en lecture/criture via un script de benchmark.",
        styles["BodyX"],
    ))
    story.append(Spacer(1, 8))
    story.append(Paragraph("Idees de mesures simples", styles["H2"]))
    story.append(Paragraph(
        "- Insert de N livres / N utilisateurs (prepared statements).<br/>"
        "- Lecture par ISBN (books_by_id).<br/>"
        "- Historique des emprunts d un utilisateur (borrows_by_user).<br/>"
        "- Arret d un noeud et verification que l app reste utilisable (selon consistency).",
        styles["BodyX"],
    ))
    story.append(Spacer(1, 10))
    story.append(Paragraph(
        "Astuce: evite SELECT COUNT(*) sans partition key en demo, Cassandra affichera un warning "
        "(et ce n est pas un pattern de prod).",
        styles["SmallX"],
    ))

    # Build with header/footer
    title = "Rapport d'Analyse - Library System"
    doc.build(
        story,
        onFirstPage=lambda c, d: add_header_footer(c, d, title),
        onLaterPages=lambda c, d: add_header_footer(c, d, title),
    )


if __name__ == "__main__":
    build_report()
    print("OK: report/rapport_analyse.pdf")
