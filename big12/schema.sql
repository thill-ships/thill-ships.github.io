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

-- One row per season: who you are tracking, and what the two confident calls
-- are worth. A coin flip is always 50%, and each call's mirror image applies to
-- the losing side, so these two numbers cover all five levels.
create table if not exists b12_settings (
  season      int primary key,
  contenders  text[] not null default '{}',    -- ESPN team ids, in board order
  strong_prob numeric not null default 0.80    -- what "should win" is worth
                check (strong_prob > 0.5 and strong_prob < 1),
  lean_prob   numeric not null default 0.65    -- what "lean" is worth
                check (lean_prob > 0.5 and lean_prob < 1),
  updated_at  timestamptz not null default now()
);

-- Upgrading from the three-level board (one "likely" setting). Safe to re-run.
alter table b12_settings add column if not exists strong_prob numeric not null default 0.80;
alter table b12_settings add column if not exists lean_prob   numeric not null default 0.65;


-- One row per game you have an opinion about. A game with no row here falls
-- back to the betting line, so an untouched board is already a real forecast.
--
-- The prediction is stored per GAME, not per team, so BYU-Utah can never be
-- "BYU likely wins" on one row and "Utah likely wins" on the other.
create table if not exists b12_predictions (
  season       int  not null,
  game_id      text not null,                  -- ESPN event id (pickem_games.id)
  pick_team_id text,                           -- winner you expect; null = 50-50
  strength     text not null default 'strong'
                 check (strength in ('strong','lean','tossup','auto','likely')),
                 -- strong: pick_team_id should win
                 -- lean:   pick_team_id is the softer call
                 -- tossup: a coin flip, pick_team_id is null
                 -- auto:   no opinion; the betting line stands. Only ever stored
                 --         so a note can outlive the opinion that came with it.
                 -- likely: what "strong" was called on the three-level board.
                 --         Accepted so old rows keep working; never written now.
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
-- Season props: the once-a-year guesses about BYU.
--
-- These live in their OWN app at /props/, because this is the one part of the
-- system where more than two people take part, and everybody needs their own
-- answer. So unlike the rest of the board, /props/ has real accounts.
--
-- The War Room only ever reads them. It is a window, not a voting booth.
--
-- The questions are written by the War Room editors; the answers belong to the
-- people who signed up.
-- ---------------------------------------------------------------------------

-- One row per person playing. Created by the props app on first sign-in.
create table if not exists b12_prop_players (
  user_id      uuid primary key references auth.users(id) on delete cascade,
  display_name text not null,
  email        text,
  created_at   timestamptz not null default now()
);

-- One question. `auto` is the small set the app can answer for itself out of
-- the schedule; everything else gets typed in as the season goes. `actual`
-- doubles as "where it stands right now" until `settled` is set, at which point
-- it stops moving and the closest answer wins.
create table if not exists b12_props (
  id        bigint generated always as identity primary key,
  season    int  not null,
  sort      int  not null default 0,
  question  text not null,                  -- "LJ Martin rushing yards"
  detail    text,                           -- an optional clarifier
  kind      text not null default 'number'
              check (kind in ('number','choice')),
  unit      text,                           -- "yards", "TDs", "wins"
  options   text[],                         -- the menu, when kind = 'choice'
  -- How this question answers itself. The first five come off the schedule and
  -- are worked out in the browser. The rest are filled in by the stats job,
  -- which reads BYU's box scores; those need auto_player, except the four
  -- "leader" keys, which work out for themselves who is leading.
  auto      text
              check (auto is null or auto in
                     ('wins','losses','conf_wins','conf_losses','blowouts',
                      'pass_yds','pass_td','rush_yds','rush_td','long_rush',
                      'rec_yds','rec_td','long_rec','ints','sacks','tackles',
                      'rec_leader','rec_leader_yds','int_leader','int_leader_ints',
                      'team_ints','team_sacks')),
  auto_player text,                         -- the athlete, as ESPN spells them
  min_val   numeric,                        -- sanity bounds for a number answer:
  max_val   numeric,                        -- nobody wins 14 Big 12 games
  whole     boolean not null default true,  -- whole numbers only?
  actual    numeric,                        -- number props: the running total
  actual_choice text,                       -- choice props: what happened
  settled   boolean not null default false,
  created_at timestamptz not null default now()
);

-- Added with the bounds; safe to re-run.
alter table b12_props add column if not exists min_val numeric;
alter table b12_props add column if not exists max_val numeric;
alter table b12_props add column if not exists whole   boolean not null default true;
alter table b12_props add column if not exists auto_player text;

-- Widening the set of things a question can answer for itself. Safe to re-run.
alter table b12_props drop constraint if exists b12_props_auto_check;
alter table b12_props add  constraint b12_props_auto_check check (auto is null or auto in
  ('wins','losses','conf_wins','conf_losses','blowouts',
   'pass_yds','pass_td','rush_yds','rush_td','long_rush',
   'rec_yds','rec_td','long_rec','ints','sacks','tackles',
   'rec_leader','rec_leader_yds','int_leader','int_leader_ints',
   'team_ints','team_sacks'));
create index if not exists b12_props_season_idx on b12_props (season, sort, id);

-- One row per person per question.
create table if not exists b12_prop_picks (
  user_id    uuid   not null references auth.users(id) on delete cascade,
  prop_id    bigint not null references b12_props(id) on delete cascade,
  value      numeric,                       -- number props
  choice     text,                          -- choice props
  updated_at timestamptz not null default now(),
  primary key (user_id, prop_id)
);

-- Locking in is how you buy the right to see everyone else's numbers, and it
-- is deliberately irreversible: there is no update or delete policy below.
create table if not exists b12_prop_locks (
  user_id   uuid not null references auth.users(id) on delete cascade,
  season    int  not null,
  locked_at timestamptz not null default now(),
  primary key (user_id, season)
);

create or replace function b12_is_locked_in(p_user uuid, p_season int)
returns boolean
language sql stable security definer set search_path = public as $$
  select exists (select 1 from b12_prop_locks
                 where user_id = p_user and season = p_season);
$$;

-- The season each prop belongs to, for the policies below.
create or replace function b12_prop_season(p_prop bigint)
returns int
language sql stable security definer set search_path = public as $$
  select season from b12_props where id = p_prop;
$$;


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
alter table b12_props        enable row level security;
alter table b12_prop_picks   enable row level security;
alter table b12_prop_players enable row level security;
alter table b12_prop_locks   enable row level security;

drop policy if exists b12_settings_all    on b12_settings;
drop policy if exists b12_predictions_all on b12_predictions;
drop policy if exists b12_snapshots_read  on b12_snapshots;
drop policy if exists b12_snapshots_write on b12_snapshots;
drop policy if exists b12_snapshots_del   on b12_snapshots;
drop policy if exists b12_props_read      on b12_props;
drop policy if exists b12_props_write     on b12_props;
drop policy if exists b12_players_read    on b12_prop_players;
drop policy if exists b12_players_write   on b12_prop_players;
drop policy if exists b12_players_update  on b12_prop_players;
drop policy if exists b12_picks_read      on b12_prop_picks;
drop policy if exists b12_picks_insert    on b12_prop_picks;
drop policy if exists b12_picks_update    on b12_prop_picks;
drop policy if exists b12_picks_delete    on b12_prop_picks;
drop policy if exists b12_locks_read      on b12_prop_locks;
drop policy if exists b12_locks_insert    on b12_prop_locks;

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

-- Anyone signed in can read the questions; only the War Room writes them.
create policy b12_props_read on b12_props
  for select to authenticated using (true);
create policy b12_props_write on b12_props
  for all to authenticated using (b12_is_editor()) with check (b12_is_editor());

-- The field is public to the field: the results table needs everyone's name.
create policy b12_players_read on b12_prop_players
  for select to authenticated using (true);
create policy b12_players_write on b12_prop_players
  for insert to authenticated with check (auth.uid() = user_id);
create policy b12_players_update on b12_prop_players
  for update to authenticated
  using (auth.uid() = user_id) with check (auth.uid() = user_id);

-- You always see your own answers. You see somebody else's when you have BOTH
-- locked in -- mutual disclosure, so nobody reads the room while their own
-- numbers are still soft.
--
-- The War Room's shared login is the exception: it sees any answer that has
-- been locked in, because it is the scoreboard. It cannot see a soft one.
create policy b12_picks_read on b12_prop_picks
  for select to authenticated using (
    user_id = auth.uid()
    or (
      b12_is_locked_in(b12_prop_picks.user_id, b12_prop_season(prop_id))
      and (
        b12_is_editor()
        or b12_is_locked_in(auth.uid(), b12_prop_season(prop_id))
      )
    )
  );

-- Your answers are yours, and only until you lock in.
create policy b12_picks_insert on b12_prop_picks
  for insert to authenticated with check (
    user_id = auth.uid() and not b12_is_locked_in(auth.uid(), b12_prop_season(prop_id)));
create policy b12_picks_update on b12_prop_picks
  for update to authenticated
  using      (user_id = auth.uid() and not b12_is_locked_in(auth.uid(), b12_prop_season(prop_id)))
  with check (user_id = auth.uid() and not b12_is_locked_in(auth.uid(), b12_prop_season(prop_id)));
create policy b12_picks_delete on b12_prop_picks
  for delete to authenticated
  using (user_id = auth.uid() and not b12_is_locked_in(auth.uid(), b12_prop_season(prop_id)));

-- Who has locked in is public -- it is what gates everything else.
create policy b12_locks_read on b12_prop_locks
  for select to authenticated using (true);

-- You may only lock yourself in, and only once every question is answered.
-- Locking in with blanks is just volunteering for last place. There is
-- deliberately no update or delete policy.
create policy b12_locks_insert on b12_prop_locks
  for insert to authenticated with check (
    user_id = auth.uid()
    and (select count(*) from b12_props p where p.season = b12_prop_locks.season)
      = (select count(*) from b12_prop_picks pk
         join b12_props p2 on p2.id = pk.prop_id
         where pk.user_id = auth.uid() and p2.season = b12_prop_locks.season
           and (pk.value is not null or pk.choice is not null))
  );


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
  begin
    alter publication supabase_realtime add table b12_props;
  exception when duplicate_object then null;
  end;
  begin
    alter publication supabase_realtime add table b12_prop_picks;
  exception when duplicate_object then null;
  end;
  begin
    alter publication supabase_realtime add table b12_prop_locks;
  exception when duplicate_object then null;
  end;
end $$;
