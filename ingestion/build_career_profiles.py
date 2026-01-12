import csv
from collections import defaultdict
from pathlib import Path
from typing import Literal

from core.career_components import Traits, Aptitudes, Interests, Values, WorkStyles
from data.onet.mappings import ABILITY_MAP, INTEREST_MAP, WORK_STYLE_MAP, WORK_ACTIVITY_MAP, WORK_VALUE_MAP


# Resolve paths safely
BASE_DIR = Path(__file__).resolve().parents[1]
ONET_RAW_DIR = BASE_DIR / "data" / "onet" / "raw"
CSV_DIR = BASE_DIR / "data" / "onet" / "csv"

ABILITIES_FILE = CSV_DIR / "abilities.csv"
INTERESTS_FILE = CSV_DIR / "interests.csv"
WORK_STYLES_FILE = CSV_DIR / "work_styles.csv"
WORK_ACTIVITIES_FILE = CSV_DIR / "work_activities.csv"
OCCUPATION_FILE = CSV_DIR / "occupation_data.csv"
WORK_VALUES_FILE = CSV_DIR / "work_values.csv"

# For Values
VH_VALUE_MAP = {
    1: "Achievement",
    2: "Working Conditions",
    3: "Recognition",
    4: "Relationships",
    5: "Support",
    6: "Independence",
}

'''
SCALE RANGES: (O*NET 30.x)

LV: 0–7
IM: 1–5
IH: 0–6
OI: 1–7
WI: -3–3
DR: 0–10
VH: 1–6
EX: 1–7
'''
def normalise(value: float, scale: Literal["LV", "IM", "IH", "OI", "WI", "DR", "VH", "EX"]) -> float:
    if type(value) != float: value = float(value)

    if scale == "LV": return value / 7
    elif scale == "IM": return (value - 1) / 4
    elif scale == "IH": return value / 6
    elif scale == "OI": return (value - 1) / 6
    elif scale == "WI": return value / 3
    elif scale == "DR": return value / 10
    elif scale == "VH": return (value - 1) / 5
    elif scale == "EX": return (value - 1) / 6
    else: raise ValueError(f"Unknown scale: {scale}")


def build_aptitudes_from_abilities() -> dict[str, Aptitudes]:
    """
    Loads O*NET Abilities.txt and maps them to internal aptitude dimensions.
    Returns: dict[SOC_code -> dict[aptitude_name -> list[values]]]
    """
    data = defaultdict(lambda: defaultdict(lambda: {"LV": [], "IM": []}))

    with open(ABILITIES_FILE, encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            abilities_soc = row["O*NET-SOC Code"]
            element_name = row["Element Name"]
            scale_id = row["Scale ID"]
            raw_val = row["Data Value"]

            if element_name not in ABILITY_MAP:
                continue

            try:
                value = normalise(raw_val, scale_id)
            except ValueError:
                continue

            internal_name, weight = ABILITY_MAP[element_name]
            data[abilities_soc][internal_name][scale_id].append(value * weight)

    aptitudes_by_career = {}

    for abilities_soc, vals in data.items():
        aggregated = {}

        for name, scales in vals.items():
            lv = sum(scales["LV"]) / len(scales["LV"]) if scales["LV"] else 0.0
            im = sum(scales["IM"]) / len(scales["IM"]) if scales["IM"] else 0.0

            aggregated[name] = lv * 0.6 + im * 0.4

        aptitudes_by_career[abilities_soc] = Aptitudes(aggregated)

    return aptitudes_by_career


def build_interests() -> dict[str, Interests]:
    data = defaultdict(lambda: defaultdict(list))

    with open(INTERESTS_FILE, encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            interest_soc = row["O*NET-SOC Code"]
            name = row["Element Name"]
            scale_id = row["Scale ID"]
            raw_val = row["Data Value"]

            if name not in INTEREST_MAP:
                continue

            if scale_id != "OI":
                continue

            try:
                value = normalise(raw_val, scale_id)
            except ValueError:
                continue

            internal_name, weight = INTEREST_MAP[name]
            data[interest_soc][internal_name].append(value * weight)

    interests_by_career = {}

    for career_soc, vals in data.items():
        aggregated = {
            dimension: sum(scores) / len(scores)
            for dimension, scores in vals.items()
            if scores
        }
        interests_by_career[career_soc] = Interests(aggregated)

    return interests_by_career


def build_traits_from_work_styles() -> dict[str, Traits]:
    data = defaultdict(lambda: defaultdict(list))

    with open(WORK_STYLES_FILE, encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            work_style__soc = row["O*NET-SOC Code"]
            name = row["Element Name"]
            scale_id = row["Scale ID"]
            raw_val = row["Data Value"]

            if scale_id != "WI":
                continue


            if name not in WORK_STYLE_MAP:
                continue

            try:
                value = normalise(raw_val, scale_id)
            except ValueError:
                continue

            trait_name, weight = WORK_STYLE_MAP[name]
            data[work_style__soc][trait_name].append(value * weight)

    traits_by_career = {}

    for career_soc, vals in data.items():
        aggregated = {
            trait: sum(scores) / len(scores)
            for trait, scores in vals.items()
            if scores
        }
        traits_by_career[career_soc] = Traits(aggregated)

    return traits_by_career


def build_traits_from_work_activities() -> dict[str, Traits]:
    data = defaultdict(lambda: defaultdict(lambda: {"LV": [], "IM": []}))

    with open(WORK_ACTIVITIES_FILE, encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            work_activity__soc = row["O*NET-SOC Code"]
            name = row["Element Name"]
            scale_id = row["Scale ID"]
            raw_val = row["Data Value"]

            if name not in WORK_ACTIVITY_MAP:
                continue

            try:
                value = normalise(raw_val, scale_id)
            except ValueError:
                continue

            trait_name, weight = WORK_ACTIVITY_MAP[name]
            data[work_activity__soc][trait_name][scale_id].append(value * weight)

    traits_by_career = {}

    for career_soc, vals in data.items():
        aggregated = {}

        for trait, scales in vals.items():
            lv = sum(scales["LV"]) / len(scales["LV"]) if scales["LV"] else 0.0
            im = sum(scales["IM"]) / len(scales["IM"]) if scales["IM"] else 0.0

            # Importance slightly outweighs frequency
            aggregated[trait] = lv * 0.4 + im * 0.6

        traits_by_career[career_soc] = Traits(aggregated)

    return traits_by_career


def build_values_from_work_values() -> dict[str, Values]:
    """
    Builds the Values component from O*NET Work Values data.

    Rules:
    - EX provides magnitude for each value.
    - VH indicates which values are top-3 for the occupation.
    - If VH exists for a SOC, only top-3 values are kept.
    - If VH is missing for a SOC, fall back to EX-only.
    """

    from collections import defaultdict

    # SOC -> value_name -> EX score (weighted)
    ex_scores_by_soc = defaultdict(dict)

    # SOC -> set of value_names that are top-3 (VH)
    vh_hits_by_soc = defaultdict(set)

    with open(WORK_VALUES_FILE, encoding="utf-8") as file:
        reader = csv.DictReader(file)

        for row in reader:
            soc_code = row["O*NET-SOC Code"]
            scale_id = row["Scale ID"]
            element_name = row["Element Name"]
            raw_value = row["Data Value"]

            # --- EX: magnitude ---
            if scale_id == "EX":
                if element_name not in WORK_VALUE_MAP:
                    continue

                try:
                    ex_value = normalise(raw_value, "EX")
                except ValueError:
                    continue

                value_name, weight = WORK_VALUE_MAP[element_name]
                ex_scores_by_soc[soc_code][value_name] = ex_value * weight

            # --- VH: top-3 selector ---
            elif scale_id == "VH":
                try:
                    vh_code = int(float(raw_value))
                except ValueError:
                    continue

                if vh_code == 0 or vh_code not in VH_VALUE_MAP:
                    continue

                value_element = VH_VALUE_MAP[vh_code]
                if value_element not in WORK_VALUE_MAP:
                    continue

                value_name, _ = WORK_VALUE_MAP[value_element]
                vh_hits_by_soc[soc_code].add(value_name)

    # --- Combine EX and VH ---
    values_by_career = {}

    for soc_code, ex_values in ex_scores_by_soc.items():
        aggregated = {}

        has_vh = bool(vh_hits_by_soc.get(soc_code))

        for value_name, ex_score in ex_values.items():
            if has_vh:
                aggregated[value_name] = (
                    ex_score if value_name in vh_hits_by_soc[soc_code] else 0.0
                )
            else:
                aggregated[value_name] = ex_score

        values_by_career[soc_code] = Values(aggregated)

    return values_by_career


def merge_traits(
    ws_traits_by_soc: dict[str, Traits],
    wa_traits_by_soc: dict[str, Traits],
) -> dict[str, Traits]:
    """
    Merge Traits from Work Styles (WI-based) and Work Activities (LV+IM-based).

    Rules:
    - Traits are additive across sources
    - Missing traits default to 0
    - WI sign is preserved
    - No normalization or weighting at merge time
    """

    from collections import defaultdict

    merged_by_soc = {}

    all_socs = set(ws_traits_by_soc) | set(wa_traits_by_soc)

    for soc_code in all_socs:
        merged_scores = defaultdict(float)

        work_style_traits = ws_traits_by_soc.get(soc_code)
        if work_style_traits:
            for trait_name, value in work_style_traits.scores.items():
                merged_scores[trait_name] += value

        work_activity_traits = wa_traits_by_soc.get(soc_code)
        if work_activity_traits:
            for trait_name, value in work_activity_traits.scores.items():
                merged_scores[trait_name] += value

        merged_by_soc[soc_code] = Traits(dict(merged_scores))

    return merged_by_soc


def derive_work_styles(
    traits_by_soc: dict[str, Traits],
) -> dict[str, WorkStyles]:
    """
    Derives WorkStyles from merged Traits.

    WorkStyles are interpretive environment descriptors,
    computed deterministically from Traits.
    """

    work_styles_by_soc = {}

    for soc_code, soc_traits in traits_by_soc.items():
        t = soc_traits.scores

        # Default missing traits to 0.0
        # analytical = t.get("analytical", 0.0) (Unused)
        creative = t.get("creative", 0.0)
        social = t.get("social", 0.0)
        leadership = t.get("leadership", 0.0)
        detail_oriented = t.get("detail_oriented", 0.0)
        adaptability = t.get("adaptability", 0.0)

        # Assigning WS
        team_based = social + leadership
        structure = detail_oriented - adaptability
        pace = leadership + adaptability
        ambiguity_tolerance = adaptability + creative - detail_oriented

        work_styles_by_soc[soc_code] = WorkStyles({
            "team_based": team_based,
            "structure": structure,
            "pace": pace,
            "ambiguity_tolerance": ambiguity_tolerance,
        })

    return work_styles_by_soc

if __name__ == "__main__":
    aptitudes = build_aptitudes_from_abilities()

    print("\n\n=====APTITUDES=====")
    for soc in ["15-1251.00", "11-1011.00"]:  # computer programmer, executive
        print("\nSOC:", soc)
        for k, v in aptitudes[soc].scores.items():
            print(f"  {k}: {v:.2f}")

    print("\n\n=====INTERESTS=====")

    interests = build_interests()

    for soc in ["15-1251.00", "11-1011.00"]:
        print("\nSOC:", soc)
        for k, v in interests[soc].scores.items():
            print(f"  {k}: {v:.2f}")

    print("\n\n=====TRAITS (FROM WS)=====")

    ws_traits = build_traits_from_work_styles()

    for soc in ["15-1251.00", "11-1011.00"]:
        print("\nSOC:", soc)
        for k, v in ws_traits[soc].scores.items():
            print(f"  {k}: {v:.2f}")

    print("\n\n=====TRAITS (FROM WA)=====")

    wa_traits = build_traits_from_work_activities()

    for soc in ["15-1251.00", "11-1011.00"]:
        print("\nSOC:", soc)
        for k, v in wa_traits[soc].scores.items():
            print(f"  {k}: {v:.2f}")

    print("\n\n=====VALUES=====")

    values = build_values_from_work_values()

    for soc in ["15-1251.00", "11-1011.00"]:
        print("\nSOC:", soc)
        for k, v in values[soc].scores.items():
            print(f"  {k}: {v:.2f}")

    print("\n\n=====TRAITS=====")

    traits = merge_traits(ws_traits, wa_traits)

    for soc in ["15-1251.00", "11-1011.00"]:
        print("\nSOC:", soc)
        for k, v in traits[soc].scores.items():
            print(f"  {k}: {v:.2f}")

    print("\n\n=====WORK STYLES=====")

    ws = derive_work_styles(traits)

    for soc in ["15-1251.00", "11-1011.00"]:
        print("\nSOC:", soc)
        for k, v in ws[soc].scores.items():
            print(f"  {k}: {v:.2f}")
