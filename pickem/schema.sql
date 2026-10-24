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
  home_rank   int,  home_score int, home_record text,
  away_id     text, away_name text, away_abbr text, away_logo text,
  away_rank   int,  away_score int, away_record text,
  winner_id   text,                        -- team id, set when the game goes final
  updated_at  timestamptz not null default now()
);
create index if not exists pickem_games_week_idx on pickem_games (season, week);

-- Added after the first release; safe to re-run.
alter table pickem_games add column if not exists home_record text;
alter table pickem_games add column if not exists away_record text;
alter table pickem_games add column if not exists home_spread numeric;  -- negative = home favored
alter table pickem_games add column if not exists odds_detail text;     -- e.g. "TTU -3.5", for display

-- One row per person per week, written when they choose to lock in early.
-- No delete policy exists: locking in is deliberately irreversible.
create table if not exists pickem_locks (
  user_id   uuid not null references auth.users(id) on delete cascade,
  season    int  not null,
  week      int  not null,
  locked_at timestamptz not null default now(),
  primary key (user_id, season, week)
);

-- Commissioners. Seeded by hand in the SQL editor; there is deliberately no
-- insert, update or delete policy, so nobody can promote themselves from the
-- browser. Readable by everyone, because the app has to know whose screen
-- shows the grant controls.
create table if not exists pickem_admins (
  user_id    uuid primary key references auth.users(id) on delete cascade,
  created_at timestamptz not null default now()
);

-- A catch-up window for one person, one week. Inside it that person may pick
-- every game in the week, including games already kicked off or finished --
-- which is the whole point, and why it is per-person, short, and visible to
-- the entire league rather than a quiet edit to the week's deadline.
--
-- Two things stop it being a back door, both enforced below rather than here:
-- while your window is open you cannot see anybody else's picks, and every
-- pick you make after a kickoff is stamped `late` for all to see.
create table if not exists pickem_grace (
  user_id    uuid not null references auth.users(id) on delete cascade,
  season     int  not null,
  week       int  not null,
  expires_at timestamptz not null,
  granted_by uuid references auth.users(id) on delete set null,
  granted_at timestamptz not null default now(),
  primary key (user_id, season, week)
);

-- A deadline extension, used when someone misses the window and the league
-- agrees to reopen it. Only ever pushes a deadline later, never earlier.
-- Delete the row to put the normal deadline back.
create table if not exists pickem_week_overrides (
  season     int not null,
  week       int not null,
  lock_at    timestamptz not null,
  reason     text,
  created_at timestamptz not null default now(),
  primary key (season, week)
);
alter table pickem_week_overrides enable row level security;
drop policy if exists overrides_read on pickem_week_overrides;
-- Readable so the app can show the extended deadline. Writing is service-role
-- only: no policy for insert or update means nobody can grant themselves time.
create policy overrides_read on pickem_week_overrides
  for select to authenticated using (true);


-- One row per person per game.
create table if not exists pickem_picks (
  user_id    uuid not null references auth.users(id) on delete cascade,
  game_id    text not null references pickem_games(id) on delete cascade,
  team_id    text not null,
  updated_at timestamptz not null default now(),
  primary key (user_id, game_id)
);
-- True when the deadline passed with this game unpicked and the favourite was
-- assigned on that player's behalf. Shown in the app so nobody is surprised.
alter table pickem_picks add column if not exists auto boolean not null default false;
-- True when the pick was made after that game's kickoff, which can only happen
-- inside a catch-up window. Stamped by a trigger, not by the client.
alter table pickem_picks add column if not exists late boolean not null default false;

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

-- Normally the first kickoff of the week. GREATEST ignores NULLs, so with no
-- override row this is unchanged, and an override can only move it later.
create or replace function pickem_lock_at(p_season int, p_week int)
returns timestamptz
language sql stable security definer set search_path = public as $$
  select greatest(
    (select min(kickoff) from pickem_games
      where season = p_season and week = p_week),
    (select lock_at from pickem_week_overrides
      where season = p_season and week = p_week)
  );
$$;

-- Underdog scoring. A correct pick is worth more the bigger the upset.
--   favorite or near-even ....... 1
--   +3   to +9.5 ................ 2
--   +10  to +17.5 ............... 3
--   +18  or more ................ 4
-- No line (FCS opponents, lines not posted yet) scores 1, same as a favorite.
create or replace function pickem_points(p_home_spread numeric, p_home_id text, p_team_id text)
returns int
language sql immutable as $$
  select case
    when p_home_spread is null then 1
    else case
      when (case when p_team_id = p_home_id then p_home_spread else -p_home_spread end) >= 18 then 4
      when (case when p_team_id = p_home_id then p_home_spread else -p_home_spread end) >= 10 then 3
      when (case when p_team_id = p_home_id then p_home_spread else -p_home_spread end) >= 3  then 2
      else 1
    end
  end;
$$;

-- The pick window opens Sunday 06:00 Mountain and runs to the first kickoff.
-- Lines are frozen at this same moment, so the number you see when picks open is
-- the number everyone is scored on. date_trunc('week') lands on Monday, hence the
-- shift either side of it to land on the preceding Sunday.
-- All the date arithmetic happens on a naive local timestamp and is converted back
-- afterwards, which keeps it correct across the November clock change.
create or replace function pickem_open_at(p_season int, p_week int)
returns timestamptz
language sql stable security definer set search_path = public as $$
  select case
           when k is null then null
           -- A game starting before 6am Sunday would otherwise open its own
           -- window after kickoff, leaving nobody able to pick it at all.
           when o >= k  then o - interval '7 days'
           else o
         end
  from (
    select k,
           (   date_trunc('week', (k at time zone 'America/Denver') + interval '1 day')
             - interval '1 day' + interval '6 hours'
           ) at time zone 'America/Denver' as o
    from (select min(kickoff) as k from pickem_games
          where season = p_season and week = p_week) m
  ) t;
$$;

-- Has this person locked their picks in for the week?
create or replace function pickem_is_locked_in(p_user uuid, p_season int, p_week int)
returns boolean
language sql stable security definer set search_path = public as $$
  select exists (
    select 1 from pickem_locks
    where user_id = p_user and season = p_season and week = p_week
  );
$$;

-- Is this person a commissioner?
create or replace function pickem_is_admin(p_user uuid)
returns boolean
language sql stable security definer set search_path = public as $$
  select exists (select 1 from pickem_admins where user_id = p_user);
$$;

-- Is this person inside an open catch-up window for the week?
create or replace function pickem_has_grace(p_user uuid, p_season int, p_week int)
returns boolean
language sql stable security definer set search_path = public as $$
  select exists (
    select 1 from pickem_grace
    where user_id = p_user and season = p_season and week = p_week
      and now() < expires_at
  );
$$;

-- Fails closed: an unknown game counts as locked.
-- True whenever a pick may NOT be made right now: before the window opens,
-- after the deadline, or because this person locked themselves in early.
--
-- A catch-up window lifts the deadline and the kickoff bar for one person, but
-- not the other two:
--   * The window opening Sunday at 6am still holds. Lines are frozen at that
--     moment, so letting anyone reach a later week early would hand them picks
--     against numbers nobody else has seen.
--   * Locking yourself in is still final. By the time you lock in you may have
--     seen the picks of everyone else who locked in, so reopening yours would
--     let you answer them.
create or replace function pickem_game_locked(p_game_id text)
returns boolean
language sql stable security definer set search_path = public as $$
  select coalesce(
    (select now() < pickem_open_at(g.season, g.week)
          or pickem_is_locked_in(auth.uid(), g.season, g.week)
          or (
            not pickem_has_grace(auth.uid(), g.season, g.week)
            and (
              now() >= pickem_lock_at(g.season, g.week)
              -- Belt and braces, and the whole point during a week-wide
              -- extension: a game already under way is not pickable, whatever
              -- the week's deadline says. Without an override this never
              -- fires, because the week locks at the earliest kickoff anyway.
              or now() >= g.kickoff
            )
          )
     from pickem_games g where g.id = p_game_id),
    true
  );
$$;

-- Stamp a pick `late` when it lands after that game's kickoff, which only a
-- catch-up window allows. A trigger rather than a column the client sets,
-- because the honesty of the badge is the whole point of it. Assigned
-- favourites are already marked `auto` and are not anybody's late pick.
create or replace function pickem_flag_late()
returns trigger
language plpgsql security definer set search_path = public as $$
declare k timestamptz;
begin
  -- Only a change of mind is re-judged. An update that leaves the pick alone
  -- keeps whatever stamp it already had, so a later housekeeping write cannot
  -- retroactively brand a whole week of on-time picks as late.
  if tg_op = 'UPDATE' and new.team_id is not distinct from old.team_id then
    new.late := old.late;
    return new;
  end if;
  select g.kickoff into k from pickem_games g where g.id = new.game_id;
  new.late := coalesce(not new.auto and now() >= k, false);
  return new;
end;
$$;

drop trigger if exists pickem_picks_flag_late on pickem_picks;
create trigger pickem_picks_flag_late
  before insert or update on pickem_picks
  for each row execute function pickem_flag_late();


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
alter table pickem_locks     enable row level security;
alter table pickem_admins    enable row level security;
alter table pickem_grace     enable row level security;

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

-- You always see your own picks. You see someone else's when either the week
-- has locked, or you have BOTH locked in early -- mutual disclosure, so nobody
-- can peek at picks the other person could still change.
--
-- And one exception that runs the other way: while your own catch-up window is
-- open you still owe picks, so the week closes to you however late it is.
-- Without this the grant would be worth more than the picks -- the week is
-- public by then, and you would be choosing with everyone's answers in front
-- of you.
create policy picks_read on pickem_picks
  for select to authenticated
  using (
    user_id = auth.uid()
    or exists (
      select 1 from pickem_games g
      where g.id = pickem_picks.game_id
        and not pickem_has_grace(auth.uid(), g.season, g.week)
        and (
          now() >= pickem_lock_at(g.season, g.week)
          or (
            pickem_is_locked_in(auth.uid(),          g.season, g.week)
            and pickem_is_locked_in(pickem_picks.user_id, g.season, g.week)
          )
        )
    )
  );

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

drop policy if exists locks_read   on pickem_locks;
drop policy if exists locks_insert on pickem_locks;

-- Who has locked in is public: the app shows it, and it gates what you can see.
create policy locks_read on pickem_locks
  for select to authenticated using (true);

-- You may only lock yourself in, only before the weekly deadline, and only once
-- every game that week has a pick. Locking in with blanks is just volunteering
-- for zeroes. There is deliberately no update or delete policy.
create policy locks_insert on pickem_locks
  for insert to authenticated
  with check (
    user_id = auth.uid()
    and now() < pickem_lock_at(season, week)
    and (
      select count(*) from pickem_games g
      where g.season = pickem_locks.season and g.week = pickem_locks.week
    ) = (
      select count(*) from pickem_picks pk
      join pickem_games g2 on g2.id = pk.game_id
      where pk.user_id = auth.uid()
        and g2.season = pickem_locks.season and g2.week = pickem_locks.week
    )
  );

drop policy if exists admins_read on pickem_admins;

-- Who the commissioners are is public. Becoming one is not: no insert, update
-- or delete policy exists, so it can only be done with the service key.
create policy admins_read on pickem_admins
  for select to authenticated using (true);

drop policy if exists grace_read   on pickem_grace;
drop policy if exists grace_insert on pickem_grace;
drop policy if exists grace_update on pickem_grace;
drop policy if exists grace_delete on pickem_grace;

-- Every open window is visible to the whole league. A quiet grant would be
-- worse than no grant at all.
create policy grace_read on pickem_grace
  for select to authenticated using (true);

-- Only a commissioner grants one, only in their own name, and never longer
-- than a day: this is for somebody who missed the window, not a second season.
create policy grace_insert on pickem_grace
  for insert to authenticated
  with check (
    pickem_is_admin(auth.uid())
    and granted_by = auth.uid()
    and expires_at >  now()
    and expires_at <= now() + interval '24 hours'
  );
create policy grace_update on pickem_grace
  for update to authenticated
  using (pickem_is_admin(auth.uid()))
  with check (
    pickem_is_admin(auth.uid())
    and granted_by = auth.uid()
    and expires_at >  now()
    and expires_at <= now() + interval '24 hours'
  );
-- Revoking early is allowed; the picks already made stand, stamped `late`.
create policy grace_delete on pickem_grace
  for delete to authenticated
  using (pickem_is_admin(auth.uid()));

-- Reminder bookkeeping is service-job only: no policies means no client access.


-- ---------------------------------------------------------------------------
-- Views
-- ---------------------------------------------------------------------------

-- One row per week, with the window it can be picked in.
-- Dropped first because the column list has changed since the first release,
-- and CREATE OR REPLACE VIEW cannot add a column anywhere but the end.
drop view if exists pickem_weeks cascade;
create view pickem_weeks with (security_invoker = true) as
select season,
       week,
       pickem_lock_at(season, week)             as lock_at,
       pickem_open_at(season, week)             as open_at,
       max(kickoff)                             as last_kickoff,
       count(*)::int                            as games,
       count(*) filter (where status = 'final')::int as finals
from pickem_games
group by season, week;

-- Season leaderboard, now scored on points rather than raw correct picks.
drop view if exists pickem_standings cascade;
create view pickem_standings with (security_invoker = true) as
select pl.user_id,
       pl.display_name,
       coalesce(sum(
         case when g.status = 'final' and pk.team_id = g.winner_id
              then pickem_points(g.home_spread, g.home_id, pk.team_id)
              else 0 end
       ), 0)::int                                                                   as points,
       count(*) filter (where g.status = 'final' and pk.team_id = g.winner_id)::int as correct,
       count(*) filter (where g.status = 'final')::int                              as decided,
       -- Surfaced on the leaderboard so a catch-up week is never invisible.
       count(*) filter (where pk.late)::int                                         as late_picks,
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
  -- So someone else locking in reveals their picks to you without a reload.
  begin
    alter publication supabase_realtime add table pickem_locks;
  exception when duplicate_object then null;
  end;
  -- So a catch-up window opens on the recipient's phone the moment it is
  -- granted, rather than whenever they next happen to reload.
  begin
    alter publication supabase_realtime add table pickem_grace;
  exception when duplicate_object then null;
  end;
  begin
    alter publication supabase_realtime add table pickem_games;
  exception when duplicate_object then null;
  end;
end $$;
