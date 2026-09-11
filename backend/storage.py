"""
storage.py
-----------
Unified storage layer for METRO CHECK supporting:
  - SQLite (zero-config local development and offline demo)
  - Supabase PostgreSQL + Cloud Storage bucket (production mode)
  - Users & Authentication
  - Extended inspection records (Metrology, Ingredients, Nutrition, Show-Cause Notices, Complaints)
"""

import os
import json
import sqlite3
import hashlib
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Load .env explicitly from backend directory
_env_path = Path(__file__).parent / ".env"
if _env_path.exists():
    load_dotenv(dotenv_path=_env_path)
else:
    load_dotenv()

STORAGE_MODE = os.getenv("STORAGE_MODE", "local")

LOCAL_DB_FILE = "compliance_local.db"
LOCAL_IMAGE_DIR = Path("uploaded_images")
LOCAL_IMAGE_DIR.mkdir(exist_ok=True)


def hash_password(password: str) -> str:
    """Simple SHA-256 password hash for demo authentication."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


# =====================================================================
# LOCAL SQLITE STORAGE
# =====================================================================
def _local_init():
    conn = sqlite3.connect(LOCAL_DB_FILE)
    cur = conn.cursor()

    # 1. Users Table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password_hash TEXT,
            full_name TEXT,
            role TEXT,
            created_at TEXT
        )
    """)

    # Pre-seed default Inspector account
    demo_user = "inspector@metrocheck.gov.in"
    cur.execute("SELECT id FROM users WHERE username = ?", (demo_user,))
    if not cur.fetchone():
        cur.execute(
            "INSERT INTO users (username, password_hash, full_name, role, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (demo_user, hash_password("admin123"), "Senior Enforcement Officer", "Inspector", datetime.now().isoformat()),
        )

    # 2. Scans Table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS scans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_name TEXT,
            category TEXT,
            scan_time TEXT,
            compliance_score INTEGER,
            decision_status TEXT,
            passed_fields INTEGER,
            total_fields INTEGER,
            details_json TEXT,
            food_safety_json TEXT,
            font_results_json TEXT,
            image_path TEXT,
            annotated_image_path TEXT,
            legal_notice_json TEXT,
            complaint_docket_id TEXT,
            verified_by_inspector INTEGER DEFAULT 0,
            inspector_notes TEXT
        )
    """)

    # Safe migration: ensure new columns exist in existing DB
    existing_cols = [row[1] for row in cur.execute("PRAGMA table_info(scans)").fetchall()]
    columns_to_add = [
        ("category", "TEXT"),
        ("decision_status", "TEXT"),
        ("food_safety_json", "TEXT"),
        ("font_results_json", "TEXT"),
        ("annotated_image_path", "TEXT"),
        ("legal_notice_json", "TEXT"),
        ("complaint_docket_id", "TEXT"),
        ("verified_by_inspector", "INTEGER DEFAULT 0"),
        ("inspector_notes", "TEXT"),
    ]
    for col_name, col_type in columns_to_add:
        if col_name not in existing_cols:
            try:
                cur.execute(f"ALTER TABLE scans ADD COLUMN {col_name} {col_type}")
            except Exception:
                pass

    # 3. Department Complaints Table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS complaints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            docket_id TEXT UNIQUE,
            product_name TEXT,
            company_name TEXT,
            violations_json TEXT,
            filed_at TEXT,
            status TEXT
        )
    """)

    conn.commit()
    conn.close()


def _local_save_scan(product_name, category, result, image_bytes, filename, food_safety=None, notice=None):
    image_path = str(LOCAL_IMAGE_DIR / filename)
    with open(image_path, "wb") as f:
        f.write(image_bytes)

    conn = sqlite3.connect(LOCAL_DB_FILE)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO scans (
            product_name, category, scan_time, compliance_score, decision_status,
            passed_fields, total_fields, details_json, food_safety_json,
            font_results_json, image_path, annotated_image_path, legal_notice_json,
            complaint_docket_id, verified_by_inspector, inspector_notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            product_name,
            category or "Packaged Commodity",
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            result.get("compliance_score", 0),
            result.get("decision", {}).get("status", "NEEDS REVIEW"),
            result.get("passed_fields", 0),
            result.get("total_fields", 0),
            json.dumps(result.get("rule_results", [])),
            json.dumps(food_safety) if food_safety else None,
            json.dumps(result.get("font_results", {})),
            image_path,
            result.get("annotated_image_path"),
            json.dumps(notice) if notice else None,
            None,
            0,
            "",
        ),
    )
    conn.commit()
    scan_id = cur.lastrowid
    conn.close()
    return scan_id


def _local_get_all_scans():
    conn = sqlite3.connect(LOCAL_DB_FILE)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM scans ORDER BY id DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _local_get_scan(scan_id):
    conn = sqlite3.connect(LOCAL_DB_FILE)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM scans WHERE id = ?", (scan_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def _local_update_scan_notice(scan_id, notice_dict):
    conn = sqlite3.connect(LOCAL_DB_FILE)
    conn.execute(
        "UPDATE scans SET legal_notice_json = ? WHERE id = ?",
        (json.dumps(notice_dict), scan_id),
    )
    conn.commit()
    conn.close()


def _local_save_complaint(docket_data):
    conn = sqlite3.connect(LOCAL_DB_FILE)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO complaints (docket_id, product_name, company_name, violations_json, filed_at, status)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            docket_data["docket_id"],
            docket_data["product_name"],
            docket_data["company_name"],
            json.dumps(docket_data.get("violations", [])),
            docket_data["submission_time"],
            docket_data["status"],
        ),
    )
    # Update scans table with docket id if reference is provided
    if docket_data.get("scan_reference_id"):
        cur.execute(
            "UPDATE scans SET complaint_docket_id = ? WHERE id = ?",
            (docket_data["docket_id"], docket_data["scan_reference_id"]),
        )
    conn.commit()
    conn.close()


def _local_get_all_complaints():
    conn = sqlite3.connect(LOCAL_DB_FILE)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM complaints ORDER BY id DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _local_authenticate(username, password):
    conn = sqlite3.connect(LOCAL_DB_FILE)
    conn.row_factory = sqlite3.Row
    hashed = hash_password(password)
    user = conn.execute(
        "SELECT id, username, full_name, role FROM users WHERE username = ? AND password_hash = ?",
        (username, hashed),
    ).fetchone()
    conn.close()
    return dict(user) if user else None


def _local_create_user(username, password, full_name, role="Citizen"):
    conn = sqlite3.connect(LOCAL_DB_FILE)
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO users (username, password_hash, full_name, role, created_at) VALUES (?, ?, ?, ?, ?)",
            (username, hash_password(password), full_name, role, datetime.now().isoformat()),
        )
        conn.commit()
        user_id = cur.lastrowid
        conn.close()
        return {"id": user_id, "username": username, "full_name": full_name, "role": role}
    except sqlite3.IntegrityError:
        conn.close()
        return None


# =====================================================================
# SUPABASE STORAGE WITH GRACEFUL FALLBACK
# =====================================================================
def _get_supabase_client():
    from supabase import create_client
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not url or not key:
        raise ValueError("Supabase URL or Key not set")
    return create_client(url, key)


def _supabase_save_scan(product_name, category, result, image_bytes, filename, food_safety=None, notice=None):
    # Always save locally first so all local files and rich details are cached
    local_id = _local_save_scan(product_name, category, result, image_bytes, filename, food_safety, notice)
    try:
        sb = _get_supabase_client()
        # Upload image to Supabase "labels" bucket
        try:
            sb.storage.from_("labels").upload(filename, image_bytes)
            image_url = sb.storage.from_("labels").get_public_url(filename)
        except Exception as storage_err:
            print(f"[storage] Supabase bucket upload note: {storage_err}")
            image_url = f"/uploaded_images/{filename}"

        row = {
            "product_name": product_name,
            "scan_time": datetime.now().isoformat(),
            "compliance_score": result.get("compliance_score", 0),
            "passed_fields": result.get("passed_fields", 0),
            "total_fields": result.get("total_fields", 0),
            "details_json": json.dumps(result.get("rule_results", [])),
            "image_path": image_url,
        }
        sb.table("scans").insert(row).execute()
        print(f"[storage] Scan synced to Supabase (local id: {local_id}).")
    except Exception as e:
        print(f"[storage] Supabase sync note: {e}")
    return local_id


def _supabase_get_all_scans():
    # Use local SQLite as authoritative source - it has all rich columns
    # (decision_status, food_safety_json, font_results_json, legal_notice_json, etc.)
    # Supabase table only has minimal columns and serves as backup/audit trail only
    return _local_get_all_scans()


def _supabase_get_scan(scan_id):
    # Use local SQLite for full scan detail with all rich columns
    return _local_get_scan(scan_id)


# =====================================================================
# PUBLIC INTERFACE
# =====================================================================
def init_storage():
    _local_init()
    if STORAGE_MODE == "supabase":
        try:
            sb = _get_supabase_client()
            res = sb.table("scans").select("id").limit(1).execute()
            print(f"[storage] Supabase connected successfully to {os.environ.get('SUPABASE_URL')}")
        except Exception as e:
            print(f"[storage] Supabase check notice ({e}), will use hybrid local storage.")


def save_scan(product_name, category, result, image_bytes, filename, food_safety=None, notice=None):
    if STORAGE_MODE == "supabase":
        return _supabase_save_scan(product_name, category, result, image_bytes, filename, food_safety, notice)
    return _local_save_scan(product_name, category, result, image_bytes, filename, food_safety, notice)


def get_all_scans():
    if STORAGE_MODE == "supabase":
        return _supabase_get_all_scans()
    return _local_get_all_scans()


def get_scan(scan_id):
    if STORAGE_MODE == "supabase":
        return _supabase_get_scan(scan_id)
    return _local_get_scan(scan_id)


def update_scan_notice(scan_id, notice_dict):
    _local_update_scan_notice(scan_id, notice_dict)


def save_complaint(docket_data):
    _local_save_complaint(docket_data)


def get_all_complaints():
    return _local_get_all_complaints()


def authenticate_user(username, password):
    return _local_authenticate(username, password)


def register_user(username, password, full_name, role="Citizen"):
    return _local_create_user(username, password, full_name, role)
