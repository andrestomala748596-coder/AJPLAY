#!/usr/bin/env python3
"""Extract a complete M3U/M3U+ playlist from one URL into AJPLAY JSON."""

import argparse
import hashlib
import json
import re
import sys
from collections import OrderedDict
from pathlib import Path
from urllib.parse import urlsplit

import requests

TIMEOUT = (20, 180)
USER_AGENT = "AJPLAY-M3U-Extractor/1.0"


def parse_attributes(value):
    attrs = {}
    pattern = re.compile(r'([A-Za-z0-9_-]+)=(?:"([^"]*)"|([^,\s]*))')
    for match in pattern.finditer(value):
        attrs[match.group(1).lower()] = match.group(2) if match.group(2) is not None else match.group(3)
    return attrs


def stable_id(url, name):
    return hashlib.sha1((url + "\n" + name).encode("utf-8")).hexdigest()[:16]


def parse_playlist(lines):
    entries = []
    pending = None
    for raw in lines:
        line = raw.strip().lstrip("\ufeff")
        if not line:
            continue
        if line.startswith("#EXTINF:"):
            info = line[len("#EXTINF:"):]
            comma = info.find(",")
            metadata = info[:comma] if comma >= 0 else info
            name = info[comma + 1:].strip() if comma >= 0 else ""
            attrs = parse_attributes(metadata)
            pending = {"name": name or attrs.get("tvg-name") or "Sin título", "attrs": attrs}
        elif line.startswith("#"):
            if pending is not None:
                pending.setdefault("extra", []).append(line)
        elif pending is not None and (line.startswith("http://") or line.startswith("https://")):
            attrs = pending["attrs"]
            group = attrs.get("group-title") or "Sin categoría"
            url = line
            sid = stable_id(url, pending["name"])
            entries.append({
                "stream_id": sid,
                "name": pending["name"],
                "title": pending["name"],
                "stream_type": "m3u",
                "stream_icon": attrs.get("tvg-logo", ""),
                "category_id": group,
                "category_name": group,
                "url_directa": url,
                "url": url,
                "tvg_id": attrs.get("tvg-id", ""),
                "tvg_name": attrs.get("tvg-name", ""),
                "tvg_logo": attrs.get("tvg-logo", ""),
                "group_title": group,
                "attributes": attrs,
                "extra_tags": pending.get("extra", []),
            })
            pending = None
    return entries


def main():
    parser = argparse.ArgumentParser(description="Extrae una playlist M3U/M3U+ desde una sola URL.")
    parser.add_argument("--url", required=True, help="URL completa de la playlist M3U/M3U+")
    parser.add_argument("--output", default="catalog.json", help="Archivo JSON de salida")
    args = parser.parse_args()

    parsed = urlsplit(args.url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise SystemExit("ERROR: la URL debe comenzar con http:// o https://")

    print("Descargando playlist M3U...")
    with requests.get(args.url, headers={"User-Agent": USER_AGENT}, stream=True, timeout=TIMEOUT) as response:
        response.raise_for_status()
        response.encoding = response.encoding or "utf-8"
        entries = parse_playlist(response.iter_lines(decode_unicode=True))

    if not entries:
        raise RuntimeError("La URL respondió, pero no se encontraron entradas EXTINF con URL HTTP/HTTPS.")

    groups = OrderedDict()
    for item in entries:
        group = item["group_title"]
        groups.setdefault(group, []).append(item["stream_id"])

    categories = [
        {"category_id": name, "category_name": name, "parent_id": 0, "count": len(ids)}
        for name, ids in groups.items()
    ]
    catalog = {
        "source_type": "m3u",
        "source_url": args.url,
        "total_entries": len(entries),
        "total_categories": len(categories),
        "categories": categories,
        "streams": entries,
    }
    output = Path(args.output)
    output.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Extracción terminada: {len(entries)} entradas, {len(categories)} categorías.")
    print(f"JSON generado: {output}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
