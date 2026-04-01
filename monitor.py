translation = ""
impact = ""
sector = "general"
for line in text.split("\n"):
    if line.startswith("TRANSLATION:"):
        translation = line.replace("TRANSLATION:", "").strip()
    elif line.startswith("IMPACT:"):
        impact = line.replace("IMPACT:", "").strip()
    elif line.startswith("SECTOR:"):
        sector = line.replace("SECTOR:", "").strip().lower()
return translation, impact, sector
