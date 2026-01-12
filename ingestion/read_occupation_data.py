import csv
from pathlib import Path
from typing import Dict, List, Tuple


# -----------------------------
# Path
# -----------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OCCUPATION_CSV_PATH = PROJECT_ROOT / "data" / "onet" / "csv" / "occupation_data.csv"


# -----------------------------
# Load SOC → title mapping
# -----------------------------

def load_soc_title_mapping(csv_path: Path=OCCUPATION_CSV_PATH) -> Dict[str, str]:
    soc_to_title: Dict[str, str] = {}

    with csv_path.open(newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)

        if not reader.fieldnames:
            raise ValueError("occupation_data.csv has no headers")

        # Normalize headers once
        header_map = {name.lower(): name for name in reader.fieldnames}
        soc_column = header_map.get("o*net-soc code")
        title_column = header_map.get("title")

        if soc_column is None or title_column is None:
            raise ValueError(
                "occupation_data.csv must contain SOC code and title columns"
            )

        for row in reader:
            soc = row[soc_column].strip()
            job = row[title_column].strip()

            if soc:
                soc_to_title[soc] = job

    return soc_to_title


# -----------------------------
# Entry point
# -----------------------------

if __name__ == "__main__":
    soc_title_mapping = load_soc_title_mapping(OCCUPATION_CSV_PATH)
    print(soc_title_mapping)

    print(f"Loaded {len(soc_title_mapping)} SOC codes\n")

    print("Example entries:")
    for index, (soc_code, job_title) in enumerate(soc_title_mapping.items()):
        print(f"{soc_code}: {job_title}")
        if index >= 10:
            break
