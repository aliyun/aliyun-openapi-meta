#!/usr/bin/env python3
"""
将 aliyun-openapi-meta 从三份冗余归一化为 single meta + description overlay。

Before:
  metadatas/{product}/{api}.json    - 结构 + example（语言无关）
  zh-CN/{product}/{api}.json        - 完整复制 + 中文描述
  en-US/{product}/{api}.json        - 完整复制 + 英文描述

After:
  metadatas/{product}/{api}.json    - 结构 + example（不变）
  descriptions/zh-CN/{product}/{api}.json  - 仅 parameters 的 description
  descriptions/en-US/{product}/{api}.json  - 仅 parameters 的 description
  products/zh-CN/products.json             - 产品列表（含中文名称）
  products/en-US/products.json             - 产品列表（含英文名称）
"""

import json
import os
import shutil
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def extract_descriptions(api_data):
    """Extract only language-dependent fields from an API JSON."""
    result = {}
    params = api_data.get("parameters", [])
    desc_params = []
    for p in params:
        desc = p.get("description", "")
        if desc:
            desc_params.append({"name": p["name"], "description": desc})
    if desc_params:
        result["parameters"] = desc_params
    if "deprecated" in api_data:
        result["deprecated"] = api_data["deprecated"]
    return result


def main():
    descriptions_dir = REPO_ROOT / "descriptions"
    products_dir = REPO_ROOT / "products"

    for lang in ["zh-CN", "en-US"]:
        lang_dir = REPO_ROOT / lang
        if not lang_dir.exists():
            print(f"Skipping {lang} (not found)")
            continue

        desc_lang_dir = descriptions_dir / lang
        desc_lang_dir.mkdir(parents=True, exist_ok=True)

        # Move products.json to products/{lang}/
        products_lang_dir = products_dir / lang
        products_lang_dir.mkdir(parents=True, exist_ok=True)
        products_src = lang_dir / "products.json"
        if products_src.exists():
            shutil.copy2(products_src, products_lang_dir / "products.json")
            print(f"Moved {lang}/products.json -> products/{lang}/products.json")

        # Extract descriptions from each API JSON
        api_count = 0
        for product_dir in sorted(lang_dir.iterdir()):
            if not product_dir.is_dir() or product_dir.name.startswith("."):
                continue
            product = product_dir.name
            desc_product_dir = desc_lang_dir / product
            desc_product_dir.mkdir(parents=True, exist_ok=True)

            for api_file in sorted(product_dir.iterdir()):
                if not api_file.name.endswith(".json") or api_file.name == "products.json":
                    continue
                try:
                    data = json.loads(api_file.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, UnicodeDecodeError):
                    continue

                desc = extract_descriptions(data)
                if desc:
                    (desc_product_dir / api_file.name).write_text(
                        json.dumps(desc, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8",
                    )
                    api_count += 1

        print(f"Extracted {api_count} description files for {lang}")

    # Remove old zh-CN and en-US directories
    for lang in ["zh-CN", "en-US"]:
        lang_dir = REPO_ROOT / lang
        if lang_dir.exists():
            shutil.rmtree(lang_dir)
            print(f"Removed {lang}/")

    # Summary
    print("\n=== After ===")
    for d in ["metadatas", "descriptions", "products"]:
        dp = REPO_ROOT / d
        if dp.exists():
            size = sum(f.stat().st_size for f in dp.rglob("*") if f.is_file())
            print(f"  {d}/: {size / 1024 / 1024:.1f} MB")


if __name__ == "__main__":
    main()
