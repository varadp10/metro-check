# ⚖️ METRO CHECK — National Legal Metrology & Food Safety Screening Platform
> **Smart India Hackathon 2026** | **Problem Statement:** SIH26034  
> **Team:** Neutral Navigators | **Category:** Software / Legal Metrology & Food Safety

---

## 📌 Problem Statement Overview
Under the **Legal Metrology (Packaged Commodities) Rules, 2011**, all pre-packaged commodities sold in India must contain specific mandatory declarations (e.g. MRP, Net Quantity, Unit Sale Price, Manufacturer Details, Packing Date, Consumer Grievance Cell, and Country of Origin). 

Currently, market surveillance and enforcement officers manually inspect labels in retail markets — an error-prone, subjective, and slow process. **METRO CHECK** automates this by combining Computer Vision (OpenCV + Tesseract OCR), Rule-Based Legal Evaluation, FSSAI Food Additive Screening, and AI-assisted cross-verification.

---

## 🚀 Key Features

1. **7 Mandatory Legal Metrology Declarations Checked:**
   - Maximum Retail Price (MRP) with tax inclusions
   - Net Quantity in standardized SI metric units
   - Unit Sale Price (USP) per gram / ml / piece
   - Manufacturer / Packer / Importer name and complete address
   - Month & Year of Manufacture / Packing
   - Consumer Care Helpline & Grievance Contact
   - Country of Origin

2. **Computer Vision & Visual Evidence:**
   - Multi-layout preprocessing (standard box, flexible pouch with anti-glare, cylindrical bottle/can)
   - Real-time word coordinate extraction and bounding box overlays
   - Rule 9 font height & numeral readability check

3. **FSSAI Food Safety & Harmful Substance Screening:**
   - Scans ingredient lists against prohibited/hazardous substances (e.g., Potassium Bromate, Titanium Dioxide E171, Trans Fats, Azodicarbonamide)
   - Allergen detection across 8 major allergen classes
   - High Fat, Sugar, Salt (HFSS) nutritional threshold evaluation

4. **Official Statutory Show-Cause Notices & Complaints:**
   - Auto-generates statutory Show-Cause Notices under Section 36 of the Legal Metrology Act, 2009
   - Auto-generates Department Complaint Dockets with unique tracking IDs

5. **Official Inspection PDF Certificates:**
   - Multi-page PDF report generation with audit checklists, risk summaries, and statutory notice annexures

6. **Batch / High-Volume Processing:**
   - Upload up to 50 label images simultaneously for market raid operations with CSV export

7. **Zero-Failure Hybrid Architecture:**
   - Works 100% offline with local SQLite + local Tesseract OCR
   - Seamlessly syncs to Supabase Cloud PostgreSQL & Storage when internet is available

---

## 🛠️ Technology Stack

| Layer | Technology |
|---|---|
| **Frontend** | HTML5, Tailwind CSS, Chart.js, Lucide Icons |
| **Backend API** | Python 3.10+, FastAPI, Uvicorn |
| **OCR & Computer Vision** | Tesseract OCR, OpenCV (`cv2`), NumPy, Pillow |
| **PDF Generation** | ReportLab |
| **Database & Cloud Storage** | SQLite (Local) + Supabase (PostgreSQL & Object Storage) |
| **AI Cross-Verification** | Anthropic Claude API (with offline regex NLP fallback) |

---

## 💻 Quickstart / Running Locally

### 1. Prerequisites
- Python 3.10+
- [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki) installed on your system (Default path on Windows: `C:\Program Files\Tesseract-OCR\tesseract.exe`)

### 2. Clone the Repository
```bash
git clone https://github.com/varadp10/metro-check.git
cd metro-check
```

### 3. Install Dependencies
```bash
cd backend
pip install -r requirements.txt
```

### 4. Configure Environment (Optional)
```bash
cp .env.example .env
# Edit .env with Supabase or Anthropic keys if cloud features are desired
```

### 5. Start the Server
```bash
uvicorn main:app --reload
```
Open your browser at: **`http://127.0.0.1:8000`**

---

## 📂 Project Structure

```
metro-check/
├── backend/
│   ├── main.py                  # FastAPI server & route handlers
│   ├── compliance_checker.py    # Computer vision, OCR & 7 Legal Metrology rules
│   ├── ingredient_analyzer.py   # FSSAI harmful additives, allergens & HFSS logic
│   ├── legal_notice.py          # Statutory show-cause notice & docket generator
│   ├── ai_extractor.py          # Claude AI semantic cross-check & local NLP fallback
│   ├── storage.py               # Hybrid SQLite + Supabase storage layer
│   ├── report.py                # Multi-page ReportLab PDF generator
│   ├── requirements.txt         # Python dependencies
│   ├── .env.example             # Example environment configuration
│   └── example_labels/          # Test label images for demo
├── frontend/
│   └── index.html               # Responsive portal UI (Tailwind CSS SPA)
├── supabase/
│   └── schema.sql               # Supabase PostgreSQL database schema
├── vercel.json                  # Vercel deployment configuration
└── README.md
```

---

## ⚖️ Regulatory Compliance Standards Followed
- **Legal Metrology Act, 2009** (Act No. 1 of 2010)
- **Legal Metrology (Packaged Commodities) Rules, 2011** (G.S.R. 202(E) as amended)
- **FSSAI (Packaging and Labelling) Regulations, 2020**

---

## 👥 Team Neutral Navigators (SIH 2026)
Developed for Smart India Hackathon 2026.
