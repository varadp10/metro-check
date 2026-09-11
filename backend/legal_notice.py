"""
legal_notice.py
----------------
Generates formal statutory Legal Show-Cause Notices and Department Violation
Dockets for non-compliant packaged commodities and food products.
Cites:
  - The Legal Metrology Act, 2009 (Sections 18, 36)
  - The Legal Metrology (Packaged Commodities) Rules, 2011 (Rules 6, 9)
  - The Food Safety and Standards Act, 2006 (Sections 23, 24)
"""

import uuid
from datetime import datetime, timedelta


def generate_legal_show_cause_notice(product_name, company_name, violations, safety_flags=None):
    """
    Drafts an official Statutory Show-Cause Notice to the manufacturer/packer.
    """
    notice_id = f"MCA/LM-FSSAI/2026/SCN-{uuid.uuid4().hex[:8].upper()}"
    issue_date = datetime.now().strftime("%d-%B-%Y")
    response_deadline = (datetime.now() + timedelta(days=15)).strftime("%d-%B-%Y")
    
    if not company_name or company_name.strip() == "":
        company_name = "The Managing Director / Compliance Officer (Manufacturer / Packer)"
        
    notice_text = f"""================================================================================
GOVERNMENT OF INDIA
MINISTRY OF CONSUMER AFFAIRS, FOOD & PUBLIC DISTRIBUTION
LEGAL METROLOGY & FOOD SAFETY ENFORCEMENT CELL
================================================================================

NOTICE REFERENCE NO: {notice_id}
DATE OF ISSUANCE:    {issue_date}
REPLY DEADLINE:      {response_deadline} (Strict 15 Days from Date of Notice)

TO:
    {company_name}
    SUBJECT COMMODITY: "{product_name}"

SUBJECT: STATUTORY SHOW-CAUSE NOTICE UNDER SECTION 36 OF THE LEGAL METROLOGY 
         ACT, 2009 AND SECTION 23/24 OF THE FOOD SAFETY AND STANDARDS ACT, 2006
--------------------------------------------------------------------------------

WHEREAS, an automated screening and optical character inspection conducted via 
the National Compliance Portal (Metro Check System) on {issue_date} revealed 
grave statutory violations on the packaging and label of the commodity "{product_name}".

SPECIFIC CHARGES AND VIOLATIONS DETECTED:
"""
    
    # 1. Metrology Violations
    idx = 1
    if violations:
        notice_text += "\n[A] INFRACTIONS UNDER LEGAL METROLOGY (PACKAGED COMMODITIES) RULES, 2011:\n"
        for v in violations:
            notice_text += f"   {idx}. Non-compliance with Rule 6: Missing or improper declaration of '{v}'.\n"
            idx += 1
    
    # 2. Food Safety & Health Violations
    if safety_flags and (safety_flags.get("flagged_harmful") or safety_flags.get("has_banned_substance")):
        notice_text += "\n[B] INFRACTIONS UNDER FOOD SAFETY & STANDARDS (PACKAGING & LABELLING) REGULATIONS:\n"
        for item in safety_flags.get("flagged_harmful", []):
            notice_text += f"   {idx}. Presence of restricted/banned substance: '{item['name']}' ({item['risk']}).\n"
            notice_text += f"      Statutory Reason: {item['reason']}\n"
            idx += 1

    notice_text += f"""
STATUTORY WARNING AND LEGAL REPERCUSSIONS:
Take notice that under Section 36(1) of the Legal Metrology Act, 2009:
  - First Violation: Penalty fine extending up to Rs. 25,000/-
  - Second Violation: Penalty fine extending up to Rs. 50,000/-
  - Subsequent Violation: Penalty fine up to Rs. 1,00,000/- or imprisonment 
    for a term which may extend to one year, or both.

Furthermore, under Section 52 of the Food Safety & Standards Act, 2006, distribution 
of misbranded or non-compliant food articles carries a penalty up to Rs. 3,00,000/-.

DIRECTIVE:
You are hereby called upon to:
  1. SHOW CAUSE in writing within 15 days ({response_deadline}) as to why legal 
     prosecution and compounding proceedings should not be instituted against you.
  2. IMMEDIATELY RECTIFY the packaging layout, typography, and mandatory declarations 
     for all subsequent production lots.
  3. Furnish verified packaging specimens to the undersigned enforcement officer.

Failure to respond within the stipulated period will result in ex-parte legal 
action, seizure of non-compliant inventory, and revocation of trade permits.

ISSUED BY:
Enforcement Directorate, Legal Metrology & Standards Division
National Automated Screening Portal (Metro Check)
"""
    return {
        "notice_id": notice_id,
        "issue_date": issue_date,
        "response_deadline": response_deadline,
        "company_name": company_name,
        "product_name": product_name,
        "notice_text": notice_text,
    }


def generate_department_complaint_docket(product_name, company_name, scan_id, violations, health_risk=None):
    """
    Creates an official complaint dossier submitted to the Department of Consumer Affairs / FSSAI.
    """
    docket_id = f"CCPA-NCH-2026-{uuid.uuid4().hex[:6].upper()}"
    submission_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    return {
        "docket_id": docket_id,
        "submission_time": submission_time,
        "target_authority": "Central Consumer Protection Authority (CCPA) & FSSAI Directorate",
        "product_name": product_name,
        "company_name": company_name or "Unknown / Unidentified Manufacturer",
        "scan_reference_id": scan_id,
        "violations": violations,
        "health_risk_level": health_risk or "Standard Non-Compliance",
        "status": "DOCKET LODGED — PENDING INSPECTOR DISPATCH",
        "recommended_action": "Conduct immediate physical retail audit and issue Section 36 summons.",
    }
