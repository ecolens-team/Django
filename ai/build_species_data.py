"""
Builds enriched_species_data.json by combining:
  - ecolens_classes.json  (the 3480 AI class labels — source of truth for which species exist)
  - species_summaries.json (Wikipedia summaries fetched earlier)
  - plants_data.csv / insects_data.csv (GBIF occurrences — type, IUCN category, vernacular name,
                                        full taxonomy: genus, family, order)

Output: enriched_species_data.json  — ready to use as a Django seed source.

Each entry:
{
  "scientific_name": "Ablattaria arenaria",
  "type": "INSECT",                  # PLANT | INSECT
  "summary": "...",                  # from Wikipedia, or ""
  "wiki_url": "...",                 # from Wikipedia, or ""
  "common_name_en": "snail hunter", # best vernacular name found, or ""
  "is_endangered": true,            # true if IUCN = CR or EN
  "iucn_category": "LC",            # raw IUCN string, or ""
  "genus": "Ablattaria",            # from GBIF, or first word of scientific_name
  "family": "Silphidae",            # from GBIF, or ""
  "order": "Coleoptera"             # from GBIF, or ""
}
"""

import csv
import json
import os

CLASSES_FILE = "../Django/observations/ecolens_classes.json"
SUMMARIES_FILE = "species_summaries.json"
INSECTS_CSV = "../gp2-ai/plants-insects-data-csvs-/insects_data.csv"
PLANTS_CSV = "../gp2-ai/plants-insects-data-csvs-/plants_data.csv"
OUTPUT_FILE = "species_summaries.json"

ENDANGERED_CATEGORIES = {"CR", "EN"}


def load_classes():
    with open(CLASSES_FILE, encoding="utf-8") as f:
        return json.load(f)  # list of "Genus_species" strings


def load_summaries():
    with open(SUMMARIES_FILE, encoding="utf-8") as f:
        data = json.load(f)
    # keyed by "Genus_species" to match classes format
    return {
        entry["scientific_name"].replace(" ", "_"): entry
        for entry in data
    }


def build_gbif_lookup():
    """
    Returns dict: "Genus_species" -> {type, iucn_category, common_name_en}
    Processes occurrences — many rows per species, we take the first non-empty value found.
    """
    lookup = {}

    def process(path, species_type):
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                raw = row.get("species", "").strip()
                if not raw:
                    continue
                key = raw.replace(" ", "_")

                if key not in lookup:
                    lookup[key] = {
                        "type": species_type,
                        "iucn_category": "",
                        "common_name_en": "",
                        "genus": "",
                        "family": "",
                        "order": "",
                    }

                entry = lookup[key]

                if not entry["iucn_category"]:
                    iucn = row.get("iucnRedListCategory", "").strip()
                    if iucn:
                        entry["iucn_category"] = iucn

                if not entry["common_name_en"]:
                    name = row.get("vernacularName", "").strip()
                    if name and name.isascii():
                        entry["common_name_en"] = name.lower()

                if not entry["genus"]:
                    entry["genus"] = row.get("genus", "").strip()

                if not entry["family"]:
                    entry["family"] = row.get("family", "").strip()

                if not entry["order"]:
                    entry["order"] = row.get("order", "").strip()

    print("Reading insects CSV...")
    process(INSECTS_CSV, "INSECT")
    print("Reading plants CSV...")
    process(PLANTS_CSV, "PLANT")

    return lookup


def main():
    print("Loading classes...")
    classes = load_classes()

    print("Loading summaries...")
    summaries = load_summaries()

    print("Building GBIF lookup...")
    gbif = build_gbif_lookup()

    results = []
    missing_type = 0

    for cls in classes:
        summary_entry = summaries.get(cls, {})
        gbif_entry = gbif.get(cls, {})

        species_type = gbif_entry.get("type")
        if not species_type:
            missing_type += 1
            species_type = "PLANT"  # fallback

        iucn = gbif_entry.get("iucn_category", "")
        is_endangered = iucn in ENDANGERED_CATEGORIES

        # Genus: prefer GBIF value, fall back to first word of scientific name
        scientific_name = cls.replace("_", " ")
        genus = gbif_entry.get("genus", "") or scientific_name.split()[0]

        results.append({
            "scientific_name": scientific_name,
            "type": species_type,
            "summary": summary_entry.get("summary", ""),
            "wiki_url": summary_entry.get("wiki_url", ""),
            "common_name_en": gbif_entry.get("common_name_en", ""),
            "is_endangered": is_endangered,
            "iucn_category": iucn,
            "genus": genus,
            "family": gbif_entry.get("family", ""),
            "order": gbif_entry.get("order", ""),
        })

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    total = len(results)
    plants = sum(1 for r in results if r["type"] == "PLANT")
    insects = sum(1 for r in results if r["type"] == "INSECT")
    endangered = sum(1 for r in results if r["is_endangered"])
    with_common = sum(1 for r in results if r["common_name_en"])
    with_summary = sum(1 for r in results if r["summary"])
    with_family = sum(1 for r in results if r["family"])
    with_order = sum(1 for r in results if r["order"])
    distinct_genera = len({r["genus"] for r in results if r["genus"]})
    distinct_families = len({r["family"] for r in results if r["family"]})
    distinct_orders = len({r["order"] for r in results if r["order"]})

    print(f"\nDone. Written to {OUTPUT_FILE}")
    print(f"  Total:            {total}")
    print(f"  Plants:           {plants}")
    print(f"  Insects:          {insects}")
    print(f"  Missing type:     {missing_type} (defaulted to PLANT)")
    print(f"  Endangered:       {endangered}")
    print(f"  With common name: {with_common}")
    print(f"  With summary:     {with_summary}")
    print(f"  With family:      {with_family}  ({distinct_families} distinct families)")
    print(f"  With order:       {with_order}  ({distinct_orders} distinct orders)")
    print(f"  Distinct genera:  {distinct_genera}")


if __name__ == "__main__":
    main()
