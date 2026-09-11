"""
compliance_checker.py
----------------------
The core computer vision & Legal Metrology rule engine for METRO CHECK.

Performs:
  1. Multi-layout image preprocessing (deskewing, adaptive thresholding,
     contrast normalization for boxes, pouches, bottles, and cans).
  2. OCR text extraction with word coordinates & confidence scores via Tesseract.
  3. Pattern matching against the 7 mandatory Legal Metrology (Packaged Commodities)
     Rules, 2011 declarations.
  4. Font size readability analysis (Rule 9 minimum height evaluation).
  5. Visual Evidence Bounding-Box generation & annotation overlay.
  6. 3-Tier Status calculation (COMPLIANT, NEEDS REVIEW, POTENTIAL NON-COMPLIANCE).
"""

import os
import re
import cv2
import base64
import numpy as np
import pytesseract
from pathlib import Path

# Configure Tesseract path if present on Windows
TESSERACT_EXE = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
if os.path.exists(TESSERACT_EXE):
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_EXE


# ---------------------------------------------------------------
# 1. THE 7 MANDATORY LEGAL METROLOGY DECLARATIONS
# ---------------------------------------------------------------
RULES = {
    "MRP (Maximum Retail Price)": {
        "rule_ref": "Rule 6(1)(e)",
        "pattern": r"(?:mrp|m\.r\.p|maximum\s+retail\s+price)[^a-z0-9]{0,15}(?:rs\.?|₹|inr)?\s*\d+(?:\.\d{1,2})?",
        "critical": True,
        "description": "Maximum Retail Price inclusive of all taxes.",
    },
    "Net Quantity": {
        "rule_ref": "Rule 6(1)(d)",
        "pattern": r"(?:net\s*(?:qty|quantity|wt|weight|vol|volume)?\s*[:=\-]?\s*)?\d+(?:\.\d+)?\s*(?:g|gm|gms|kg|ml|l|litre|liter|cm|m|meter|pieces?|units?|n)\b",
        "critical": True,
        "description": "Net quantity in standard SI metric units (weight, volume, or count).",
    },
    "Unit Sale Price (USP)": {
        "rule_ref": "Rule 6(1)(11)",
        "pattern": r"(?:usp|lsp|unit\s+sale\s+price|unit\s+price|price\s+per)[^a-z0-9]{0,15}(?:rs\.?|₹|inr)?\s*\d+(?:\.\d+)?\s*(?:/|per)\s*(?:g|gm|kg|ml|l|unit|piece|n)\b|(?:rs\.?|₹|inr)?\s*\d+(?:\.\d+)?\s*(?:/|per)\s*(?:g|gm|kg|ml|l|unit|piece|n)\b",
        "critical": False,
        "description": "Price per unit (per gram, ml, or piece) for consumer transparency.",
    },
    "Manufacturer / Packer / Importer Details": {
        "rule_ref": "Rule 6(1)(a) & (b)",
        "pattern": r"(?:mfd|manufactured|manutactuted|marketed|packed|imported|processed)\s*(?:by|for)?\s*[:\-]?\s*[a-zA-Z0-9\s,.\-&]+(?:ltd|lid|limited|industries|foods|corp|co|works|plot|road|street|estate|nagar|dist|pin|india)",
        "critical": True,
        "description": "Name and complete address of the manufacturer, packer, or importer.",
    },
    "Month & Year of Packing/Import": {
        "rule_ref": "Rule 6(1)(c)",
        "pattern": r"(?:mfg|mfd|packed|pkd|pko|pkg|packing|import|use\s*by|best\s*before|expiry|exp|date)[^a-z0-9]{0,15}(?:0[1-9]|1[0-2]|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s*[/:\-.,\s]\s*(?:20\d{2}|\d{2})",
        "critical": True,
        "description": "Date, month, and year of manufacture, packing, or import.",
    },
    "Consumer Care Details": {
        "rule_ref": "Rule 6(1)(f)",
        "pattern": r"(?:customer|consumer|consumer\s*cell|helpline|helping|toll\s*free|care\s*executive|grievance|feedback)[^a-z0-9]{0,25}(?:\d{3,5}[-\s]?\d{3,4}[-\s]?\d{3,4}|[\w.+-]+@[\w-]+\.[\w.-]+)|(?:\d{4}[-\s]?\d{3}[-\s]?\d{4})|([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)",
        "critical": False,
        "description": "Name, contact address, helpline number, and email of consumer grievance cell.",
    },
    "Country of Origin": {
        "rule_ref": "Rule 6(10)",
        "pattern": r"(?:country\s+of\s+origin|made\s+in|product\s+of)\s*[:\-]?\s*(?:india|bharat|ingia|[a-zA-Z]+)",
        "critical": False,
        "description": "Clear declaration of country of origin for all manufactured and imported goods.",
    },
}


# ---------------------------------------------------------------
# 2. MULTI-LAYOUT IMAGE PREPROCESSING
# ---------------------------------------------------------------
def preprocess_image_multilayout(image_path, layout_type="standard"):
    """
    Advanced OpenCV preprocessing tailored for different packaging formats:
      - 'standard' / 'box': Flat cardboard box or rectangular container
      - 'pouch': Flexible foil or plastic pouch (specular reflections, folds)
      - 'bottle_can': Cylindrical curved surfaces
    """
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f"Could not read image from {image_path}")

    # Resize if excessively large to balance OCR speed and accuracy
    h, w = img.shape[:2]
    if max(h, w) > 2000:
        scale = 2000.0 / max(h, w)
        img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    if layout_type == "pouch":
        # Apply CLAHE (Contrast Limited Adaptive Histogram Equalization)
        # to normalize lighting reflections on glossy pouches
        clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
        contrast = clahe.apply(gray)
        # Bilateral filter to reduce plastic crinkle noise while preserving text edges
        filtered = cv2.bilateralFilter(contrast, 9, 75, 75)
        thresh = cv2.adaptiveThreshold(
            filtered, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 15, 8
        )
    elif layout_type == "bottle_can":
        # Normalization for curved surfaces
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        contrast = clahe.apply(gray)
        _, thresh = cv2.threshold(contrast, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    else:
        # Standard flat box
        blurred = cv2.GaussianBlur(gray, (3, 3), 0)
        _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    return img, thresh


# ---------------------------------------------------------------
# 3. OCR EXTRACTION & WORD BOUNDING BOX DATA
# ---------------------------------------------------------------
def extract_ocr_data(processed_image):
    """
    Extracts text along with bounding box coordinates and confidence levels.
    """
    data = pytesseract.image_to_data(processed_image, output_type=pytesseract.Output.DICT)
    return data


def assemble_full_text(data):
    """
    Combines detected words into clean readable text blocks.
    """
    words = []
    total_conf = 0
    valid_words = 0
    
    for i in range(len(data["text"])):
        w = data["text"][i].strip()
        conf = int(data["conf"][i])
        if w:
            words.append(w)
            if conf > 0:
                total_conf += conf
                valid_words += 1

    full_text = " ".join(words)
    avg_conf = round(total_conf / valid_words, 1) if valid_words > 0 else 0
    return full_text, avg_conf


# ---------------------------------------------------------------
# 4. RULE ENGINE & BOUNDING BOX MATCHING
# ---------------------------------------------------------------
def check_metrology_rules(text):
    """
    Checks the 7 Legal Metrology declarations against the extracted text.
    """
    text_lower = text.lower()
    results = []
    
    for field, info in RULES.items():
        match = re.search(info["pattern"], text_lower, re.IGNORECASE)
        results.append({
            "field": field,
            "rule_ref": info["rule_ref"],
            "critical": info["critical"],
            "description": info["description"],
            "found": match is not None,
            "matched_text": match.group(0).strip() if match else None,
        })
    return results


def check_font_sizes(data, min_ratio=0.30):
    """
    Checks whether declaration words are excessively small relative to the largest text.
    """
    heights = [int(h) for h, t in zip(data["height"], data["text"]) if t.strip() != ""]
    if not heights:
        return {"max_height": 0, "flagged_words": [], "font_compliant": True}

    max_height = max(heights)
    flagged = []
    for i, t in enumerate(data["text"]):
        word = t.strip()
        if not word or len(word) < 2:
            continue
        h = int(data["height"][i])
        # Words smaller than 30% of max height are flagged for potential legibility issues
        if h < min_ratio * max_height and h < 14:
            flagged.append({"word": word, "height_px": h})

    font_compliant = len(flagged) <= 5
    return {
        "max_height": max_height,
        "flagged_words": flagged[:12],  # keep top 12
        "total_flagged": len(flagged),
        "font_compliant": font_compliant,
    }


# ---------------------------------------------------------------
# 5. VISUAL COMPUTER VISION BOUNDING-BOX ANNOTATION
# ---------------------------------------------------------------
def annotate_evidence_image(original_img, ocr_data, rule_results, output_path=None):
    """
    Draws highlighted bounding boxes onto the product label image:
      - 🟢 Green: Matched mandatory Legal Metrology declaration words
      - 🟡 Amber: Moderate confidence / potential information words
      - 🔵 Blue: Text boundary boxes
    Returns the annotated image in base64 format for instant UI preview.
    """
    annotated = original_img.copy()
    h_img, w_img = annotated.shape[:2]

    matched_keywords = set()
    for r in rule_results:
        if r["found"] and r["matched_text"]:
            words = re.findall(r"\b\w+\b", r["matched_text"].lower())
            matched_keywords.update(words)

    bounding_boxes = []

    for i in range(len(ocr_data["text"])):
        word = ocr_data["text"][i].strip()
        if not word:
            continue

        x = int(ocr_data["left"][i])
        y = int(ocr_data["top"][i])
        w = int(ocr_data["width"][i])
        h = int(ocr_data["height"][i])
        conf = int(ocr_data["conf"][i])

        is_matched = word.lower() in matched_keywords
        
        # Determine box color: BGR format
        if is_matched:
            color = (0, 200, 50)  # Bright Green
            thickness = 2
            label_type = "MANDATORY_DECLARATION"
        elif conf > 75:
            color = (220, 150, 20)  # Cyan/Blue
            thickness = 1
            label_type = "TEXT_BLOCK"
        else:
            color = (30, 160, 240)  # Amber
            thickness = 1
            label_type = "LOW_CONFIDENCE"

        cv2.rectangle(annotated, (x, y), (x + w, y + h), color, thickness)
        
        bounding_boxes.append({
            "word": word,
            "x": x, "y": y, "w": w, "h": h,
            "conf": conf,
            "type": label_type,
        })

    # Save to disk if output path is provided
    if output_path:
        cv2.imwrite(output_path, annotated)

    # Encode to base64 for direct browser transmission
    _, buffer = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 85])
    b64_image = base64.b64encode(buffer).decode("utf-8")
    b64_data_uri = f"data:image/jpeg;base64,{b64_image}"

    return b64_data_uri, bounding_boxes


# ---------------------------------------------------------------
# 6. 3-TIER DECISION ENGINE
# ---------------------------------------------------------------
def calculate_decision_status(rule_results, font_results, avg_conf):
    """
    Computes the 3-Tier Status matching SIH presentation guidelines:
      - COMPLIANT
      - NEEDS REVIEW
      - POTENTIAL NON-COMPLIANCE
    """
    total = len(rule_results)
    passed = sum(1 for r in rule_results if r["found"])
    compliance_score = round(100 * passed / total)

    critical_rules = [r for r in rule_results if r["critical"]]
    critical_passed = sum(1 for r in critical_rules if r["found"])
    all_critical_pass = (critical_passed == len(critical_rules))

    if compliance_score >= 85 and all_critical_pass and font_results.get("font_compliant", True):
        status = "COMPLIANT"
        status_color = "green"
        summary = "Label complies with mandatory Legal Metrology (Packaged Commodities) Rules, 2011."
    elif compliance_score >= 55 and critical_passed >= 3:
        status = "NEEDS REVIEW"
        status_color = "amber"
        summary = "Minor omissions, legibility warnings, or ambiguous declarations detected. Human inspector verification recommended."
    else:
        status = "POTENTIAL NON-COMPLIANCE"
        status_color = "red"
        summary = "Critical mandatory declarations missing or illegible. Subject to statutory notice under Section 36."

    return {
        "status": status,
        "status_color": status_color,
        "compliance_score": compliance_score,
        "passed_fields": passed,
        "total_fields": total,
        "summary": summary,
        "ocr_confidence": avg_conf,
    }


# ---------------------------------------------------------------
# 7. UNIFIED PIPELINE EXECUTION
# ---------------------------------------------------------------
def run_full_scan(image_path, layout_type="standard", save_annotated=True):
    """
    End-to-end execution of the scanning & verification pipeline.
    """
    orig_img, processed_img = preprocess_image_multilayout(image_path, layout_type)
    ocr_data = extract_ocr_data(processed_img)
    raw_text, avg_conf = assemble_full_text(ocr_data)
    rule_results = check_metrology_rules(raw_text)
    font_results = check_font_sizes(ocr_data)
    decision = calculate_decision_status(rule_results, font_results, avg_conf)

    annotated_path = None
    if save_annotated:
        p = Path(image_path)
        annotated_path = str(p.parent / f"annotated_{p.name}")

    b64_preview, bounding_boxes = annotate_evidence_image(
        orig_img, ocr_data, rule_results, output_path=annotated_path
    )

    return {
        "raw_text": raw_text,
        "rule_results": rule_results,
        "font_results": font_results,
        "decision": decision,
        "compliance_score": decision["compliance_score"],
        "passed_fields": decision["passed_fields"],
        "total_fields": decision["total_fields"],
        "annotated_preview_b64": b64_data_uri_if_needed(b64_preview),
        "annotated_image_path": annotated_path,
        "bounding_boxes_count": len(bounding_boxes),
    }


def b64_data_uri_if_needed(val):
    return val
