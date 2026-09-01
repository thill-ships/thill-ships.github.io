-- ============================================================================
-- Big 12 War Room -- database schema
--
-- Run this in the SAME Supabase project the pick'em app uses:
--   Supabase Dashboard -> SQL Editor -> New query -> paste this whole file -> Run
--
-- Safe to re-run. Every statement is idempotent; policies are dropped only so
-- they can be recreated. No table, column, or row is ever dropped.
--
-- This app deliberately does NOT keep its own copy of the schedule. It reads
-- `pickem_games`, which the existing "Pick'em -- sync games" GitHub Action
-- already refreshes every two hours with every Big 12 game, score, and spread.
-- One sync job, two apps.
-- ============================================================================


-- ---------------------------------------------------------------------------
-- Who is allowed to edit
--
-- There are no per-person accounts here. Both of you sign in with ONE shared
-- email and password, and this function is the whole access rule. Put that
-- address in the array below; add a second only if you want a personal login
-- to work too.
-- ---------------------------------------------------------------------------
create or replace function b12_is_editor()
returns boolean
language sql stable as $$
  select coalesce(auth.jwt() ->> 'email', '') = any (array[
    'warroom@thill-ships.app'          -- <-- the shared account (see SETUP.md)
  ]);
$$;


-- ---------------------------------------------------------------------------
-- Tables
-- ---------------------------------------------------------------------------

-- One row per season: who you are tracking, and how confident "likely" means.
create table if not exists b12_settings (
  season      int primary key,
  contenders  text[] not null default '{}',    -- ESPN team ids, in board order
  likely_prob numeric not null default 0.75    -- win probability behind "likely"
                check (likely_prob > 0.5 and likely_prob < 1),
  updated_at  timestamptz not null default now()
);

-- One row per game you have an opinion about. A game with no row here falls
-- back to the betting line, so an untouched board is already a real forecast.
--
-- The prediction is stored per GAME, not per team, so BYU-Utah can never be
-- "BYU likely wins" on one row and "Utah likely wins" on the other.
create table if not exists b12_predictions (
  season       int  not null,
  game_id      text not null,                  -- ESPN event id (pickem_games.id)
  pick_team_id text,                           -- winner you expect; null = 50-50
  strength     text not null default 'likely'
                 check (strength in ('likely','tossup','auto')),
                 -- likely: you expect pick_team_id to win
                 -- tossup: a 50-50, pick_team_id is null
                 -- auto:   no opinion; the betting line stands. Only ever stored
                 --         so a note can outlive the opinion that came with it.
  note         text,                           -- "starting QB is out", etc.
  updated_at   timestamptz not null default now(),
  primary key (season, game_id)
);

-- The point of the whole thing: what the board looked like on a given Monday.
-- The payload is SELF-CONTAINED -- it carries the game results as they stood at
-- the time, so a snapshot can be re-rendered exactly as you saw it, rather than
-- being re-scored against results that had not happened yet.
create table if not exists b12_snapshots (
  id       bigint generated always as identity primary key,
  season   int not null,
  week     int,                                -- the week it was taken during
  taken_at timestamptz not null default now(),
  label    text,                               -- "Week 5" or whatever you type
  note     text,                               -- Monday-meeting notes
  source   text not null default 'app'         -- app | auto
             check (source in ('app','auto')),
  payload  jsonb not null
);
create index if not exists b12_snapshots_season_idx
  on b12_snapshots (season, taken_at desc);


-- ---------------------------------------------------------------------------
-- Row Level Security
--
-- Everything is gated on the shared account. The service_role key used by the
-- weekly snapshot Action bypasses all of it, which is how the automatic
-- Monday snapshot gets written even when nobody opens the page.
-- ---------------------------------------------------------------------------

alter table b12_settings    enable row level security;
alter table b12_predictions enable row level security;
alter table b12_snapshots   enable row level security;

drop policy if exists b12_settings_all    on b12_settings;
drop policy if exists b12_predictions_all on b12_predictions;
drop policy if exists b12_snapshots_read  on b12_snapshots;
drop policy if exists b12_snapshots_write on b12_snapshots;
drop policy if exists b12_snapshots_del   on b12_snapshots;

create policy b12_settings_all on b12_settings
  for all to authenticated using (b12_is_editor()) with check (b12_is_editor());

create policy b12_predictions_all on b12_predictions
  for all to authenticated using (b12_is_editor()) with check (b12_is_editor());

create policy b12_snapshots_read on b12_snapshots
  for select to authenticated using (b12_is_editor());
create policy b12_snapshots_write on b12_snapshots
  for insert to authenticated with check (b12_is_editor());
-- Snapshots are history, so there is no UPDATE policy: a saved week cannot be
-- quietly rewritten later. Deleting an obvious mistake is still allowed.
create policy b12_snapshots_del on b12_snapshots
  for delete to authenticated using (b12_is_editor());


-- ---------------------------------------------------------------------------
-- Realtime: when one of you flips a game, it moves on the other's screen.
-- ---------------------------------------------------------------------------

do $$
begin
  begin
    alter publication supabase_realtime add table b12_predictions;
  exception when duplicate_object then null;
  end;
  begin
    alter publication supabase_realtime add table b12_settings;
  exception when duplicate_object then null;
  end;
end $$;
