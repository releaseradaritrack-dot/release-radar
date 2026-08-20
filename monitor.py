"""
Release Radar — monitor.py
============================
Run AFTER discover.py. Compares the freshly generated catalog.json against
state.json (what we saw last time) to find:
  - Newly announced titles
  - Titles whose release_date changed
Then:
  - Appends changes to changelog.json (permanent history)
  - Emails a summary to OWNER_EMAIL via Gmail SMTP, if changes exist

Required GitHub secrets:
  GMAIL_ADDRESS     — the Gmail account sending mail
  GMAIL_APP_PASSWORD — a Gmail "App Password" (not your normal password)
  OWNER_EMAIL       — fallback address if no one has an account yet

Optional (Phase 2 — personalized per-user emails via Supabase accounts):
  SUPABASE_URL              — same URL you put in config.js
  SUPABASE_SERVICE_ROLE_KEY — from Supabase Project Settings -> API.
                               NEVER put this one in config.js — it bypasses
                               Row Level Security and must stay a GitHub
                               secret only, never exposed to the browser.
If the Supabase secrets aren't set, this script quietly falls back to
Phase 1 behaviour: one email to OWNER_EMAIL. Nothing breaks either way.
"""

import json
import os
import smtplib
from datetime import datetime
from email.mime.text import MIMEText

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
CATALOG_PATH = os.path.join(HERE, "catalog.json")
STATE_PATH = os.path.join(HERE, "state.json")
CHANGELOG_PATH = os.path.join(HERE, "changelog.json")

GMAIL_ADDRESS = os.environ.get("GMAIL_ADDRESS")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")
OWNER_EMAIL = os.environ.get("OWNER_EMAIL", GMAIL_ADDRESS)

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")


def fetch_subscribers():
    """Returns list of notification_preferences rows, or [] if Supabase isn't configured."""
    if not (SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY):
        return []
    try:
        resp = requests.get(
            f"{SUPABASE_URL}/rest/v1/notification_preferences",
            params={"select": "*"},
            headers={
                "apikey": SUPABASE_SERVICE_ROLE_KEY,
                "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
            },
            timeout=15,
        )
        if resp.status_code == 200:
            return resp.json()
        print(f"Supabase fetch failed: HTTP {resp.status_code}: {resp.text[:200]}")
    except requests.RequestException as e:
        print(f"Supabase fetch error: {e}")
    return []


def relevant_to(pref, item):
    favs_ind = pref.get("favorite_industries") or []
    favs_plat = pref.get("favorite_platforms") or []
    if not favs_ind and not favs_plat:
        return True  # no preference set = interested in everything
    return item.get("industry") in favs_ind or item.get("platform") in favs_plat


def load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def diff_catalog(old_items_by_id, new_items):
    new_titles = []
    date_changes = []
    for item in new_items:
        old = old_items_by_id.get(item["id"])
        if old is None:
            new_titles.append(item)
        elif old.get("release_date") != item.get("release_date"):
            date_changes.append({
                "id": item["id"],
                "title": item["title"],
                "old_date": old.get("release_date"),
                "new_date": item.get("release_date"),
                "detected_at": datetime.utcnow().isoformat() + "Z",
            })
    return new_titles, date_changes


def send_email(subject, body_html, to_address):
    if not (GMAIL_ADDRESS and GMAIL_APP_PASSWORD and to_address):
        print("Email not configured (missing secrets) — skipping send.")
        return
    msg = MIMEText(body_html, "html")
    msg["Subject"] = subject
    msg["From"] = GMAIL_ADDRESS
    msg["To"] = to_address
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_ADDRESS, [to_address], msg.as_string())
    print(f"Email sent to {to_address}")


def build_email_body(new_titles, date_changes):
    parts = ["<h2>Release Radar update</h2>"]
    if new_titles:
        parts.append("<h3>Newly announced</h3><ul>")
        for t in new_titles[:50]:
            parts.append(f"<li><b>{t['title']}</b> — {t['release_date']} ({t['industry']})</li>")
        parts.append("</ul>")
    if date_changes:
        parts.append("<h3>Release date changed</h3><ul>")
        for c in date_changes:
            parts.append(
                f"<li><b>{c['title']}</b>: {c['old_date']} &rarr; <b>{c['new_date']}</b></li>"
            )
        parts.append("</ul>")
    return "".join(parts)


def main():
    catalog = load_json(CATALOG_PATH, {"items": []})
    new_items = catalog.get("items", [])

    state = load_json(STATE_PATH, {"items": []})
    old_items_by_id = {i["id"]: i for i in state.get("items", [])}

    new_titles, date_changes = diff_catalog(old_items_by_id, new_items)

    if new_titles or date_changes:
        changelog = load_json(CHANGELOG_PATH, [])
        changelog.append({
            "run_at": datetime.utcnow().isoformat() + "Z",
            "new_titles": [{"id": t["id"], "title": t["title"], "release_date": t["release_date"]} for t in new_titles],
            "date_changes": date_changes,
        })
        save_json(CHANGELOG_PATH, changelog)

        subscribers = fetch_subscribers()
        if subscribers:
            new_by_id = {t["id"]: t for t in new_titles}
            for pref in subscribers:
                want_new = pref.get("new_releases", True)
                want_changes = pref.get("date_changes", True)
                my_new = [t for t in new_titles if want_new and relevant_to(pref, t)]
                my_changes = [
                    c for c in date_changes
                    if want_changes and relevant_to(pref, new_by_id.get(c["id"], {}))
                ]
                if my_new or my_changes:
                    body = build_email_body(my_new, my_changes)
                    send_email(
                        f"Release Radar: {len(my_new)} new, {len(my_changes)} date change(s)",
                        body,
                        pref.get("email"),
                    )
        else:
            # Phase 1 fallback — no accounts set up yet, one email to the owner
            body = build_email_body(new_titles, date_changes)
            send_email(f"Release Radar: {len(new_titles)} new, {len(date_changes)} date change(s)", body, OWNER_EMAIL)
    else:
        print("No changes detected.")

    # state.json always mirrors the latest catalog, for next run's comparison
    save_json(STATE_PATH, {"items": new_items, "updated_at": datetime.utcnow().isoformat() + "Z"})


if __name__ == "__main__":
    main()
