import csv
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
ONET_RAW = BASE_DIR / "data" / "onet" / "raw"
ONET_CSV = BASE_DIR / "data" / "onet" / "csv"

ONET_CSV.mkdir(parents=True, exist_ok=True)


def convert(tsv_name, csv_name):
    tsv_path = ONET_RAW / tsv_name
    csv_path = ONET_CSV / csv_name

    with open(tsv_path, encoding="utf-8") as tsv_file:
        reader = csv.reader(tsv_file, delimiter="\t")
        rows = list(reader)

    with open(csv_path, "w", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerows(rows)

    print(f"Converted {tsv_name} → {csv_name}")


if __name__ == "__main__":
    convert("Work Values.txt", "work_values.csv")
