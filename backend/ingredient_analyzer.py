"""
ingredient_analyzer.py
-----------------------
Analyzes food and product labels for:
  1. Harmful, banned, or hazardous additives and chemicals according to
     FSSAI (Food Safety and Standards Authority of India) and international health bodies.
  2. Common allergens requiring mandatory statutory declarations.
  3. Nutritional facts extraction (Calories, Sugars, Saturated Fat, Trans Fat, Sodium, Protein).
  4. Proportion check against Govt RDA standards and FSSAI HFSS (High in Fat, Sugar, and Salt) regulations.
"""

import re

# ---------------------------------------------------------------------
# 1. HARMFUL & BANNED INGREDIENTS / ADDITIVES DATABASE
# ---------------------------------------------------------------------
# Each entry includes:
# - name: ingredient name
# - risk: 'BANNED', 'HIGH_RISK', or 'MODERATE_RISK'
# - reason: regulatory/health justification
# - keywords: regex patterns to match
HARMFUL_INGREDIENTS_DB = [
    {
        "name": "Potassium Bromate",
        "risk": "BANNED",
        "category": "Banned Flour Treatment Agent",
        "reason": "Class 2B possible carcinogen; strictly banned in India by FSSAI since 2016 for bakery and flour products.",
        "patterns": [r"potassium\s+bromate", r"kbro3", r"e924a"],
    },
    {
        "name": "Potassium Iodate",
        "risk": "BANNED",
        "category": "Banned Bread Additive",
        "reason": "Prohibited by FSSAI as a bread improver due to risk of thyroid dysfunction and thyroid malignancies.",
        "patterns": [r"potassium\s+iodate", r"kio3", r"e917"],
    },
    {
        "name": "Titanium Dioxide (E171)",
        "risk": "HIGH_RISK",
        "category": "Restricted Food Whitener",
        "reason": "Banned in the European Union (EU) and flagged by global agencies as genotoxic (causes DNA damage).",
        "patterns": [r"titanium\s+dioxide", r"\be\s?171\b", r"\bins\s?171\b", r"ci\s?77891"],
    },
    {
        "name": "Azodicarbonamide (ADA)",
        "risk": "BANNED",
        "category": "Banned Bleaching / Foaming Agent",
        "reason": "Banned in multiple countries and heavily restricted; breaks down into semicarbazide and urethane when baked.",
        "patterns": [r"azodicarbonamide", r"\be\s?927\b", r"\bins\s?927\b"],
    },
    {
        "name": "Partially Hydrogenated Oils (Artificial Trans Fat)",
        "risk": "HIGH_RISK",
        "category": "Harmful Lipid / Trans Fat",
        "reason": "FSSAI limits trans fats to under 2% of total fat. Partially hydrogenated oils increase LDL cholesterol and risk of cardiovascular disease.",
        "patterns": [
            r"partially\s+hydrogenated\s+(?:oil|vegetable|fat)",
            r"hydrogenated\s+vegetable\s+oil",
            r"vanaspati\b",
        ],
    },
    {
        "name": "BHA / BHT (Synthetic Antioxidants)",
        "risk": "MODERATE_RISK",
        "category": "Preservative with Toxicity Concerns",
        "reason": "Butylated hydroxyanisole (BHA) & Butylated hydroxytoluene (BHT) are restricted to 200 ppm by FSSAI; suspected endocrine disruptors.",
        "patterns": [
            r"\bbha\b",
            r"\bbht\b",
            r"butylated\s+hydroxyanisole",
            r"butylated\s+hydroxytoluene",
            r"\be\s?320\b",
            r"\be\s?321\b",
            r"\bins\s?320\b",
            r"\bins\s?321\b",
        ],
    },
    {
        "name": "Synthetic Artificial Dyes (Tartrazine / Sunset Yellow / Allura Red)",
        "risk": "MODERATE_RISK",
        "category": "Restricted Synthetic Colors",
        "reason": "FSSAI mandates statutory warning: 'May have an adverse effect on activity and attention in children' when synthetic food colors are used.",
        "patterns": [
            r"tartrazine",
            r"sunset\s+yellow",
            r"allura\s+red",
            r"carmoisine",
            r"brilliant\s+blue",
            r"\be\s?102\b",
            r"\be\s?110\b",
            r"\be\s?129\b",
            r"\be\s?122\b",
            r"\bins\s?102\b",
            r"\bins\s?110\b",
            r"\bins\s?129\b",
        ],
    },
    {
        "name": "Monosodium Glutamate (MSG / E621)",
        "risk": "MODERATE_RISK",
        "category": "Flavor Enhancer",
        "reason": "Prohibited in food manufactured for infants below 12 months. Requires clear declaration under FSSAI Packaging & Labelling Rules.",
        "patterns": [r"monosodium\s+glutamate", r"\bmsg\b", r"\be\s?621\b", r"\bins\s?621\b"],
    },
    {
        "name": "High Fructose Corn Syrup (HFCS)",
        "risk": "MODERATE_RISK",
        "category": "Excessive Simple Sugar",
        "reason": "Directly linked to non-alcoholic fatty liver disease, rapid insulin spikes, and obesity.",
        "patterns": [r"high\s+fructose\s+corn\s+syrup", r"\bhfcs\b"],
    },
    {
        "name": "Artificial Sweeteners (Aspartame / Sucralose / Acesulfame-K)",
        "risk": "MODERATE_RISK",
        "category": "Intense Non-Nutritive Sweetener",
        "reason": "Requires mandatory statutory declaration under FSSAI: 'CONTAINS ARTIFICIAL SWEETENER AND FOR CALORIE CONSCIOUS'. Not recommended for children.",
        "patterns": [
            r"aspartame",
            r"acesulfame\s*k",
            r"sucralose",
            r"\be\s?951\b",
            r"\be\s?950\b",
            r"\be\s?955\b",
            r"\bins\s?951\b",
            r"\bins\s?950\b",
            r"\bins\s?955\b",
        ],
    },
]

# ---------------------------------------------------------------------
# 2. COMMON ALLERGENS DATABASE (FSSAI Mandatory Declaration)
# ---------------------------------------------------------------------
ALLERGENS_DB = [
    {"name": "Gluten / Wheat", "patterns": [r"\bwheat\b", r"\bgluten\b", r"\bmaida\b", r"\bbarley\b", r"\brye\b", r"\boats\b"]},
    {"name": "Peanuts", "patterns": [r"\bpeanut", r"\bgroundnut"]},
    {"name": "Tree Nuts", "patterns": [r"\balmond", r"\bcashew", r"\bwalnut", r"\bpista", r"\bhazelnut"]},
    {"name": "Milk & Dairy", "patterns": [r"\bmilk\b", r"\bwhey\b", r"\bcasein\b", r"\blactose\b", r"\bbutter\b", r"\bcheese\b", r"\bcurd\b"]},
    {"name": "Soy / Soya", "patterns": [r"\bsoy\b", r"\bsoya\b", r"\bsoybean\b", r"soy\s+lecithin"]},
    {"name": "Sulphites / Sulfites", "patterns": [r"sulphite", r"sulfite", r"sulfur\s+dioxide", r"e220", r"ins\s?220"]},
    {"name": "Eggs", "patterns": [r"\begg\b", r"\beggs\b", r"albumin"]},
    {"name": "Fish / Crustaceans", "patterns": [r"\bfish\b", r"\bprawn", r"\bshrimp", r"\bcrab"]},
]

# ---------------------------------------------------------------------
# 3. FSSAI / GOVT RDA NUTRITIONAL THRESHOLDS (Per 100g / 100ml)
# ---------------------------------------------------------------------
# High Fat, Sugar and Salt (HFSS) thresholds under Indian regulatory framework
HFSS_THRESHOLDS = {
    "added_sugar_g": {"high": 10.0, "moderate": 5.0, "unit": "g", "label": "Added Sugars"},
    "saturated_fat_g": {"high": 6.0, "moderate": 3.0, "unit": "g", "label": "Saturated Fat"},
    "trans_fat_g": {"high": 0.2, "moderate": 0.1, "unit": "g", "label": "Trans Fat"},
    "sodium_mg": {"high": 400.0, "moderate": 200.0, "unit": "mg", "label": "Sodium"},
    "calories_kcal": {"high": 400.0, "moderate": 250.0, "unit": "kcal", "label": "Energy / Calories"},
}


def analyze_ingredients(text):
    """
    Scans the extracted label text for ingredients, harmful chemicals,
    banned additives, and allergens.
    """
    text_lower = text.lower()
    
    # 1. Identify presence of Ingredients List section
    has_ingredient_list = bool(re.search(r"\b(ingredients?|ingrediente?s?|contains)\b", text_lower))
    
    # 2. Match Harmful Additives
    flagged_harmful = []
    has_banned_substance = False
    
    for item in HARMFUL_INGREDIENTS_DB:
        matched = False
        match_str = ""
        for pattern in item["patterns"]:
            m = re.search(pattern, text_lower)
            if m:
                matched = True
                match_str = m.group(0)
                break
        
        if matched:
            if item["risk"] == "BANNED":
                has_banned_substance = True
            flagged_harmful.append({
                "name": item["name"],
                "risk": item["risk"],
                "category": item["category"],
                "reason": item["reason"],
                "matched_text": match_str,
            })

    # 3. Match Allergens
    detected_allergens = []
    for allergen in ALLERGENS_DB:
        for pattern in allergen["patterns"]:
            if re.search(pattern, text_lower):
                detected_allergens.append(allergen["name"])
                break

    # Calculate Ingredient Safety Score (0-100)
    # Starts at 100, drops heavily for banned, moderately for high risk
    safety_score = 100
    if not has_ingredient_list:
        safety_score -= 25  # Missing mandatory ingredient declaration
    for item in flagged_harmful:
        if item["risk"] == "BANNED":
            safety_score -= 50
        elif item["risk"] == "HIGH_RISK":
            safety_score -= 25
        elif item["risk"] == "MODERATE_RISK":
            safety_score -= 10
            
    safety_score = max(0, min(100, safety_score))
    
    safety_status = "SAFE"
    if has_banned_substance or safety_score < 50:
        safety_status = "HAZARDOUS / BANNED"
    elif safety_score < 75:
        safety_status = "CAUTION REQUIRED"

    return {
        "has_ingredient_list": has_ingredient_list,
        "safety_score": safety_score,
        "safety_status": safety_status,
        "flagged_harmful": flagged_harmful,
        "has_banned_substance": has_banned_substance,
        "detected_allergens": detected_allergens,
    }


def analyze_nutrition(text):
    """
    Extracts nutritional declarations from the OCR text and checks them
    against Indian Govt (FSSAI) HFSS and RDA thresholds.
    """
    text_lower = text.lower()
    
    # Extraction regex patterns for standard nutritional declarations
    patterns = {
        "calories_kcal": [
            r"(?:energy|calories?|cal)\s*[:=\-]?\s*(\d+(?:\.\d+)?)\s*(?:k?cal|kj)?",
            r"(\d+(?:\.\d+)?)\s*(?:k?cal|calories?)\b",
        ],
        "protein_g": [
            r"protein\s*[:=\-]?\s*(\d+(?:\.\d+)?)\s*g?",
        ],
        "carbohydrates_g": [
            r"(?:carbohydrates?|carbs?)\s*[:=\-]?\s*(\d+(?:\.\d+)?)\s*g?",
        ],
        "added_sugar_g": [
            r"(?:added\s+sugars?|sugars?)\s*[:=\-]?\s*(\d+(?:\.\d+)?)\s*g?",
        ],
        "total_fat_g": [
            r"(?:total\s+fat|fat)\s*[:=\-]?\s*(\d+(?:\.\d+)?)\s*g?",
        ],
        "saturated_fat_g": [
            r"(?:saturated\s+fat|sat\.?\s+fat)\s*[:=\-]?\s*(\d+(?:\.\d+)?)\s*g?",
        ],
        "trans_fat_g": [
            r"trans\s+fat\s*[:=\-]?\s*(\d+(?:\.\d+)?)\s*g?",
        ],
        "sodium_mg": [
            r"sodium\s*[:=\-]?\s*(\d+(?:\.\d+)?)\s*mg?",
            r"salt\s*[:=\-]?\s*(\d+(?:\.\d+)?)\s*g?",
        ],
    }

    extracted_nutrition = {}
    
    for nutrient, regex_list in patterns.items():
        val = None
        for p in regex_list:
            m = re.search(p, text_lower)
            if m:
                try:
                    val = float(m.group(1))
                    if nutrient == "sodium_mg" and "salt" in m.group(0) and "g" in m.group(0):
                        # Convert grams of salt to mg of sodium (approx 400mg Na per 1g salt)
                        val = round(val * 400, 1)
                    break
                except (ValueError, IndexError):
                    continue
        extracted_nutrition[nutrient] = val

    # Proportion & HFSS Compliance Analysis
    hfss_flags = []
    hfss_score = 100  # starts at 100, drops for each exceeded threshold
    
    for metric, config in HFSS_THRESHOLDS.items():
        val = extracted_nutrition.get(metric)
        if val is not None:
            if val >= config["high"]:
                hfss_flags.append({
                    "nutrient": config["label"],
                    "value": val,
                    "unit": config["unit"],
                    "threshold": config["high"],
                    "status": "HIGH (HFSS VIOLATION)",
                    "severity": "red",
                    "note": f"Exceeds Govt maximum recommended threshold of {config['high']}{config['unit']}/100g.",
                })
                hfss_score -= 20
            elif val >= config["moderate"]:
                hfss_flags.append({
                    "nutrient": config["label"],
                    "value": val,
                    "unit": config["unit"],
                    "threshold": config["moderate"],
                    "status": "MODERATE",
                    "severity": "amber",
                    "note": f"Approaching high limit ({config['moderate']}{config['unit']}/100g).",
                })
                hfss_score -= 10
            else:
                hfss_flags.append({
                    "nutrient": config["label"],
                    "value": val,
                    "unit": config["unit"],
                    "threshold": config["high"],
                    "status": "COMPLIANT / LOW",
                    "severity": "green",
                    "note": f"Within safe daily dietary proportion.",
                })

    has_nutrition_table = any(v is not None for v in extracted_nutrition.values())
    hfss_score = max(0, min(100, hfss_score))
    
    if not has_nutrition_table:
        proportion_verdict = "NOT DECLARED"
    elif any(f["severity"] == "red" for f in hfss_flags):
        proportion_verdict = "HFSS (HIGH FAT/SUGAR/SALT WARNING)"
    elif any(f["severity"] == "amber" for f in hfss_flags):
        proportion_verdict = "MODERATE PROPORTION"
    else:
        proportion_verdict = "BALANCED / COMPLIANT"

    return {
        "has_nutrition_table": has_nutrition_table,
        "extracted_values": extracted_nutrition,
        "hfss_flags": hfss_flags,
        "hfss_score": hfss_score,
        "proportion_verdict": proportion_verdict,
    }


def run_full_food_and_ingredient_scan(text):
    """
    Unified entry point for ingredient safety + nutritional analysis.
    """
    ingredients_res = analyze_ingredients(text)
    nutrition_res = analyze_nutrition(text)

    # Combined Food & Health Rating (0 to 100)
    combined_score = round((ingredients_res["safety_score"] * 0.6) + (nutrition_res["hfss_score"] * 0.4))
    
    return {
        "ingredients": ingredients_res,
        "nutrition": nutrition_res,
        "food_safety_score": combined_score,
    }
