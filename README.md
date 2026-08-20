# Release Radar — Phase 1 Setup (No Coding Required)

This turns on a real, auto-updating movie & series release tracker: a premium
dark/glassmorphism website that refreshes itself every 6 hours and emails you
when something new is announced or a release date changes.

Total time: about 15 minutes. Follow the steps in order.

---

## Step 1 — Create a GitHub account
Skip if you already have one: https://github.com/signup

## Step 2 — Create a new repository
1. Go to https://github.com/new
2. Repository name: `release-radar`
3. Keep it **Public** (required for the free GitHub Pages website — don't worry,
   your API keys and passwords never go in the code, only in GitHub's encrypted
   "Secrets" vault, see Step 5)
4. Click **Create repository**

## Step 3 — Upload these files
On the new repository's page, click **"uploading an existing file"**
(or **Add file → Upload files**).

Drag in **everything** from this project folder — including the hidden
`.github` folder — then click **Commit changes**.

Your repository should look like this:

```
release-radar/
├── index.html
├── admin.html
├── config.js
├── discover.py
├── monitor.py
├── requirements.txt
├── options.json
├── catalog.json
├── state.json
├── changelog.json
├── manual_additions.json
├── supabase/
│   └── schema.sql
└── .github/
    └── workflows/
        └── discover.yml
```

(`admin.html`, `config.js`, and `supabase/schema.sql` are for Phase 2 —
Step 9 onward, further down this page. You can upload them now even if
you're doing Phase 1 first; they just sit unused until then.)

## Step 4 — Get a free TMDB API key (this is your real movie data source)
TMDB (The Movie Database) is a free, official-source-backed movie/TV database —
this is what fetches real release dates so nothing is ever guessed.

1. Go to https://www.themoviedb.org/signup and create a free account
2. Go to https://www.themoviedb.org/settings/api and request an API key
   (choose "Developer", the form is quick — personal project is a fine answer)
3. Copy the **API Key (v3 auth)** value — you'll paste it in Step 6

## Step 5 — Create a Gmail "App Password" (lets the robot email you)
1. Go to https://myaccount.google.com/security and turn on **2-Step Verification**
   if it isn't already on
2. Go to https://myaccount.google.com/apppasswords
3. Create a new app password (name it "Release Radar")
4. Copy the 16-character password — you'll paste it in Step 6

## Step 6 — Add your secrets to GitHub
In your repository: **Settings → Secrets and variables → Actions → New repository secret**.
Add each of these one at a time:

| Secret name | Value |
|---|---|
| `TMDB_API_KEY` | the key from Step 4 |
| `GMAIL_ADDRESS` | your Gmail address |
| `GMAIL_APP_PASSWORD` | the 16-character password from Step 5 |
| `OWNER_EMAIL` | where you want alerts sent (can be the same Gmail address) |

Your keys are never visible in the code and never shown on the website.

## Step 7 — Turn on the website (GitHub Pages)
1. **Settings → Pages**
2. Under "Build and deployment", set **Source** to **Deploy from a branch**
3. Branch: `main`, folder: `/ (root)` → **Save**
4. After ~1 minute, your site is live at:
   `https://YOUR-USERNAME.github.io/release-radar/`

## Step 8 — Run the first data sync
1. Go to the **Actions** tab in your repository
2. Click **"Update Release Radar Data"** on the left
3. Click **Run workflow → Run workflow**
4. Wait 1–2 minutes, then refresh your website — real upcoming releases should
   now appear instead of the sample preview cards

From here on, it runs itself every 6 hours automatically. You'll get an email
whenever something new is announced or a date changes.

---

## Bangladesh coverage — how it actually works now
TMDB (the main data source) has almost no Bangladeshi film data, so this
project also pulls from a second, real source automatically: Wikipedia's
**"List of Bangladeshi films of [year]"** pages. These are actively
maintained by Wikipedia's film editors, cite real news sources (Prothom
Alo, The Daily Star, etc.) for each date, and even flag when a film is a
Hoichoi or Chorki co-production — `discover.py` reads this automatically
every sync, no typing required from you. This covers **Dhallywood theatrical
films** well.

**What this still can't cover automatically:** Bangladeshi **web/TV
series** (Hoichoi/Chorki originals) — no equivalent structured public list
exists for these anywhere, so there's nothing free and reliable to pull
from automatically. For those, use the admin panel (Part B, `/admin.html`)
to add them by hand once you know about them — it takes under a minute per
title and they'll appear on the site exactly like automatic ones, with full
countdown/calendar/watchlist support. You can also still edit
`manual_additions.json` directly if you haven't set up Part B yet.

## Adding Hoichoi / Chorki / any other title by hand

---

## Phase 2 — Accounts, synced watchlist, notification preferences, admin panel

This turns on real sign-in (magic-link email, no passwords), a watchlist and
notification preferences that follow the user across devices, and an admin
page to add/verify titles TMDB doesn't cover. It uses **Supabase** — a free
hosted Postgres database with built-in accounts, which is what lets a fully
static GitHub Pages site have real logins without you running a server.

If you skip this section, the site still works exactly as in Phase 1 —
sign-in just stays off.

### Step 9 — Create a free Supabase project
1. Go to https://supabase.com and sign up
2. **New project** → name it `release-radar` → set a database password
   (save it somewhere; you won't need it day-to-day) → choose the region
   closest to you → **Create new project** (takes ~2 minutes to provision)

### Step 10 — Set up the database
1. In your Supabase project: **SQL Editor → New query**
2. Open `supabase/schema.sql` from this project, copy all of it, paste it in,
   click **Run**
3. Still in SQL Editor, run one more line to make yourself an admin
   (replace with your real email):
   ```sql
   insert into public.admins (email) values ('you@example.com');
   ```

### Step 11 — Turn on email sign-in
1. **Authentication → Providers → Email** — make sure it's enabled
   (it is by default)
2. **Authentication → URL Configuration** → set **Site URL** to your GitHub
   Pages address (`https://YOUR-USERNAME.github.io/release-radar/`) so the
   magic-link email sends people back to the right place

### Step 12 — Connect the site to Supabase
1. In Supabase: **Project Settings → API**
2. Copy the **Project URL** and the **anon / public key**
3. Open `config.js` in your repository, paste them in, commit the change
4. Also copy the **service_role** key (different from the anon key — keep this
   one secret) — add it to GitHub as a repository secret named
   `SUPABASE_SERVICE_ROLE_KEY`, and add `SUPABASE_URL` as a secret too
   (**Settings → Secrets and variables → Actions → New repository secret**,
   same place as Step 6)

That's it — reload your site. The account icon in the top-right now opens
real sign-in, preferences, and a synced watchlist. Visit `/admin.html` on
your site to add or verify titles (sign in with the email you added to
`admins` in Step 10).

### A note on Google Calendar
Phase 1's "Add to Calendar" button (a Google Calendar link, no login needed)
is still what's used everywhere, including in Phase 2. A true *auto-syncing*
calendar connection — where an event updates itself the moment a release
date changes — is possible, but it needs a registered Google Cloud OAuth app
and long-lived stored credentials, and Google's own token-expiry rules for
personal/unverified apps make that sync quietly stop working after about a
week unless the app goes through Google's verification review. Given that
overhead versus the benefit over the one-click link (which never expires and
needs no setup), I've left that out for now. Say the word if you'd like it
built anyway — it's doable, just a heavier lift.

## What Phase 1 does and doesn't include
**Included, fully working:** cinematic homepage, search & filters, all the
release-window shelves (Today / This Week / This Month / Most Anticipated /
Newly Announced / Recently Updated), per-title details, countdowns,
Add-to-Google-Calendar (via Google's own event link — no login setup needed),
browser watchlist, automatic 6-hourly data refresh, email alerts for new
titles and date changes.

**Added in Phase 2 (see above), all free:** real sign-in, a watchlist and
notification preferences that sync across devices, and a click-and-edit
admin page at `/admin.html` for adding/verifying titles.

**Still not included — the one piece that genuinely needs a heavier,
ongoing setup:**
- **True Google Calendar *sync*** (an event auto-updates itself when a
  release date changes, instead of a one-time "add" link) — explained in
  the note above. Everything else in the original spec is built.
