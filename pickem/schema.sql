-- ============================================================================
-- Big 12 Pick'em -- database schema
--
-- Run this ONCE in a brand-new Supabase project:
--   Supabase Dashboard -> SQL Editor -> New query -> paste this whole file -> Run
--
-- Safe to re-run: every statement is idempotent.
-- ============================================================================


-- ---------------------------------------------------------------------------
-- Tables
-- ---------------------------------------------------------------------------

-- One row per person in the league. Created by the app on first sign-in.
create table if not exists pickem_players (
  user_id      uuid primary key references auth.users(id) on delete cascade,
  display_name text not null,
  email        text,
  notify       boolean not null default true,
  created_at   timestamptz not null default now()
);

-- One row per Big 12 game. Written only by the GitHub Actions sync job.
create table if not exists pickem_games (
  id          text primary key,          -- ESPN event id
  season      int  not null,
  week        int  not null,
  kickoff     timestamptz not null,
  status      text not null default 'scheduled',  -- scheduled | in | final
  neutral     boolean not null default false,
  conference_game boolean not null default false,
  home_id     text, home_name text, home_abbr text, home_logo text,
  home_rank   int,  home_score int,
  away_id     text, away_name text, away_abbr text, away_logo text,
  away_rank   int,  away_score int,
  winner_id   text,                        -- team id, set when the game goes final
  updated_at  timestamptz not null default now()
);
create index if not exists pickem_games_week_idx on pickem_games (season, week);

-- One row per person per game.
create table if not exists pickem_picks (
  user_id    uuid not null references auth.users(id) on delete cascade,
  game_id    text not null references pickem_games(id) on delete cascade,
  team_id    text not null,
  updated_at timestamptz not null default now(),
  primary key (user_id, game_id)
);

-- Bookkeeping so the reminder job never nags the same person twice in a week.
create table if not exists pickem_reminders (
  user_id uuid not null references auth.users(id) on delete cascade,
  season  int  not null,
  week    int  not null,
  sent_at timestamptz not null default now(),
  primary key (user_id, season, week, sent_at)
);


-- ---------------------------------------------------------------------------
-- Lock rule: every pick for a week locks at that week's FIRST kickoff.
-- ---------------------------------------------------------------------------

create or replace function pickem_lock_at(p_season int, p_week int)
returns timestamptz
language sql stable security definer set search_path = public as $$
  select min(kickoff) from pickem_games where season = p_season and week = p_week;
$$;

-- Fails closed: an unknown game counts as locked.
create or replace function pickem_game_locked(p_game_id text)
returns boolean
language sql stable security definer set search_path = public as $$
  select coalesce(
    now() >= (select pickem_lock_at(g.season, g.week)
              from pickem_games g where g.id = p_game_id),
    true
  );
$$;


-- ---------------------------------------------------------------------------
-- Row Level Security
--
-- The service_role key used by the GitHub Actions jobs bypasses all of this,
-- which is why the sync job can write games and nobody else can.
-- ---------------------------------------------------------------------------

alter table pickem_players   enable row level security;
alter table pickem_games     enable row level security;
alter table pickem_picks     enable row level security;
alter table pickem_reminders enable row level security;

drop policy if exists players_read   on pickem_players;
drop policy if exists players_insert on pickem_players;
drop policy if exists players_update on pickem_players;

-- The whole league is visible to the league -- the leaderboard needs names.
create policy players_read on pickem_players
  for select to authenticated using (true);
create policy players_insert on pickem_players
  for insert to authenticated with check (auth.uid() = user_id);
create policy players_update on pickem_players
  for update to authenticated
  using (auth.uid() = user_id) with check (auth.uid() = user_id);

drop policy if exists games_read on pickem_games;
create policy games_read on pickem_games
  for select to authenticated using (true);

drop policy if exists picks_read   on pickem_picks;
drop policy if exists picks_insert on pickem_picks;
drop policy if exists picks_update on pickem_picks;
drop policy if exists picks_delete on pickem_picks;

-- You always see your own picks. You see everyone else's only once the week
-- has locked -- so nobody can copy the sharpest person in the family.
create policy picks_read on pickem_picks
  for select to authenticated
  using (user_id = auth.uid() or pickem_game_locked(game_id));

-- Writes are yours alone, and only before the week locks.
create policy picks_insert on pickem_picks
  for insert to authenticated
  with check (user_id = auth.uid() and not pickem_game_locked(game_id));
create policy picks_update on pickem_picks
  for update to authenticated
  using      (user_id = auth.uid() and not pickem_game_locked(game_id))
  with check (user_id = auth.uid() and not pickem_game_locked(game_id));
create policy picks_delete on pickem_picks
  for delete to authenticated
  using (user_id = auth.uid() and not pickem_game_locked(game_id));

-- Reminder bookkeeping is service-job only: no policies means no client access.


-- ---------------------------------------------------------------------------
-- Views
-- ---------------------------------------------------------------------------

-- One row per week, with its lock time.
create or replace view pickem_weeks with (security_invoker = true) as
select season,
       week,
       min(kickoff)                             as lock_at,
       max(kickoff)                             as last_kickoff,
       count(*)::int                            as games,
       count(*) filter (where status = 'final')::int as finals
from pickem_games
group by season, week;

-- Season leaderboard. Every game is worth exactly 1 point.
create or replace view pickem_standings with (security_invoker = true) as
select pl.user_id,
       pl.display_name,
       count(*) filter (where g.status = 'final' and pk.team_id = g.winner_id)::int as correct,
       count(*) filter (where g.status = 'final')::int                              as decided,
       coalesce(max(g.season), 0)                                                   as season
from pickem_players pl
left join pickem_picks pk on pk.user_id = pl.user_id
left join pickem_games g  on g.id = pk.game_id
group by pl.user_id, pl.display_name;

grant select on pickem_weeks     to authenticated;
grant select on pickem_standings to authenticated;


-- ---------------------------------------------------------------------------
-- Realtime: leaderboard and picks update live without a refresh.
-- ---------------------------------------------------------------------------

do $$
begin
  begin
    alter publication supabase_realtime add table pickem_picks;
  exception when duplicate_object then null;
  end;
  begin
    alter publication supabase_realtime add table pickem_games;
  exception when duplicate_object then null;
  end;
end $$;
