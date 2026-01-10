import csv
from collections import defaultdict
from pathlib import Path

from core.career_components import Traits, Aptitudes, Interests
from data.onet.mappings import ABILITY_MAP, INTEREST_MAP, WORK_STYLE_MAP


# Resolve paths safely
BASE_DIR = Path(__file__).resolve().parents[1]
ONET_RAW_DIR = BASE_DIR / "data" / "onet" / "raw"
CSV_DIR = BASE_DIR / "data" / "onet" / "csv"

ABILITIES_FILE = CSV_DIR / "abilities.csv"
INTERESTS_FILE = CSV_DIR / "interests.csv"
WORK_STYLES_FILE = CSV_DIR / "work_styles.csv"
WORK_ACTIVITIES_FILE = CSV_DIR / "work_activities.csv"
OCCUPATION_FILE = CSV_DIR / "occupation_data.csv"


def load_abilities():
    """
    Loads O*NET Abilities.txt and maps them to internal aptitude dimensions.
    Returns: dict[SOC_code -> dict[aptitude_name -> list[values]]]
    """
    data = defaultdict(lambda: defaultdict(lambda: {"LV": [], "IM": []}))

    with open(ABILITIES_FILE, encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            soc_code = row["O*NET-SOC Code"]
            element_name = row["Element Name"]
            scale_id = row["Scale ID"]

            if scale_id not in ("LV", "IM"):
                continue


            if element_name not in ABILITY_MAP:
                continue

            try:
                value = float(row["Data Value"]) / 7.0
            except ValueError:
                continue

            internal_name, weight = ABILITY_MAP[element_name]
            data[soc_code][internal_name][scale_id].append(value * weight)

    return data


def build_aptitudes():
    """
    Aggregates mapped abilities into Aptitudes objects per career.
    Returns: dict[SOC_code -> Aptitudes]
    """
    raw = load_abilities()
    aptitudes_by_career = {}

    for soc_code, values in raw.items():
        aggregated = {}

        for name, scales in values.items():
            lv = sum(scales["LV"]) / len(scales["LV"]) if scales["LV"] else 0.0
            im = sum(scales["IM"]) / len(scales["IM"]) if scales["IM"] else 0.0

            aggregated[name] = lv * 0.6 + im * 0.4

        aptitudes_by_career[soc_code] = Aptitudes(aggregated)

    return aptitudes_by_career


def build_interests():
    data = defaultdict(lambda: defaultdict(list))

    with open(INTERESTS_FILE, encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            interest_soc = row["O*NET-SOC Code"]
            name = row["Element Name"]
            scale_id = row["Scale ID"]
            
            if name not in INTEREST_MAP:
                continue

            if scale_id != "OI":
                continue

            try:
                value = float(row["Data Value"]) / 7.0
            except ValueError:
                continue

            internal_name, weight = INTEREST_MAP[name]
            data[interest_soc][internal_name].append(value * weight)

    interests_by_career = {}

    for career_soc, values in data.items():
        aggregated = {
            dimension: sum(scores) / len(scores)
            for dimension, scores in values.items()
            if scores
        }
        interests_by_career[career_soc] = Interests(aggregated)

    return interests_by_career


def build_traits_from_work_styles():
    data = defaultdict(lambda: defaultdict(list))

    with open(WORK_STYLES_FILE, encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            scale_id = row["Scale ID"]
            if scale_id != "WI":
                continue

            element_name = row["Element Name"]
            if element_name not in WORK_STYLE_MAP:
                continue

            try:
                value = float(row["Data Value"]) / 3.0
                if value < 0: print(f"NEG VALUE {value} for {element_name}")
            except ValueError:
                continue

            career_soc = row["O*NET-SOC Code"]
            trait_name, weight = WORK_STYLE_MAP[element_name]
            data[career_soc][trait_name].append(value * weight)

    traits_by_career = {}

    for career_soc, values in data.items():
        aggregated = {
            trait: sum(scores) / len(scores)
            for trait, scores in values.items()
            if scores
        }
        traits_by_career[career_soc] = Traits(aggregated)

    return traits_by_career


if __name__ == "__main__":
    aptitudes = build_aptitudes()

    print("=====APTITUDES=====")
    for soc in ["15-1252.00", "11-1011.00"]:  # software dev, executive
        print("\nSOC:", soc)
        for k, v in aptitudes[soc].scores.items():
            print(f"  {k}: {v:.2f}")

    print("=====INTERESTS=====")

    interests = build_interests()

    for soc in ["15-1252.00", "11-1011.00"]:
        print("\nSOC:", soc)
        print("Interests:")
        for k, v in interests[soc].scores.items():
            print(f"  {k}: {v:.2f}")

    print("=====TRAITS (FROM WS)=====")

    traits = build_traits_from_work_styles()

    for soc in ["15-1252.00", "11-1011.00"]:
        print("\nSOC:", soc)
        print("Traits:")
        for k, v in traits[soc].scores.items():
            print(f"  {k}: {v:.2f}")

