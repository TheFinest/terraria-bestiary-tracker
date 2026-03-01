#!/usr/bin/env python3
"""
RUN THIS IN THE ROOT DIRECTORY, NOT HERE.
This was moved to the scripts folder for cleanliness, but should you want to run it,
it should be ran in the root, so it properly populates the asset directory

Download creature sprite images from the Terraria wiki for the bestiary tracker.
Saves images to assets/creatures/{num}.png

Run once to populate the image cache. Re-run at any time to fill in gaps
(already-downloaded files are skipped).
"""

import json
import os
import re
import shutil
import sys
import time
import urllib.request
import urllib.parse

# Import BESTIARY from the main tracker (no side-effects — server only starts in main())
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from terraria_bestiary_tracker import BESTIARY

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR    = os.path.join(SCRIPT_DIR, "assets", "creatures")
WIKI_API   = "https://terraria.wiki.gg/api.php"

HEADERS = {"User-Agent": "TerrariaeBestiaryTracker/1.0 (local bestiary tracker)"}

# Slugs whose wiki file name doesn't follow the standard pattern.
# Maps slug -> exact "File:*.png" title to query (space form).
OVERRIDES: dict[str, str] = {
    "Gem_Squirrel":  "File:Amethyst Squirrel.png",   # representative colour variant
    "Gem_Bunny":     "File:Amethyst Bunny.png",
    "Dragonfly":     "File:Blue Dragonfly.png",
    "Ghost":         "File:Ghost (NPC).png",
    "Slime":         "File:Green Slime.png",   # seasonal costume slime variants
}


def api_imageinfo(file_titles: list[str]) -> dict[str, str]:
    """
    Query imageinfo for a list of 'File:Foo.png' titles (up to 50).
    Returns {sent_title: url} for titles that resolve to an existing file.
    Titles should be passed with spaces (not underscores) as MediaWiki expects.
    """
    params = urllib.parse.urlencode({
        "action": "query",
        "titles": "|".join(file_titles),
        "prop":   "imageinfo",
        "iiprop": "url",
        "format": "json",
    })
    req = urllib.request.Request(WIKI_API + "?" + params, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read())

    # Build map: canonical_title -> sent_title (to recover what we originally sent)
    canonical_to_sent: dict[str, str] = {}
    for n in data.get("query", {}).get("normalized", []):
        canonical_to_sent[n["to"]] = n["from"]
    # For un-normalised titles, canonical == sent
    for t in file_titles:
        if t not in canonical_to_sent.values():
            canonical_to_sent.setdefault(t, t)

    result: dict[str, str] = {}
    for page in data.get("query", {}).get("pages", {}).values():
        if "missing" in page:
            continue
        canonical = page.get("title", "")
        sent      = canonical_to_sent.get(canonical, canonical)
        url       = (page.get("imageinfo") or [{}])[0].get("url")
        if url:
            result[sent] = url   # keyed by what we sent
    return result


def slug_to_file_candidates(slug: str) -> list[str]:
    """
    Return candidate 'File:*.png' titles (space form) to try for this slug.
    Parenthesised slugs get both the full form and the stripped form as fallback.
    URL-encoded characters (e.g. %27 for apostrophe) are decoded first.
    """
    if slug in OVERRIDES:
        return [OVERRIDES[slug]]

    # Decode any URL-encoding in the slug (e.g. Hoppin%27_Jack -> Hoppin'_Jack)
    decoded = urllib.parse.unquote(slug)
    readable = decoded.replace("_", " ")   # MediaWiki uses spaces
    primary  = "File:" + readable + ".png"
    candidates = [primary]
    if "(" in readable:
        stripped = re.sub(r" \([^)]+\)$", "", readable)
        fallback = "File:" + stripped + ".png"
        if fallback != primary:
            candidates.append(fallback)
    return candidates


def download_bytes(url: str) -> bytes:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read()


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)

    # Build slug -> [nums] map (multiple entries can share a wiki page)
    slug_to_nums: dict[str, list[int]] = {}
    for num, _display, slug, _internals, _hm in BESTIARY:
        slug_to_nums.setdefault(slug, []).append(num)

    # Determine which slugs still need downloading
    needed = [
        slug for slug, nums in slug_to_nums.items()
        if not os.path.exists(os.path.join(OUT_DIR, f"{nums[0]}.png"))
    ]

    total_slugs = len(slug_to_nums)
    already     = total_slugs - len(needed)

    if not needed:
        print(f"All {total_slugs} images already downloaded - nothing to do.")
        return

    print(f"Downloading {len(needed)} images  ({already} already cached, {total_slugs} total)")
    print(f"Saving to: {OUT_DIR}\n")

    # Map every candidate file title -> the slug it came from
    # Primary candidates are inserted first; fallbacks only fill gaps
    title_to_slug: dict[str, str] = {}   # sent_title -> slug
    for slug in needed:
        for file_title in slug_to_file_candidates(slug):
            if file_title not in title_to_slug:
                title_to_slug[file_title] = slug

    all_titles    = list(title_to_slug.keys())
    slug_url: dict[str, str] = {}

    # Batch fetch imageinfo (50 titles per request)
    BATCH         = 50
    total_batches = (len(all_titles) + BATCH - 1) // BATCH
    print(f"Querying wiki API ({len(all_titles)} file lookups in {total_batches} batch(es))...")

    for i in range(0, len(all_titles), BATCH):
        batch = all_titles[i : i + BATCH]
        try:
            results = api_imageinfo(batch)
        except Exception as exc:
            print(f"  API error (batch {i//BATCH + 1}): {exc}")
            time.sleep(3)
            continue

        for sent_title, url in results.items():
            slug = title_to_slug.get(sent_title)
            if slug and slug not in slug_url:   # first match wins (primary over fallback)
                slug_url[slug] = url

        if i + BATCH < len(all_titles):
            time.sleep(0.4)

    print(f"  Found URLs for {len(slug_url)}/{len(needed)} slugs\n")

    # Download images
    downloaded = 0
    failed: list[str] = []

    for slug in needed:
        nums = slug_to_nums[slug]
        url  = slug_url.get(slug)

        if not url:
            failed.append(slug)
            continue

        primary_dest = os.path.join(OUT_DIR, f"{nums[0]}.png")
        try:
            data = download_bytes(url)
            with open(primary_dest, "wb") as f:
                f.write(data)

            # Copy to any other entry numbers sharing this wiki page
            for extra_num in nums[1:]:
                extra_dest = os.path.join(OUT_DIR, f"{extra_num}.png")
                if not os.path.exists(extra_dest):
                    shutil.copy(primary_dest, extra_dest)

            downloaded += 1
            pct = int(100 * (already + downloaded) / total_slugs)
            print(f"  [{already + downloaded}/{total_slugs}]  {pct:3d}%  {slug}")
        except Exception as exc:
            print(f"  FAILED: {slug}: {exc}")
            failed.append(slug)

        time.sleep(0.15)   # be polite to the wiki

    print(f"\nFinished: {downloaded} downloaded, {len(failed)} failed.")
    if failed:
        print(f"Failed slugs ({len(failed)}):")
        for s in failed:
            print(f"  {s}")


if __name__ == "__main__":
    main()
