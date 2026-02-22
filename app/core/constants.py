# IARC Carcinogenicity Group Definitions
IARC_EVIDENCE = {
    "Group 1": "Carcinogenic to humans.",
    "Group 2A": "Probably carcinogenic to humans.",
    "Group 2B": "Possibly carcinogenic to humans.",
    "Group 3": "Not classifiable as to its carcinogenicity to humans.",
    "Not Found": "Insufficient data to classify carcinogenicity"
}

# Practical advice based on predicted routes
ROUTE_ADVICE = {
    "oral": "Avoid ingestion. Wash hands thoroughly after handling.",
    "dermal": "Wear protective gloves and clothing to prevent skin contact.",
    "inhalation": "Use in a well-ventilated area or wear a respiratory mask.",
    "ocular": "Wear safety goggles or other eye protection."
}

# Hazard level descriptions
HAZARD_LEVEL_DESCRIPTIONS = {
    "Group 1": "High",
    "Group 2A": "Moderate to High",
    "Group 2B": "Moderate",
    "Group 3": "Low",
    "Not Found": "Insufficient data"
}

# Category mapping
CATEGORY_MAPPING = {
    1: "Aerosol / Spray (Disinfectant, Freshener, Cleaner)",
    2: "Liquid Solution (Bleach, Detergent, Cleaner, Chemical)",
    3: "Powder / Granular (Detergent, Cleanser, Chemical)",
    4: "Cream / Gel / Paste (Polish, Cleaner, Compound)",
    5: "Solid / Tablet / Block (Bleach solid, chemical block)",
    6: "Vapor / Strong Fumes (Solvent, Paint, Thinner, Chemical)",
    7: "Mixed / Unknown HUHS Substance"
}
