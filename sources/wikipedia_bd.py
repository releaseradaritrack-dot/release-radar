"""
Release Radar — sources/wikipedia_bd.py
=========================================
TMDB has almost no Bangladeshi film coverage, so this module fills that gap
using a real, actively edited, actual source: Wikipedia's
"List of Bangladeshi films of <year>" pages. These are maintained by
Wikipedia's film-project editors and cite news sources (Prothom Alo, The
Daily Star, etc.) for each release date — this is not TMDB, and not a guess.

We read the page's WIKITEXT (the raw markup), not the rendered HTML — the
table structure is much easier to parse reliably from wikitext, and it's
what Wikipedia's own API is built to serve.

WHAT THIS DOES:
  - Fetches "List of Bangladeshi films of <year>" for this year and next
  - Parses the month-by-month release tables (Opening / Title / Director /
    Cast / Production company)
  - Flags Hoichoi / Chorki co-productions as that platform; everything else
    defaults to "theatrical" (this list is Dhallywood cinema releases)
  - Never invents a date — if a row doesn't parse cleanly, it's skipped,
    not guessed

WHAT THIS DOESN'T COVER:
  - Bangladeshi web/TV series (no equivalent structured Wikipedia list
    exists) — keep using manual_additions.json / the admin panel for those
  - Exact release TIMES (Wikipedia doesn't track these — release_time is
    always left blank, same as everywhere else in this project)

If Wikipedia changes this page's table format, parsing may silently return
fewer (or zero) rows for that run rather than crash — check the Actions log
if Bangladesh coverage suddenly drops, and this file is the one to fix.
"""

import re
from datetime import date

import requests

WIKI_API = "https://en.wikipedia.org/w/api.php"
HEADERS = {"User-Agent": "ReleaseRadar/1.0 (personal, non-commercial release tracker)"}

MONTHS = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}


def fetch_wikitext(page_title):
    try:
        resp = requests.get(
            WIKI_API,
            params={"action": "parse", "page": page_title, "format": "json",
                    "formatversion": 2, "prop": "wikitext"},
            headers=HEADERS,
            timeout=20,
        )
        if resp.status_code != 200:
            print(f"Wikipedia fetch failed for '{page_title}': HTTP {resp.status_code}")
            return ""
        data = resp.json()
        if "error" in data:
            print(f"Wikipedia API error for '{page_title}': {data['error'].get('info')}")
            return ""
        return data.get("parse", {}).get("wikitext", "")
    except requests.RequestException as e:
        print(f"Wikipedia fetch error for '{page_title}': {e}")
        return ""


def clean_wiki(text):
    """Strips wikitext markup down to plain, readable text."""
    if not text:
        return ""
    text = re.sub(r"<ref[^>]*?/>", "", text)
    text = re.sub(r"<ref.*?</ref>", "", text, flags=re.S)
    text = re.sub(r"\{\{[^{}]*\}\}", "", text)                      # {{r|ref1}} templates
    text = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]+)\]\]", r"\1", text)   # [[Link|Display]] -> Display
    text = re.sub(r"\[https?://\S+\s+([^\]]+)\]", r"\1", text)      # [http://... label] -> label
    text = re.sub(r"'''?", "", text)                                # bold/italic markers
    text = re.sub(r"<br\s*/?>", ", ", text, flags=re.I)
    text = re.sub(r'rowspan="\d+"\s*\|', "", text)
    text = re.sub(r'colspan="\d+"\s*\|', "", text)
    text = re.sub(r"\s+", " ", text).strip(" |\u2013-")
    return text.strip()


def detect_platform(company_text):
    low = (company_text or "").lower()
    if "hoichoi" in low:
        return "hoichoi"
    if "chorki" in low:
        return "chorki"
    return "theatrical"


def parse_year_page(wikitext, year):
    """Returns a list of normalized release dicts parsed from one year's wikitext."""
    items = []
    if not wikitext:
        return items

    tables = re.findall(r"\{\|.*?\n\|\}", wikitext, flags=re.S)
    for table in tables:
        if "Director" not in table or "Title" not in table:
            continue  # skip the box-office summary table and any unrelated tables

        row_blocks = re.split(r"\n\|-\s*\n?", table)
        current_month = None

        for block in row_blocks:
            block = block.strip()
            if not block or block.startswith("!") or block.startswith("{|"):
                continue
            if block.endswith("|}"):
                block = block[:-2].strip()  # strip the table-close marker, keep the last row's data
            if not block:
                continue

            # Normalize "\n|cell" line-style cells into "||cell" so we can split on one delimiter
            normalized = re.sub(r"\n\s*\|(?!\|)", "||", block)
            raw_cells = [c.strip() for c in normalized.split("||")]
            raw_cells = [c for c in raw_cells if c != ""]
            if not raw_cells:
                continue

            first_clean = clean_wiki(raw_cells[0]).replace(" ", "").upper()
            if first_clean in MONTHS:
                current_month = MONTHS[first_clean]
                raw_cells = raw_cells[1:]

            if current_month is None or not raw_cells:
                continue

            day_text = clean_wiki(raw_cells[0])
            day_match = re.search(r"\d{1,2}", day_text)
            if not day_match:
                continue
            day = int(day_match.group())

            rest = raw_cells[1:]
            title = clean_wiki(rest[0]) if len(rest) > 0 else ""
            director = clean_wiki(rest[1]) if len(rest) > 1 else ""
            cast = clean_wiki(rest[2]) if len(rest) > 2 else ""
            company = clean_wiki(rest[3]) if len(rest) > 3 else ""

            if not title or len(title) > 150:
                continue  # skip anything that didn't parse into a clean title

            try:
                release_date = date(year, current_month, day).isoformat()
            except ValueError:
                continue  # invalid day for that month — malformed row, skip rather than guess

            synopsis_bits = []
            if director:
                synopsis_bits.append(f"Directed by {director}.")
            if cast:
                synopsis_bits.append(f"Starring {cast}.")

            slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:50]
            items.append({
                "id": f"bdwiki-{slug}-{release_date}",
                "tmdb_id": None,
                "type": "movie",
                "industry": "bangladesh",
                "title": title,
                "original_title": title,
                "release_date": release_date,
                "release_time": "",
                "status": "confirmed",
                "genres": [],
                "language": "bn",
                "synopsis": " ".join(synopsis_bits),
                "poster_url": "",
                "backdrop_url": "",
                "popularity": 0,
                "platform": detect_platform(company),
                "source": f"Wikipedia — List of Bangladeshi films of {year} (community-maintained; verify before fully trusting)",
                "official_url": f"https://en.wikipedia.org/wiki/List_of_Bangladeshi_films_of_{year}",
                "trailer_url": "",
            })

    return items


def fetch_bangladesh_films():
    """Entry point called from discover.py. Returns a deduped list of items."""
