"""
Release Radar — discover.py
============================
Fetches upcoming movie/series release data from TMDB (The Movie Database),
a free, official-source-backed movie database, and writes it to catalog.json.

WHY TMDB:
- Free API key, no credit card.
- Aggregates official studio/platform-announced release dates — not rumors.
- We NEVER invent a date: if TMDB has no date, we skip the title or mark it
  "Date TBD" rather than guessing.

This script is meant to be run by GitHub Actions on a schedule (see
.github/workflows/discover.yml), not manually. It needs network access,
which your sandbox/computer does not have — but GitHub Actions does.

Required secret: TMDB_API_KEY (set in GitHub repo Settings -> Secrets)
"""

import json
import os
import sys
import time
from datetime import date, datetime, timedelta

import requests

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "sources"))
from wikipedia_bd import fetch_bangladesh_films  # noqa: E402

TMDB_BASE = "https://api.themoviedb.org/3"
API_KEY = os.environ.get("TMDB_API_KEY")

HERE = os.path.dirname(os.path.abspath(__file__))
OPTIONS_PATH = os.path.join(HERE, "options.json")
CATALOG_PATH = os.path.join(HERE, "catalog.json")
MANUAL_PATH = os.path.join(HERE, "manual_additions.json")


def load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def tmdb_get(endpoint, params=None):
    """Single point of contact with TMDB. Retries once on failure."""
    if not API_KEY:
        print("ERROR: TMDB_API_KEY environment variable is not set.", file=sys.stderr)
        sys.exit(1)
    params = dict(params or {})
    params["api_key"] = API_KEY
    for attempt in range(2):
        try:
            resp = requests.get(f"{TMDB_BASE}{endpoint}", params=params, timeout=20)
            if resp.status_code == 200:
                return resp.json()
            print(f"TMDB {endpoint} -> HTTP {resp.status_code}: {resp.text[:200]}", file=sys.stderr)
        except requests.RequestException as e:
            print(f"TMDB request failed: {e}", file=sys.stderr)
        time.sleep(1)
    return {"results": []}


def poster_url(path, size="w500"):
    return f"https://image.tmdb.org/t/p/{size}{path}" if path else ""


def get_watch_providers(media_type, tmdb_id, region="US"):
    """Returns list of provider names TMDB has flagged for this title/region."""
    data = tmdb_get(f"/{media_type}/{tmdb_id}/watch/providers")
    region_data = data.get("results", {}).get(region, {})
    names = set()
    for bucket in ("flatrate", "ads", "free"):
        for p in region_data.get(bucket, []):
            names.add(p.get("provider_name"))
    return sorted(names)


# TMDB's provider names (sourced from JustWatch) don't always match the tidy
# labels in options.json — e.g. it says "Amazon Prime Video", not "Prime Video",
# and "Disney Plus", not "Disney+". Mapping known variants directly here is more
# reliable than a fragile exact-label match.
PROVIDER_NAME_TO_PLATFORM_KEY = {
    "Netflix": "netflix", "Netflix Standard with Ads": "netflix", "Netflix Kids": "netflix",
    "Amazon Prime Video": "prime_video", "Amazon Prime Video with Ads": "prime_video", "Prime Video": "prime_video",
    "Disney Plus": "disney_plus", "Disney+": "disney_plus",
    "Apple TV Plus": "apple_tv", "Apple TV+": "apple_tv",
    "HBO Max": "hbo_max", "Max": "hbo_max",
    "Hulu": "hulu",
    "Paramount Plus": "paramount_plus", "Paramount+": "paramount_plus",
    "Peacock": "peacock", "Peacock Premium": "peacock",
    "Hoichoi": "hoichoi",
    "Chorki": "chorki",
    "BINGE": "binge", "Binge": "binge",
}


def discover_movies(industry_key, cfg, window_start, window_end):
    """Discover upcoming movies for one industry bucket (e.g. hollywood, bollywood)."""
    languages = cfg.get("tmdb_languages") or ([cfg["tmdb_language"]] if cfg.get("tmdb_language") else [None])
    results = []
    for lang in languages:
        page = 1
        while page <= 3:  # cap pages to keep runs fast; raise if you want deeper coverage
            params = {
                "primary_release_date.gte": window_start,
                "primary_release_date.lte": window_end,
                # Popularity-first (not date-first) so genuinely notable upcoming
                # titles surface before obscure zero-poster festival entries.
                "sort_by": "popularity.desc",
                "page": page,
            }
            if lang:
                params["with_original_language"] = lang
            if cfg.get("tmdb_region"):
                params["region"] = cfg["tmdb_region"]
            if cfg.get("tmdb_origin_country"):
                # Filters by actual production country, NOT language — this is what
                # correctly separates Bangladesh from Kolkata/West Bengal (India),
                # since both share the Bengali language code ("bn") on TMDB.
                params["with_origin_country"] = cfg["tmdb_origin_country"]
            data = tmdb_get("/discover/movie", params)
            batch = data.get("results", [])
            if not batch:
                break
            results.extend(batch)
            if page >= data.get("total_pages", 1):
                break
            page += 1
    return results


def discover_tv(industry_key, cfg, window_start, window_end):
    languages = cfg.get("tmdb_languages") or ([cfg["tmdb_language"]] if cfg.get("tmdb_language") else [None])
    results = []
    for lang in languages:
        page = 1
        while page <= 3:
            params = {
                "first_air_date.gte": window_start,
                "first_air_date.lte": window_end,
                "sort_by": "popularity.desc",
                "page": page,
            }
            if lang:
                params["with_original_language"] = lang
            if cfg.get("tmdb_origin_country"):
                params["with_origin_country"] = cfg["tmdb_origin_country"]
            data = tmdb_get("/discover/tv", params)
            batch = data.get("results", [])
            if not batch:
                break
            results.extend(batch)
            if page >= data.get("total_pages", 1):
                break
            page += 1
    return results


def normalize_movie(raw, industry_key, genre_map):
    release_date = raw.get("release_date") or ""
    if not release_date:
        return None  # never invent a date — skip rather than guess
    genres = [genre_map.get(str(g), None) for g in raw.get("genre_ids", [])]
    genres = [g for g in genres if g]
    return {
        "id": f"movie-{raw['id']}",
        "tmdb_id": raw["id"],
        "type": "movie",
        "industry": industry_key,
        "title": raw.get("title") or raw.get("original_title"),
        "original_title": raw.get("original_title"),
        "release_date": release_date,
        "release_time": "",  # TMDB does not provide exact times — left blank on purpose
        "status": "confirmed" if release_date else "date_tbd",
        "genres": genres,
        "language": raw.get("original_language"),
        "synopsis": raw.get("overview") or "",
        "poster_url": poster_url(raw.get("poster_path")),
        "backdrop_url": poster_url(raw.get("backdrop_path"), "w1280"),
        "popularity": raw.get("popularity", 0),
        "platform": "theatrical",  # refined later via watch-provider lookup for near-term titles
        "source": "TMDB",
        "official_url": "",
        "trailer_url": "",
    }


def normalize_tv(raw, industry_key, genre_map):
    release_date = raw.get("first_air_date") or ""
    if not release_date:
        return None
    genres = [genre_map.get(str(g), None) for g in raw.get("genre_ids", [])]
    genres = [g for g in genres if g]
    return {
        "id": f"tv-{raw['id']}",
        "tmdb_id": raw["id"],
        "type": "series",
        "industry": industry_key,
        "title": raw.get("name") or raw.get("original_name"),
        "original_title": raw.get("original_name"),
        "release_date": release_date,
        "release_time": "",
        "status": "confirmed" if release_date else "date_tbd",
        "genres": genres,
        "language": raw.get("original_language"),
        "synopsis": raw.get("overview") or "",
        "poster_url": poster_url(raw.get("poster_path")),
        "backdrop_url": poster_url(raw.get("backdrop_path"), "w1280"),
        "popularity": raw.get("popularity", 0),
        "platform": "ott",
        "source": "TMDB",
        "official_url": "",
        "trailer_url": "",
    }


def dedupe(items):
    seen = {}
    for it in items:
        seen[it["id"]] = it  # last write wins; fine since fields are identical per id
    return list(seen.values())


def main():
    options = load_json(OPTIONS_PATH, {})
    industries = options.get("industries", {})
    genre_map_movie = options.get("genres_movie", {})
    genre_map_tv = options.get("genres_tv", {})
    lookahead = options.get("site", {}).get("lookahead_days", 120)

    today = date.today()
    window_start = today.isoformat()
    window_end = (today + timedelta(days=lookahead)).isoformat()

    all_items = []

    for industry_key, cfg in industries.items():
        print(f"Fetching movies for {industry_key}...")
        raw_movies = discover_movies(industry_key, cfg, window_start, window_end)
        for raw in raw_movies:
            norm = normalize_movie(raw, industry_key, genre_map_movie)
            if norm:
                all_items.append(norm)

        print(f"Fetching series for {industry_key}...")
        raw_tv = discover_tv(industry_key, cfg, window_start, window_end)
        for raw in raw_tv:
            norm = normalize_tv(raw, industry_key, genre_map_tv)
            if norm:
                all_items.append(norm)

    all_items = dedupe(all_items)

    # Bangladesh: TMDB barely covers Dhallywood, so pull real release dates
    # from Wikipedia's editor-maintained "List of Bangladeshi films" pages.
    print("Fetching Bangladesh films from Wikipedia...")
    try:
        bd_items = fetch_bangladesh_films()
        print(f"Wikipedia BD: {len(bd_items)} titles")
        all_items.extend(bd_items)
        all_items = dedupe(all_items)
    except Exception as e:
        # Never let a Wikipedia format change take down the whole sync —
        # TMDB data still gets written even if this source fails this run.
        print(f"Wikipedia BD source failed this run (skipping, will retry next sync): {e}", file=sys.stderr)

    # Look up the REAL streaming platform (Netflix, Apple TV+, HBO/Max, etc.) for
    # every TMDB-sourced item — previously this only ran for titles releasing
    # within 30 days, so almost everything else sat under a generic
    # "Theatrical"/"Streaming" label instead of the actual service. Region is
    # matched to the industry so we check the market that matters (US for
    # Hollywood/international, IN for Bollywood, BD for Bangladesh).
    region_by_industry = {k: (v.get("tmdb_region") or "US") for k, v in industries.items()}
    lookups = [i for i in all_items if i.get("tmdb_id")]
    print(f"Looking up real streaming platforms for {len(lookups)} titles...")
    for n, item in enumerate(lookups, 1):
        media_type = "movie" if item["type"] == "movie" else "tv"
        region = region_by_industry.get(item["industry"], "US")
        names = get_watch_providers(media_type, item["tmdb_id"], region=region)
        for name in names:
            if name in PROVIDER_NAME_TO_PLATFORM_KEY:
                item["platform"] = PROVIDER_NAME_TO_PLATFORM_KEY[name]
                break
        if n % 50 == 0:
            print(f"  ...{n}/{len(lookups)} platform lookups done")

    # Merge manually curated titles (Hoichoi/Chorki/Bangladesh titles TMDB lacks)
    manual = load_json(MANUAL_PATH, [])
    for m in manual:
        if "_comment" in m:
            continue
        m = dict(m)
        m["id"] = m.get("id") or f"manual-{abs(hash(m['title'] + m['release_date']))}"
        m["tmdb_id"] = None
        m["source"] = m.get("source", "Manually added")
        all_items.append(m)

    all_items.sort(key=lambda i: i["release_date"])

    catalog = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "window_start": window_start,
        "window_end": window_end,
        "count": len(all_items),
        "items": all_items,
    }

    with open(CATALOG_PATH, "w", encoding="utf-8") as f:
        json.dump(catalog, f, indent=2, ensure_ascii=False)

    print(f"Wrote {len(all_items)} items to catalog.json")


if __name__ == "__main__":
    main()
