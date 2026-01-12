import csv
from pathlib import Path


# Resolve project root no matter where this script is run from
BASE_DIR = Path(__file__).resolve().parents[1]
ONET_CSV_DIR = BASE_DIR / "data" / "onet" / "csv"

SOC_FIELD = "O*NET-SOC Code"


def extract_all_soc_codes(csv_dir: Path) -> set[str]:
    """
    Extracts the union of all SOC codes appearing in any CSV file
    under csv_dir. A SOC only needs to appear in one file to be included.
    """

    soc_codes: set[str] = set()

    for csv_file in csv_dir.glob("*.csv"):
        with open(csv_file, encoding="utf-8") as f:
            reader = csv.DictReader(f)

            if not reader.fieldnames or SOC_FIELD not in reader.fieldnames:
                continue

            for row in reader:
                soc = row.get(SOC_FIELD)
                if soc:
                    soc_codes.add(soc.strip())

    return soc_codes


def main():
    soc_codes = extract_all_soc_codes(ONET_CSV_DIR)

    print(f"Found {len(soc_codes)} unique SOC codes:\n")
    for soc in sorted(soc_codes):
        print(soc)


if __name__ == "__main__":
    main()
