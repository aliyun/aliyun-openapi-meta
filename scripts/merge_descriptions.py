#!/usr/bin/env python3
"""
将 zh-CN/ 和 en-US/ 中的 description 合并到 metadatas/ 中。

合并后的 metadatas/{product}/{api}.json 参数结构：
  "description": {"zh": "中文描述", "en": "English description"}

同时合并 products.json 中的 name 字段：
  "name": {"zh": "中文名", "en": "English name"}
"""

import json
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
LANG_MAP = {"zh-CN": "zh", "en-US": "en"}


def merge_api_descriptions(product_dir, api_name):
    """Merge descriptions from zh-CN and en-US into a single map."""
    desc_map = {}
    for lang_dir, lang_key in LANG_MAP.items():
        api_path = REPO_ROOT / lang_dir / product_dir / f"{api_name}.json"
        if not api_path.exists():
            continue
        try:
            data = json.loads(api_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        for p in data.get("parameters", []):
            desc = p.get("description", "")
            if desc:
                if p["name"] not in desc_map:
                    desc_map[p["name"]] = {}
                desc_map[p["name"]][lang_key] = desc
    return desc_map


def merge_product_names():
    """Merge product names from zh-CN and en-US products.json into metadatas/products.json."""
    meta_products_path = REPO_ROOT / "metadatas" / "products.json"
    meta_products = json.loads(meta_products_path.read_text(encoding="utf-8"))

    # Build name maps from each language
    name_maps = {}
    for lang_dir, lang_key in LANG_MAP.items():
        products_path = REPO_ROOT / lang_dir / "products.json"
        if not products_path.exists():
            continue
        lang_products = json.loads(products_path.read_text(encoding="utf-8"))
        for p in lang_products.get("products", []):
            code = p.get("code", "")
            name = p.get("name", "")
            if code and name:
                if code not in name_maps:
                    name_maps[code] = {}
                name_maps[code][lang_key] = name

    # Merge names into metadatas products
    merged_count = 0
    for p in meta_products.get("products", []):
        code = p.get("code", "")
        if code in name_maps:
            p["name"] = name_maps[code]
            merged_count += 1

    meta_products_path.write_text(
        json.dumps(meta_products, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Merged {merged_count} product names into metadatas/products.json")


def main():
    # 1. Merge product names
    merge_product_names()

    # 2. Merge API parameter descriptions
    metadatas_dir = REPO_ROOT / "metadatas"
    api_count = 0
    param_count = 0

    for product_dir in sorted(metadatas_dir.iterdir()):
        if not product_dir.is_dir() or product_dir.name.startswith("."):
            continue
        product = product_dir.name

        for api_file in sorted(product_dir.iterdir()):
            if not api_file.name.endswith(".json") or api_file.name in ("products.json", "version.json"):
                continue

            # Read base API data
            try:
                api_data = json.loads(api_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue

            # Get merged descriptions
            desc_map = merge_api_descriptions(product, api_file.stem)
            if not desc_map:
                continue

            # Merge descriptions into parameters
            modified = False
            for param in api_data.get("parameters", []):
                pname = param.get("name", "")
                if pname in desc_map:
                    param["description"] = desc_map[pname]
                    modified = True
                    param_count += 1

            if modified:
                api_file.write_text(
                    json.dumps(api_data, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8",
                )
                api_count += 1

    print(f"Merged descriptions into {api_count} API files, {param_count} parameters total")

    # 3. Report sizes
    print("\n=== Size report ===")
    for d in ["metadatas"]:
        dp = REPO_ROOT / d
        size = sum(f.stat().st_size for f in dp.rglob("*") if f.is_file())
        print(f"  {d}/: {size / 1024 / 1024:.1f} MB")


if __name__ == "__main__":
    main()
