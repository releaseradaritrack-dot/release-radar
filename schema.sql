-- Release Radar — Phase 2 database schema
-- Run this once in Supabase: Project -> SQL Editor -> New query -> paste all -> Run

-- Signed-in users' saved titles, synced across devices
create table if not exists public.watchlist (
  user_id uuid references auth.users(id) on delete cascade,
  item_id text not null,
  item_title text,
  created_at timestamptz default now(),
  primary key (user_id, item_id)
);

-- Per-user notification settings
create table if not exists public.notification_preferences (
  user_id uuid primary key references auth.users(id) on delete cascade,
  email text not null,
  favorite_industries text[] default '{}',
  favorite_platforms text[] default '{}',
  new_releases boolean default true,
  date_changes boolean default true,
  weekly_digest boolean default true,
  reminder_hours_before int default 24,
  updated_at timestamptz default now()
);

-- Allowlist of admin emails. Add yourself here after running this script:
--   insert into public.admins (email) values ('you@example.com');
create table if not exists public.admins (
  email text primary key
);

-- Admin-curated / manually verified titles (Hoichoi, Chorki, Bangladesh titles
-- TMDB doesn't cover, or corrections to an existing TMDB-sourced title).
-- The site merges this table with catalog.json at load time.
create table if not exists public.manual_titles (
  id text primary key,
  title text not null,
  original_title text,
  type text not null,               -- 'movie' or 'series'
  industry text not null,           -- hollywood | bollywood | bangladesh | international
  platform text,                    -- netflix | prime_video | hoichoi | chorki | theatrical | ...
  release_date date not null,
  release_time text,                -- '19:00' or '' if unconfirmed — never guess
  status text default 'confirmed',  -- confirmed | estimated | rumored | date_tbd | delayed | cancelled
  genres text[] default '{}',
  language text,
  synopsis text,
  poster_url text,
  backdrop_url text,
  trailer_url text,
  official_url text,
  featured boolean default false,
  source text default 'Manually added (admin)',
  created_by text,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

alter table public.watchlist enable row level security;
alter table public.notification_preferences enable row level security;
alter table public.manual_titles enable row level security;
alter table public.admins enable row level security;

-- Users can only see/edit their OWN watchlist and preferences
drop policy if exists "users manage own watchlist" on public.watchlist;
create policy "users manage own watchlist" on public.watchlist
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

drop policy if exists "users manage own prefs" on public.notification_preferences;
create policy "users manage own prefs" on public.notification_preferences
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

-- Everyone (including logged-out visitors) can read manual_titles — it's public site content
drop policy if exists "anyone can read manual titles" on public.manual_titles;
create policy "anyone can read manual titles" on public.manual_titles
  for select using (true);

-- Only emails listed in public.admins can add/edit/delete manual_titles
drop policy if exists "admins can write manual titles" on public.manual_titles;
create policy "admins can write manual titles" on public.manual_titles
  for all using (exists (select 1 from public.admins a where a.email = auth.jwt() ->> 'email'))
  with check (exists (select 1 from public.admins a where a.email = auth.jwt() ->> 'email'));

drop policy if exists "anyone can check admin list" on public.admins;
create policy "anyone can check admin list" on public.admins
  for select using (true);
