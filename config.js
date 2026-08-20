// Release Radar — Phase 2 config
// Leave these as-is if you only want Phase 1 (no accounts, no admin panel) —
// the site works fine without them, sign-in just stays disabled.
//
// To turn on accounts, synced watchlists, notification preferences, and the
// admin panel: create a free project at https://supabase.com, then paste
// your Project URL and anon public key below (Project Settings -> API).
// The anon key is DESIGNED to be public — it only allows what your Row Level
// Security rules (in supabase/schema.sql) permit. Never paste the
// "service_role" key here; that one must stay a GitHub Actions secret only.

window.SUPABASE_URL = "YOUR_SUPABASE_PROJECT_URL";
window.SUPABASE_ANON_KEY = "YOUR_SUPABASE_ANON_PUBLIC_KEY";
