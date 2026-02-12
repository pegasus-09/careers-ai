"""
Keyword-to-career matching from teacher comments.
Scans comment text for curated keywords and maps them to O*NET SOC codes
that may not appear in the deterministic top 20.
"""
from typing import Dict, List, Set


CAREER_KEYWORDS: Dict[str, List[tuple]] = {
    # Film / Media
    "screenwriting": [("27-3043.00", "Writers and Authors")],
    "film script": [("27-3043.00", "Writers and Authors"), ("27-2012.00", "Producers and Directors")],
    "film": [("27-2012.00", "Producers and Directors"), ("27-4032.00", "Film and Video Editors")],
    "script": [("27-3043.00", "Writers and Authors"), ("27-2012.00", "Producers and Directors")],
    "video editing": [("27-4032.00", "Film and Video Editors")],

    # Music
    "music": [("27-2041.00", "Music Directors and Composers"), ("27-2042.00", "Musicians and Singers")],
    "instrument": [("27-2042.00", "Musicians and Singers")],
    "song": [("27-2041.00", "Music Directors and Composers")],

    # Healthcare
    "nursing": [("29-1141.00", "Registered Nurses")],
    "aged care": [("29-1141.00", "Registered Nurses"), ("21-1093.00", "Social and Human Service Assistants")],
    "first aid": [("29-2042.00", "Emergency Medical Technicians")],

    # Trades
    "electrician": [("47-2111.00", "Electricians")],
    "apprenticeship": [("47-2111.00", "Electricians"), ("47-2031.00", "Carpenters")],
    "woodwork": [("47-2031.00", "Carpenters")],

    # Technology
    "programming": [("15-1252.00", "Software Developers")],
    "discord bot": [("15-1252.00", "Software Developers")],
    "coding": [("15-1252.00", "Software Developers")],
    "app": [("15-1252.00", "Software Developers")],

    # Law / Politics
    "debating": [("23-1011.00", "Lawyers")],
    "law": [("23-1011.00", "Lawyers")],
    "politics": [("11-1031.00", "Legislators")],

    # Design
    "graphic design": [("27-1024.00", "Graphic Designers")],
    "logo": [("27-1024.00", "Graphic Designers")],
    "branding": [("27-1024.00", "Graphic Designers"), ("27-1011.00", "Art Directors")],
    "UX": [("15-1255.01", "Video Game Designers")],

    # Counselling / Social work
    "mental health": [("21-1014.00", "Mental Health Counselors"), ("21-1021.00", "Child, Family, and School Counselors")],
    "counselling": [("21-1014.00", "Mental Health Counselors")],
    "social justice": [("21-1029.00", "Social Workers, All Other")],

    # Sports
    "biomechanics": [("29-1128.00", "Exercise Physiologists")],
    "sports science": [("29-1128.00", "Exercise Physiologists")],
    "physiotherapy": [("29-1123.00", "Physical Therapists")],
    "coaching": [("27-2022.00", "Coaches and Scouts")],
}

# Pre-sort keywords longest-first so "film script" matches before "film"
_SORTED_KEYWORDS = sorted(CAREER_KEYWORDS.keys(), key=len, reverse=True)


def suggest_careers_from_comments(
    teacher_comments: List[dict],
    top_20_soc_codes: Set[str],
) -> List[dict]:
    """
    Scan teacher comments for keyword matches and return career suggestions
    not already in the deterministic top 20.

    Returns max 3 suggestions, each with soc_code, title, keyword, teacher, quote.
    """
    if not teacher_comments:
        return []

    # Collect all matches: soc_code -> best evidence
    matches: Dict[str, dict] = {}

    for tc in teacher_comments:
        text = (tc.get("comment_text") or "").lower()
        teacher = tc.get("teacher_name", "Unknown")

        for keyword in _SORTED_KEYWORDS:
            if keyword.lower() in text:
                for soc_code, title in CAREER_KEYWORDS[keyword]:
                    if soc_code in top_20_soc_codes:
                        continue
                    if soc_code not in matches:
                        # Extract a short quote around the keyword
                        idx = text.find(keyword.lower())
                        start = max(0, idx - 40)
                        end = min(len(text), idx + len(keyword) + 40)
                        snippet = text[start:end].strip()
                        if start > 0:
                            snippet = "..." + snippet
                        if end < len(text):
                            snippet = snippet + "..."

                        matches[soc_code] = {
                            "soc_code": soc_code,
                            "title": title,
                            "keyword": keyword,
                            "teacher": teacher,
                            "quote": snippet,
                        }

    # Return max 3
    return list(matches.values())[:3]
