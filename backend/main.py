"""
main.py
--------
Production-Ready FastAPI Server for METRO CHECK
(Legal Metrology & FSSAI Food Safety Compliance Screening Platform)
SIH 2026 - Problem Statement SIH26034 | Team Neutral Navigators
"""

import os
import json
import uuid
import tempfile
from typing import List, Optional
from datetime import datetime

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from pathlib import Path
from dotenv import load_dotenv

_backend_dir = Path(__file__).resolve().parent
_env_file = _backend_dir / ".env"
if _env_file.exists():
    load_dotenv(dotenv_path=_env_file)
else:
    load_dotenv()

from compliance_checker import run_full_scan, calculate_decision_status
from ingredient_analyzer import run_full_food_and_ingredient_scan
from legal_notice import generate_legal_show_cause_notice, generate_department_complaint_docket
from ai_extractor import ai_crosscheck, merge_results
from storage import (
    init_storage,
    save_scan,
    get_all_scans,
    get_scan,
    update_scan_notice,
    save_complaint,
    get_all_complaints,
    authenticate_user,
    register_user,
)
from report import generate_pdf_report

app = FastAPI(
    title="Metro Check: Legal Metrology & Food Standards Compliance Engine",
    description="Automated AI-assisted screening system for packaged commodity labels "
                "under the Legal Metrology Act, 2009 and FSSAI Food Safety Regulations.",
    version="2.0.0",
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

init_storage()


# ---------------------------------------------------------------------
# ROOT & STATIC PREVIEW ENDPOINTS
# ---------------------------------------------------------------------
@app.get("/")
def serve_frontend():
    """Serves the web dashboard directly from FastAPI root URL."""
    frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend", "index.html")
    if os.path.exists(frontend_path):
        return FileResponse(frontend_path, media_type="text/html")
    return {"message": "Metro Check API Server is running. Open frontend/index.html in your browser."}

# ---------------------------------------------------------------------
class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    password: str
    full_name: str
    role: Optional[str] = "Citizen"


class NoticeGenerateRequest(BaseModel):
    scan_id: int
    company_name: Optional[str] = None


class ComplaintFileRequest(BaseModel):
    scan_id: int
    company_name: Optional[str] = None
    remarks: Optional[str] = None


# ---------------------------------------------------------------------
# AUTHENTICATION ENDPOINTS
# ---------------------------------------------------------------------
@app.post("/api/auth/login")
def login(creds: LoginRequest):
    user = authenticate_user(creds.username, creds.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password.")
    return {
        "status": "success",
        "user": user,
        "token": f"bearer_{uuid.uuid4().hex}",
    }


@app.post("/api/auth/register")
def register(req: RegisterRequest):
    user = register_user(req.username, req.password, req.full_name, req.role or "Citizen")
    if not user:
        raise HTTPException(status_code=400, detail="Username already registered.")
    return {"status": "success", "user": user}


# ---------------------------------------------------------------------
# HEALTH CHECK
# ---------------------------------------------------------------------
@app.get("/api/health")
def health():
    return {
        "status": "healthy",
        "engine": "Metro Check v2.0",
        "timestamp": datetime.now().isoformat(),
        "storage": os.getenv("STORAGE_MODE", "local"),
    }


# ---------------------------------------------------------------------
# CORE COMPLIANCE SCANNING ENDPOINT
# ---------------------------------------------------------------------
@app.post("/api/scan")
async def scan_product(
    product_name: str = Form(...),
    category: str = Form("Packaged Food"),
    layout_type: str = Form("standard"),
    file: UploadFile = File(...),
):
    """
    Unified compliance analysis:
      1. OCR & Multi-Layout Computer Vision
      2. 7 Legal Metrology Mandatory Declarations
      3. Banned/Harmful Additives & Allergens Screening
      4. FSSAI Nutritional Proportions & HFSS Calculation
      5. Bounding-box visual evidence overlay
      6. Statutory Show-Cause Notice & Decision Status
    """
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Uploaded file must be a valid image.")

    image_bytes = await file.read()
    file_ext = os.path.splitext(file.filename)[1] or ".png"
    unique_filename = f"{uuid.uuid4().hex}{file_ext}"

    # Write temporarily to disk for OpenCV/Tesseract processing
    with tempfile.NamedTemporaryFile(suffix=file_ext, delete=False) as tmp:
        tmp.write(image_bytes)
        tmp_path = tmp.name

    try:
        scan_res = run_full_scan(tmp_path, layout_type=layout_type, save_annotated=True)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    # 1. Food Safety & Ingredient Analysis
    food_safety_res = run_full_food_and_ingredient_scan(scan_res["raw_text"])
    scan_res["food_safety"] = food_safety_res

    # 2. AI / Semantic Cross-Check
    ai_verdict = ai_crosscheck(scan_res["raw_text"])
    scan_res["rule_results"] = merge_results(scan_res["rule_results"], ai_verdict)
    
    # Recalculate passed fields & 3-tier decision
    scan_res["passed_fields"] = sum(1 for r in scan_res["rule_results"] if r["found"])
    scan_res["compliance_score"] = round(100 * scan_res["passed_fields"] / scan_res["total_fields"])
    scan_res["decision"] = calculate_decision_status(
        scan_res["rule_results"], scan_res["font_results"], scan_res["decision"]["ocr_confidence"]
    )

    # 3. Detect Violations & Auto-Draft Show-Cause Notice if non-compliant
    violations = [r["field"] for r in scan_res["rule_results"] if not r["found"]]
    if scan_res["font_results"].get("total_flagged", 0) > 5:
        violations.append("Rule 9: Minimum Font Size Violation")

    # Extract detected company name from manufacturer field if available
    extracted_company = None
    for r in scan_res["rule_results"]:
        if "Manufacturer" in r["field"] and r["found"] and r["matched_text"]:
            extracted_company = r["matched_text"]
            break

    notice_data = None
    if scan_res["decision"]["status"] != "COMPLIANT" or food_safety_res["ingredients"].get("has_banned_substance"):
        notice_data = generate_legal_show_cause_notice(
            product_name, extracted_company, violations, food_safety_res["ingredients"]
        )

    # 4. Save to Database
    scan_id = save_scan(
        product_name=product_name,
        category=category,
        result=scan_res,
        image_bytes=image_bytes,
        filename=unique_filename,
        food_safety=food_safety_res,
        notice=notice_data,
    )

    return {
        "scan_id": scan_id,
        "product_name": product_name,
        "category": category,
        "decision": scan_res["decision"],
        "compliance_score": scan_res["compliance_score"],
        "passed_fields": scan_res["passed_fields"],
        "total_fields": scan_res["total_fields"],
        "rule_results": scan_res["rule_results"],
        "font_results": scan_res["font_results"],
        "food_safety": food_safety_res,
        "legal_notice": notice_data,
        "raw_text": scan_res["raw_text"],
        "annotated_preview_b64": scan_res["annotated_preview_b64"],
    }


# ---------------------------------------------------------------------
# BATCH SCANNING ENDPOINT
# ---------------------------------------------------------------------
@app.post("/api/scan/batch")
async def batch_scan(files: List[UploadFile] = File(...)):
    """
    Process multiple commodity label images in one batch.
    """
    batch_results = []
    for file in files:
        if not file.content_type.startswith("image/"):
            continue

        prod_name = os.path.splitext(file.filename)[0].replace("_", " ").title()
        image_bytes = await file.read()
        file_ext = os.path.splitext(file.filename)[1] or ".png"
        unique_filename = f"{uuid.uuid4().hex}{file_ext}"

        with tempfile.NamedTemporaryFile(suffix=file_ext, delete=False) as tmp:
            tmp.write(image_bytes)
            tmp_path = tmp.name

        try:
            res = run_full_scan(tmp_path, layout_type="standard", save_annotated=False)
            food_safety = run_full_food_and_ingredient_scan(res["raw_text"])
            res["food_safety"] = food_safety
            
            scan_id = save_scan(prod_name, "Packaged Commodity", res, image_bytes, unique_filename, food_safety)
            
            batch_results.append({
                "scan_id": scan_id,
                "filename": file.filename,
                "product_name": prod_name,
                "compliance_score": res["compliance_score"],
                "status": res["decision"]["status"],
                "passed_fields": f"{res['passed_fields']}/{res['total_fields']}",
                "food_safety_score": food_safety["food_safety_score"],
                "harmful_count": len(food_safety["ingredients"].get("flagged_harmful", [])),
            })
        except Exception as e:
            batch_results.append({
                "filename": file.filename,
                "product_name": prod_name,
                "error": str(e),
                "status": "ERROR",
            })
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    return {"total_scanned": len(batch_results), "results": batch_results}


# ---------------------------------------------------------------------
# STATUTORY SHOW-CAUSE NOTICE & COMPLAINT FILING ENDPOINTS
# ---------------------------------------------------------------------
@app.post("/api/notice/generate")
def create_notice(req: NoticeGenerateRequest):
    scan = get_scan(req.scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found.")

    details_json = scan.get("details_json") or "[]"
    rules = json.loads(details_json)
    violations = [r["field"] for r in rules if not r.get("found")]
    food_data = json.loads(scan["food_safety_json"]) if scan.get("food_safety_json") else {}

    notice = generate_legal_show_cause_notice(
        scan["product_name"],
        req.company_name,
        violations,
        food_data.get("ingredients"),
    )
    update_scan_notice(req.scan_id, notice)
    return notice


@app.post("/api/complaint/file")
def file_department_complaint(req: ComplaintFileRequest):
    scan = get_scan(req.scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan record not found.")

    details_json = scan.get("details_json") or "[]"
    rules = json.loads(details_json)
    violations = [r["field"] for r in rules if not r.get("found")]
    food_data = json.loads(scan["food_safety_json"]) if scan.get("food_safety_json") else {}
    harmful = food_data.get("ingredients", {}).get("flagged_harmful", [])

    docket = generate_department_complaint_docket(
        product_name=scan["product_name"],
        company_name=req.company_name,
        scan_id=req.scan_id,
        violations=violations,
        health_risk=f"{len(harmful)} harmful substances flagged" if harmful else "Legal Metrology Violations",
    )
    save_complaint(docket)
    return {
        "status": "success",
        "message": "Statutory complaint docket filed with Department of Consumer Affairs / FSSAI.",
        "docket": docket,
    }



@app.get("/api/complaints")
def list_complaints():
    return get_all_complaints()


# ---------------------------------------------------------------------
# REGULATIONS & LEGAL NORMS GUIDE ENDPOINT
# ---------------------------------------------------------------------
@app.get("/api/regulations")
def get_regulations():
    return {
        "title": "National Packaged Commodity Regulatory Framework",
        "acts": [
            {
                "name": "Legal Metrology Act, 2009 & Packaged Commodities Rules, 2011",
                "rules": [
                    {
                        "rule": "Rule 6(1)(a) & (b)",
                        "title": "Manufacturer, Packer & Importer Declaration",
                        "mandate": "Every package must bear the full name and complete address of the manufacturer, packer, or importer.",
                        "penalty": "Section 36(1): Fine up to ₹25,000 (1st offence), ₹50,000 (2nd offence), up to ₹1,00,000 and/or 1 year imprisonment.",
                    },
                    {
                        "rule": "Rule 6(1)(c)",
                        "title": "Month and Year of Manufacture / Packing",
                        "mandate": "Prominent statement of Month and Year in which the commodity is manufactured or pre-packed.",
                        "penalty": "Compounding or court prosecution under Section 36.",
                    },
                    {
                        "rule": "Rule 6(1)(d)",
                        "title": "Net Quantity in Standard SI Units",
                        "mandate": "Net quantity shall be declared in standard metric units: g, kg, ml, l, or count. Non-standard symbols are prohibited.",
                        "penalty": "Penalty for short weight/measurement under Section 30 & 36.",
                    },
                    {
                        "rule": "Rule 6(1)(e)",
                        "title": "Maximum Retail Price (MRP)",
                        "mandate": "MRP must be clearly printed inclusive of all taxes ('MRP Rs. XX.XX incl. of all taxes'). Charging above MRP is a punishable offence.",
                        "penalty": "Fine up to ₹50,000 for overcharging; invalid declaration under Section 36.",
                    },
                    {
                        "rule": "Rule 6(1)(11)",
                        "title": "Unit Sale Price (USP)",
                        "mandate": "Mandatory declaration of price per gram/kg/ml/liter/unit for consumer price comparison.",
                        "penalty": "Statutory notice and fines under 2021/2022 amendments.",
                    },
                    {
                        "rule": "Rule 6(1)(f)",
                        "title": "Consumer Care & Grievance Redressal",
                        "mandate": "Name, address, telephone number, and email of person or officer who can be contacted for consumer grievances.",
                        "penalty": "Non-compliance penalty under Section 36.",
                    },
                    {
                        "rule": "Rule 6(10)",
                        "title": "Country of Origin",
                        "mandate": "Mandatory declaration of country of origin on all packages manufactured or imported.",
                        "penalty": "Mandatory seizure and penalty under Department of Consumer Affairs guidelines.",
                    },
                    {
                        "rule": "Rule 9 (Table 1)",
                        "title": "Minimum Height of Numerals & Letters",
                        "mandate": "Minimum font height ranges from 1.0mm to 6.0mm depending on package net quantity and principal display panel area.",
                        "penalty": "Illegible / deceptive declaration violation.",
                    },
                ],
            },
            {
                "name": "FSSAI Packaging & Labelling Regulations, 2020",
                "rules": [
                    {
                        "rule": "Regulation 5(1)",
                        "title": "Nutritional Information & HFSS Proportions",
                        "mandate": "Mandatory per 100g or per serving declaration of Energy, Protein, Carbohydrates, Total Sugars, Added Sugars, Saturated Fat, Trans Fat, and Sodium.",
                        "penalty": "Section 52: Penalty for misbranded food up to ₹3,00,000.",
                    },
                    {
                        "rule": "Regulation 5(2)",
                        "title": "Harmful Additives & Prohibited Ingredients",
                        "mandate": "Zero tolerance for banned additives such as Potassium Bromate, Potassium Iodate, and unapproved synthetic colors.",
                        "penalty": "Section 59: Penalty for unsafe food with imprisonment up to 7 years and fine up to ₹10,00,000.",
                    },
                    {
                        "rule": "Regulation 5(3)",
                        "title": "Mandatory Allergen Declaration",
                        "mandate": "Clear declaration of allergens: Cereals containing gluten, Crustaceans, Eggs, Fish, Peanuts, Soybeans, Milk, and Tree nuts.",
                        "penalty": "Section 55: Penalty for failure to comply with Food Safety Officer directions.",
                    },
                ],
            },
        ],
    }


# ---------------------------------------------------------------------
# DASHBOARD, STATS & HISTORY ENDPOINTS
# ---------------------------------------------------------------------
@app.get("/api/history")
def history():
    return get_all_scans()


@app.get("/api/stats")
def get_dashboard_stats():
    scans = get_all_scans()
    if not scans:
        return {
            "total_scans": 0,
            "compliant_count": 0,
            "needs_review_count": 0,
            "non_compliant_count": 0,
            "average_score": 0,
            "rule_violations": {},
            "complaints_lodged": len(get_all_complaints()),
        }

    compliant = 0
    needs_review = 0
    non_compliant = 0
    total_score = 0
    rule_violations = {}

    for s in scans:
        total_score += s.get("compliance_score", 0)
        status = s.get("decision_status", "")
        if status == "COMPLIANT":
            compliant += 1
        elif status == "NEEDS REVIEW":
            needs_review += 1
        else:
            non_compliant += 1

        try:
            details = json.loads(s.get("details_json", "[]"))
            for r in details:
                if not r.get("found"):
                    field = r.get("field", "Unknown")
                    rule_violations[field] = rule_violations.get(field, 0) + 1
        except Exception:
            pass

    return {
        "total_scans": len(scans),
        "compliant_count": compliant,
        "needs_review_count": needs_review,
        "non_compliant_count": non_compliant,
        "average_score": round(total_score / len(scans)),
        "rule_violations": rule_violations,
        "complaints_lodged": len(get_all_complaints()),
    }


@app.get("/api/scan/{scan_id}")
def scan_detail(scan_id: int):
    scan = get_scan(scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan record not found.")
    return scan


# ---------------------------------------------------------------------
# PDF REPORT & NOTICE DOWNLOAD ENDPOINTS
# ---------------------------------------------------------------------
@app.get("/api/report/{scan_id}")
def download_report(scan_id: int):
    scan = get_scan(scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan record not found.")

    food_safety = json.loads(scan["food_safety_json"]) if scan.get("food_safety_json") else None
    notice_data = json.loads(scan["legal_notice_json"]) if scan.get("legal_notice_json") else None
    font_results = json.loads(scan["font_results_json"]) if scan.get("font_results_json") else {"flagged_words": []}

    result = {
        "rule_results": json.loads(scan["details_json"]),
        "compliance_score": scan["compliance_score"],
        "passed_fields": scan["passed_fields"],
        "total_fields": scan["total_fields"],
        "decision": {"status": scan.get("decision_status", "NEEDS REVIEW")},
        "food_safety": food_safety,
        "font_results": font_results,
    }

    pdf_filename = f"Inspection_Report_{scan_id}.pdf"
    generate_pdf_report(
        scan["product_name"], result, output_path=pdf_filename, notice_data=notice_data
    )
    return FileResponse(pdf_filename, media_type="application/pdf", filename=pdf_filename)
