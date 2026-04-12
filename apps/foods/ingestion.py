from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin

import requests
from django.conf import settings
from django.db import transaction
from lxml import etree

from apps.foods.models import Foods

BASE_DOMAIN = "https://www.xiaochushuo.com"
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}
CSV_HEADERS = [
    "类型",
    "标题",
    "描述",
    "作者",
    "作者主页",
    "收藏数量",
    "评论数量",
    "图片",
    "菜谱链接",
    "来源页",
]
DEFAULT_CSV_PATH = settings.BASE_DIR / "data" / "imports" / "food.csv"


@dataclass(frozen=True)
class CrawlResult:
    csv_path: Path
    page_count: int
    row_count: int


@dataclass(frozen=True)
class ImportResult:
    csv_path: Path
    created_count: int
    cleared_count: int


def clean_text(text: str | None) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def get_page_html(url: str, *, timeout: int = 15) -> str:
    response = requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout)
    response.raise_for_status()
    response.encoding = response.apparent_encoding
    return response.text


def parse_page(page_text: str, page_url: str) -> list[list[str]]:
    tree = etree.HTML(page_text)
    type_name = clean_text(tree.xpath('string(//*[@id="listtitle"])')) or "其他"
    li_list = tree.xpath('//ul[@class="menu_list"]/li')

    rows: list[list[str]] = []
    for li in li_list:
        recipe_href = li.xpath("./a/@href")
        recipe_url = urljoin(BASE_DOMAIN, recipe_href[0]) if recipe_href else ""
        imgurl = clean_text(_first_or_empty(li.xpath('.//div[contains(@class,"img")]//img/@src')))
        title = clean_text(li.xpath('string(.//div[@class="txt"]/a/h4)'))
        describe = clean_text(li.xpath('string(.//div[@class="txt"]/a/p[@class="pbm"])'))
        author = clean_text(li.xpath('string(.//div[@class="writer"]/a)'))
        author_href = li.xpath('.//div[@class="writer"]/a/@href')
        author_url = urljoin(BASE_DOMAIN, author_href[0]) if author_href else ""
        collect = clean_text(li.xpath('string(.//div[@class="list_collect"]/span)'))
        comment = clean_text(li.xpath('string(.//div[@class="praise"]/span)'))
        rows.append(
            [
                type_name,
                title,
                describe,
                author,
                author_url,
                collect,
                comment,
                imgurl,
                recipe_url,
                page_url,
            ]
        )
    return rows


def crawl_to_csv(source_url: str, page_count: int, csv_path: Path | None = None) -> CrawlResult:
    target_path = csv_path or DEFAULT_CSV_PATH
    target_path.parent.mkdir(parents=True, exist_ok=True)

    normalized_url = source_url.strip()
    if not normalized_url.endswith("/"):
        normalized_url += "/"

    all_rows: list[list[str]] = []
    for page_index in range(1, page_count + 1):
        page_url = normalized_url if page_index == 1 else f"{normalized_url}?page={page_index}"
        page_text = get_page_html(page_url)
        all_rows.extend(parse_page(page_text, page_url))

    with target_path.open("w", encoding="utf-8-sig", newline="") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(CSV_HEADERS)
        writer.writerows(all_rows)

    return CrawlResult(csv_path=target_path, page_count=page_count, row_count=len(all_rows))


def import_csv_to_foods(
    csv_path: Path | None = None,
    *,
    clear_existing: bool = False,
) -> ImportResult:
    target_path = csv_path or DEFAULT_CSV_PATH
    if not target_path.exists():
        raise FileNotFoundError(f"CSV 文件不存在: {target_path}")

    rows = list(_read_csv_rows(target_path))
    cleared_count = 0
    with transaction.atomic():
        if clear_existing:
            cleared_count, _ = Foods.objects.all().delete()
        foods = [Foods(**_build_food_payload(row)) for row in rows]
        Foods.objects.bulk_create(foods)

    return ImportResult(csv_path=target_path, created_count=len(rows), cleared_count=cleared_count)


def delete_csv(csv_path: Path | None = None) -> bool:
    target_path = csv_path or DEFAULT_CSV_PATH
    if not target_path.exists():
        return False
    target_path.unlink()
    return True


def csv_snapshot(csv_path: Path | None = None) -> dict[str, object]:
    target_path = csv_path or DEFAULT_CSV_PATH
    if not target_path.exists():
        return {"exists": False, "path": str(target_path), "row_count": 0}

    with target_path.open("r", encoding="utf-8-sig", newline="") as csv_file:
        row_count = max(sum(1 for _ in csv.DictReader(csv_file)), 0)
    stat = target_path.stat()
    return {
        "exists": True,
        "path": str(target_path),
        "row_count": row_count,
        "modified_at": stat.st_mtime,
    }


def parse_stat_count(raw_value: object) -> int:
    text = "" if raw_value is None else str(raw_value).strip()
    if not text or text.lower() == "nan":
        return 0

    compact_text = text.replace(",", "")
    match = re.search(r"(\d+(?:\.\d+)?)", compact_text)
    if match is None:
        return 0

    number = float(match.group(1))
    if "万" in compact_text:
        number *= 10000
    elif "千" in compact_text:
        number *= 1000
    return max(int(number), 0)


def _read_csv_rows(csv_path: Path) -> list[dict[str, str]]:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as csv_file:
        return list(csv.DictReader(csv_file))


def _build_food_payload(row: dict[str, str]) -> dict[str, object]:
    description = clean_text(row.get("描述"))[:255]
    title = clean_text(row.get("标题")) or "未命名菜品"
    return {
        "foodname": title,
        "foodtype": clean_text(row.get("类型")) or "其他",
        "recommend": description,
        "imgurl": clean_text(row.get("图片")),
        "price": _derive_price(title),
        "collect_count": parse_stat_count(row.get("收藏数量")),
        "comment_count": parse_stat_count(row.get("评论数量")),
    }


def _derive_price(seed_text: str) -> int:
    checksum = sum(ord(char) for char in seed_text)
    return 30 + (checksum % 71)


def _first_or_empty(values: list[str]) -> str:
    if not values:
        return ""
    return values[0]
