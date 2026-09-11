"""
report.py
----------
Generates official, multi-section Legal Metrology & FSSAI Food Safety Inspection
Certificates using ReportLab.
"""

import os
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, KeepTogether
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle


def generate_pdf_report(product_name, result, output_path="compliance_report.pdf", notice_data=None):
    """
    Builds a professional multi-page inspection report including:
      - Executive Compliance Summary & 3-Tier Badge
      - Legal Metrology 7-Rule Audit Table
      - FSSAI Food Safety & Banned Additives Audit
      - Nutritional Proportion & HFSS Analysis
      - Annexure: Statutory Show-Cause Notice
    """
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
    )

    styles = getSampleStyleSheet()

    # Custom styles
    header_style = ParagraphStyle(
        "GovHeader",
        parent=styles["Normal"],
        fontSize=13,
        leading=16,
        fontName="Helvetica-Bold",
        textColor=colors.HexColor("#0D233A"),
        alignment=1,  # Center
    )
    sub_header_style = ParagraphStyle(
        "GovSubHeader",
        parent=styles["Normal"],
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#4B5563"),
        alignment=1,
    )
    section_title = ParagraphStyle(
        "SectionTitle",
        parent=styles["Heading2"],
        fontSize=11,
        leading=14,
        fontName="Helvetica-Bold",
        textColor=colors.HexColor("#065A82"),
        spaceBefore=10,
        spaceAfter=4,
    )
    cell_text = ParagraphStyle(
        "CellText",
        parent=styles["Normal"],
        fontSize=8,
        leading=10,
    )
    cell_bold = ParagraphStyle(
        "CellBold",
        parent=styles["Normal"],
        fontSize=8,
        leading=10,
        fontName="Helvetica-Bold",
    )

    story = []

    # -------------------------------------------------------------
    # 1. HEADER BANNER
    # -------------------------------------------------------------
    story.append(Paragraph("GOVERNMENT OF INDIA", header_style))
    story.append(Paragraph("MINISTRY OF CONSUMER AFFAIRS, FOOD & PUBLIC DISTRIBUTION", header_style))
    story.append(Paragraph("DIRECTORATE OF LEGAL METROLOGY & FOOD STANDARDS (METRO CHECK)", sub_header_style))
    story.append(Spacer(1, 4 * mm))

    # Divider line
    story.append(Table([[""]], colWidths=[180 * mm], rowHeights=[1.5], style=[("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#065A82"))]))
    story.append(Spacer(1, 4 * mm))

    # Inspection Metadata Card
    status = result.get("decision", {}).get("status", "NEEDS REVIEW")
    score = result.get("compliance_score", 0)
    badge_bg = "#22C55E" if status == "COMPLIANT" else "#EAB308" if status == "NEEDS REVIEW" else "#EF4444"

    meta_table_data = [
        [
            Paragraph(f"<b>Inspection Ref:</b> MC-INSP-{datetime.now().strftime('%Y%m%d%H%M')}", cell_text),
            Paragraph(f"<b>Date:</b> {datetime.now().strftime('%d %b %Y, %H:%M')}", cell_text),
        ],
        [
            Paragraph(f"<b>Product Under Scan:</b> {product_name}", cell_bold),
            Paragraph(f"<b>Status:</b> <font color='{badge_bg}'><b>{status} ({score}%)</b></font>", cell_bold),
        ],
    ]
    meta_table = Table(meta_table_data, colWidths=[110 * mm, 70 * mm])
    meta_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ("PADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 4 * mm))

    # -------------------------------------------------------------
    # 2. LEGAL METROLOGY DECLARATIONS AUDIT TABLE
    # -------------------------------------------------------------
    story.append(Paragraph("1. Legal Metrology (Packaged Commodities) Rules, 2011 Compliance", section_title))
    
    rules_table_data = [
        [
            Paragraph("<b>Mandatory Declaration</b>", cell_bold),
            Paragraph("<b>Rule Reference</b>", cell_bold),
            Paragraph("<b>Status</b>", cell_bold),
            Paragraph("<b>Extracted Evidence</b>", cell_bold),
        ]
    ]

    for r in result.get("rule_results", []):
        st = "PASS" if r["found"] else "FAIL"
        st_color = "#16A34A" if r["found"] else "#DC2626"
        matched = r.get("matched_text") or "-- Not Detected --"
        ref = r.get("rule_ref") or "Rule 6"
        rules_table_data.append([
            Paragraph(r["field"], cell_text),
            Paragraph(ref, cell_text),
            Paragraph(f"<font color='{st_color}'><b>{st}</b></font>", cell_bold),
            Paragraph(matched[:65] + ("..." if len(matched) > 65 else ""), cell_text),
        ])

    rt = Table(rules_table_data, colWidths=[55 * mm, 30 * mm, 20 * mm, 75 * mm])
    rt.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#065A82")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ("PADDING", (0, 0), (-1, -1), 4),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(rt)
    story.append(Spacer(1, 4 * mm))

    # -------------------------------------------------------------
    # 3. FSSAI INGREDIENT & FOOD SAFETY AUDIT
    # -------------------------------------------------------------
    food_data = result.get("food_safety", {})
    ing_data = food_data.get("ingredients", {})
    nut_data = food_data.get("nutrition", {})

    if ing_data:
        story.append(Paragraph("2. Ingredient Safety & Harmful Substance Screening", section_title))
        
        safe_status = ing_data.get("safety_status", "SAFE")
        safe_color = "#16A34A" if "SAFE" in safe_status else "#DC2626"
        
        flagged = ing_data.get("flagged_harmful", [])
        allergens = ing_data.get("detected_allergens", [])
        
        ing_summary = [
            [
                Paragraph(f"<b>Safety Rating:</b> <font color='{safe_color}'><b>{safe_status} (Score: {ing_data.get('safety_score', 100)}/100)</b></font>", cell_text),
                Paragraph(f"<b>Allergens Detected:</b> {', '.join(allergens) if allergens else 'None'}", cell_text),
            ]
        ]
        t_ing_meta = Table(ing_summary, colWidths=[90 * mm, 90 * mm])
        t_ing_meta.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F1F5F9")),
            ("PADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(t_ing_meta)
        story.append(Spacer(1, 2 * mm))

        if flagged:
            flag_table = [
                [
                    Paragraph("<b>Flagged Substance</b>", cell_bold),
                    Paragraph("<b>Risk Category</b>", cell_bold),
                    Paragraph("<b>Statutory Ground / Restriction</b>", cell_bold),
                ]
            ]
            for f in flagged:
                risk_c = "#DC2626" if f["risk"] == "BANNED" else "#D97706"
                flag_table.append([
                    Paragraph(f["name"], cell_text),
                    Paragraph(f"<font color='{risk_c}'><b>{f['risk']}</b></font>", cell_bold),
                    Paragraph(f["reason"], cell_text),
                ])
            t_flag = Table(flag_table, colWidths=[50 * mm, 35 * mm, 95 * mm])
            t_flag.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#7F1D1D")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                ("PADDING", (0, 0), (-1, -1), 4),
            ]))
            story.append(t_flag)
        else:
            story.append(Paragraph("✅ No banned or hazardous additives detected in the ingredients list.", cell_text))
        
        story.append(Spacer(1, 4 * mm))

    # -------------------------------------------------------------
    # 4. NUTRITION & CALORIE PROPORTION AUDIT (HFSS)
    # -------------------------------------------------------------
    if nut_data and nut_data.get("has_nutrition_table"):
        story.append(Paragraph("3. Nutritional Proportions & FSSAI HFSS Evaluation", section_title))
        nut_table = [
            [
                Paragraph("<b>Nutrient Metric</b>", cell_bold),
                Paragraph("<b>Extracted Value</b>", cell_bold),
                Paragraph("<b>Govt Threshold</b>", cell_bold),
                Paragraph("<b>Evaluation</b>", cell_bold),
            ]
        ]
        for h in nut_data.get("hfss_flags", []):
            sev_c = "#DC2626" if h["severity"] == "red" else "#D97706" if h["severity"] == "amber" else "#16A34A"
            nut_table.append([
                Paragraph(h["nutrient"], cell_text),
                Paragraph(f"{h['value']} {h['unit']}", cell_bold),
                Paragraph(f"<= {h['threshold']} {h['unit']}/100g", cell_text),
                Paragraph(f"<font color='{sev_c}'><b>{h['status']}</b></font>", cell_text),
            ])
        t_nut = Table(nut_table, colWidths=[50 * mm, 35 * mm, 45 * mm, 50 * mm])
        t_nut.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#065A82")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
            ("PADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(t_nut)
        story.append(Spacer(1, 4 * mm))

    # -------------------------------------------------------------
    # 5. ANNEXURE: STATUTORY SHOW-CAUSE NOTICE (If generated)
    # -------------------------------------------------------------
    if notice_data and notice_data.get("notice_text"):
        story.append(PageBreak())
        story.append(Paragraph("ANNEXURE: STATUTORY SHOW-CAUSE NOTICE", header_style))
        story.append(Paragraph("ISSUED UNDER SECTION 36, LEGAL METROLOGY ACT, 2009", sub_header_style))
        story.append(Spacer(1, 4 * mm))

        notice_lines = notice_data["notice_text"].split("\n")
        formatted_notice = []
        for line in notice_lines:
            if line.startswith("===") or line.startswith("---"):
                continue
            if line.startswith("SUBJECT:") or line.startswith("NOTICE REFERENCE"):
                formatted_notice.append(Paragraph(f"<b>{line}</b>", cell_bold))
            else:
                formatted_notice.append(Paragraph(line, cell_text))
            formatted_notice.append(Spacer(1, 1 * mm))

        story.extend(formatted_notice)

    # Build Document
    doc.build(story)
    return output_path
