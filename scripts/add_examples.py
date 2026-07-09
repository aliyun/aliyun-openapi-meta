#!/usr/bin/env python3
"""
为 aliyun-openapi-meta 中的 API JSON 文件添加 example 字段。

从 http://aliyun-cli-api-map.aliyun-inc.com 获取推荐的 CLI example，
写入每个 API JSON 的顶层 "example" 字段：

  "example": {
    "unifiedCli": "新版 CLI 命令",
    "legacyCli": "旧版 CLI 命令"
  }

用法:
  python3 scripts/add_examples.py                          # 处理所有产品
  python3 scripts/add_examples.py --product Ecs            # 只处理 Ecs
  python3 scripts/add_examples.py --product Ecs --dry-run  # 只预览不写入
"""

import json
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional, Dict, List
from concurrent.futures import ThreadPoolExecutor, as_completed

REPO_ROOT = Path(__file__).resolve().parent.parent
PRODUCTS_JSON = REPO_ROOT / "metadatas" / "products.json"

EXAMPLE_API_URL = (
    "http://aliyun-cli-api-map.aliyun-inc.com/v1/apis"
    "/{product}/{version}/{api_name}/recommended-example"
)

# Directories to update
TARGET_DIRS = ["metadatas", "zh-CN", "en-US"]

CONCURRENCY = 8
REQUEST_TIMEOUT = 10


def fetch_example(product_code: str, version: str, api_name: str) -> Optional[Dict]:
    """Fetch example from API. Returns {"unifiedCli": ..., "legacyCli": ...} or None."""
    url = EXAMPLE_API_URL.format(
        product=product_code, version=version, api_name=api_name
    )
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if data.get("status") != "SUCCESS":
            return None
        example_data = data.get("example", {})
        unified = example_data.get("unifiedCli", "")
        legacy = example_data.get("cli", "")
        if not unified and not legacy:
            return None
        result = {}
        if unified:
            result["unifiedCli"] = unified
        if legacy:
            result["legacyCli"] = legacy
        return result
    except Exception:
        return None


def add_example_to_file(json_path: Path, example: dict) -> bool:
    """Add example field to a JSON file. Returns True if file was modified."""
    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, FileNotFoundError):
        return False

    if not isinstance(data, dict):
        return False

    old_example = data.get("example")
    if old_example == example:
        return False

    data["example"] = example
    json_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return True


def process_product(product_code: str, version: str, api_names: List[str], dry_run: bool) -> Dict:
    """Process all APIs for one product. Returns stats."""
    stats = {"total": 0, "fetched": 0, "written": 0, "failed": 0, "skipped": 0}
    api_count = len(api_names)

    # Fetch examples concurrently
    examples = {}
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
        futures = {
            pool.submit(fetch_example, product_code, version, name): name
            for name in api_names
        }
        done = 0
        for future in as_completed(futures):
            name = futures[future]
            done += 1
            result = future.result()
            if result:
                examples[name] = result
                stats["fetched"] += 1
            else:
                stats["failed"] += 1
            if done % 50 == 0 or done == api_count:
                print(f"  [{product_code}] fetched {done}/{api_count}")

    if dry_run:
        print(f"  [{product_code}] dry-run: would write {len(examples)} examples")
        stats["written"] = len(examples)
        return stats

    # Write to JSON files
    for api_name, example in examples.items():
        stats["total"] += 1
        modified_any = False
        for dir_name in TARGET_DIRS:
            json_path = REPO_ROOT / dir_name / product_code.lower() / f"{api_name}.json"
            if json_path.exists():
                if add_example_to_file(json_path, example):
                    modified_any = True
        if modified_any:
            stats["written"] += 1
        else:
            stats["skipped"] += 1

    return stats


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Add example field to openapi-meta JSONs")
    parser.add_argument("--product", "-p", type=str, help="Only process this product code")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    args = parser.parse_args()

    products_data = json.loads(PRODUCTS_JSON.read_text(encoding="utf-8"))
    products = products_data.get("products", [])

    if args.product:
        target = args.product.lower()
        products = [p for p in products if p["code"].lower() == target]
        if not products:
            print(f"Product '{args.product}' not found")
            sys.exit(1)

    total_stats = {"total": 0, "fetched": 0, "written": 0, "failed": 0}
    start_time = time.time()

    for product in products:
        code = product["code"]
        version = product.get("version", "")
        api_names = product.get("apis", [])

        if not version or not api_names:
            continue

        print(f"\nProcessing {code} (version={version}, apis={len(api_names)})")
        stats = process_product(code, version, api_names, args.dry_run)

        for k in total_stats:
            total_stats[k] += stats[k]

        print(
            f"  [{code}] done: fetched={stats['fetched']}, "
            f"written={stats['written']}, failed={stats['failed']}"
        )

    elapsed = time.time() - start_time
    print(f"\n{'=' * 60}")
    print(f"Total: fetched={total_stats['fetched']}, written={total_stats['written']}, "
          f"failed={total_stats['failed']}, elapsed={elapsed:.1f}s")


if __name__ == "__main__":
    main()
