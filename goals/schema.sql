-- ============================================================================
-- Goals -- database schema
--
-- Run this in the SAME Supabase project the pick'em and war room use:
--   Supabase Dashboard -> SQL Editor -> New query -> paste this whole file -> Run
--
-- Safe to re-run. Every statement is idempotent; policies and functions are
-- replaced, never a table, column or row dropped.
--
-- Two ways in:
--   * the phone app (goals/) signs in as the one account named below, and
--     reads and writes the tables directly;
--   * the kitchen wall (daily/) never signs in. It carries a secret wall key
--     in its link, and the two functions at the bottom check that key.
-- ============================================================================


-- ---------------------------------------------------------------------------
-- Who owns the data. One login; see SETUP.md.
-- ---------------------------------------------------------------------------
create or replace function goals_is_owner()
returns boolean
language sql stable as $$
  select coalesce(auth.jwt() ->> 'email', '') = any (array[
    'tyler@thill-ships.app'            -- <-- the login (see SETUP.md)
  ]);
$$;


-- ---------------------------------------------------------------------------
-- Tables
-- ---------------------------------------------------------------------------

-- One row per day: which goals got done. Goals are stored by key
-- ('gym', 'pray', 'teeth', 'clean', 'income'), so renaming one in
-- goals/core.js never touches the data. Weekly goals are worked out from
-- these daily rows; nothing about weeks is stored. A day with no row is a day with nothing done.
create table if not exists goals_days (
  day        date primary key,               -- local (Mountain) calendar day
  done       text[] not null default '{}',
  updated_at timestamptz not null default now()
);

-- A single row of settings.
--   start_day: the day the stock "went public". Null = the first day logged.
--   wall_key:  the secret in the wall's link. Change it from the phone app.
create table if not exists goals_settings (
  id         int primary key default 1 check (id = 1),
  start_day  date,
  wall_key   text not null default substr(replace(gen_random_uuid()::text, '-', ''), 1, 16),
  updated_at timestamptz not null default now()
);
insert into goals_settings (id) values (1) on conflict (id) do nothing;

-- Added for the daily board's feeds (see daily/schema.sql). Safe to re-run.
--   auto:     goals a feed checked off by itself (Garmin -> Gym), so the
--             screens can say where a check came from.
--   cleared:  goals you unchecked by hand that day. A feed never re-checks
--             one of these, so your uncheck always wins.
--   feed_key: the secret the morning brief and the Garmin sync write with.
--             Separate from the wall key: the wall reads, feeds write.
alter table goals_days     add column if not exists auto    text[] not null default '{}';
alter table goals_days     add column if not exists cleared text[] not null default '{}';
alter table goals_settings add column if not exists feed_key text not null
  default substr(replace(gen_random_uuid()::text, '-', ''), 1, 24);


-- ---------------------------------------------------------------------------
-- Row Level Security: only the owner reads or writes, directly.
-- ---------------------------------------------------------------------------
alter table goals_days     enable row level security;
alter table goals_settings enable row level security;

drop policy if exists goals_days_owner on goals_days;
create policy goals_days_owner on goals_days
  for all to authenticated using (goals_is_owner()) with check (goals_is_owner());

drop policy if exists goals_settings_owner on goals_settings;
create policy goals_settings_owner on goals_settings
  for all to authenticated using (goals_is_owner()) with check (goals_is_owner());


-- ---------------------------------------------------------------------------
-- Checking a goal on or off. One function for the phone and the wall, so a
-- tap on one can never overwrite a tap on the other: it changes one goal on
-- one day, in the database, rather than saving a whole day the screen read
-- a minute ago. The owner needs no key; the wall passes its key.
-- ---------------------------------------------------------------------------
create or replace function goals_check(d date, goal text, val boolean, k text default null)
returns text[]
language plpgsql security definer set search_path = public as $$
declare out text[];
begin
  if not (goals_is_owner()
          or (k is not null and k = (select wall_key from goals_settings where id = 1))) then
    raise exception 'not allowed' using errcode = '42501';
  end if;
  if goal !~ '^[a-z]{1,20}$' then
    raise exception 'bad goal' using errcode = '22023';
  end if;
  -- Today, or any day before it; a day of slack either way for time zones.
  if d > current_date + 1 or d < date '2020-01-01' then
    raise exception 'bad day' using errcode = '22023';
  end if;

  insert into goals_days as c (day, done, cleared)
  values (d, case when val then array[goal] else '{}'::text[] end,
             case when val then '{}'::text[] else array[goal] end)
  on conflict (day) do update
    set done = case when val
                 then (case when goal = any (c.done) then c.done else c.done || goal end)
                 else array_remove(c.done, goal) end,
        auto = array_remove(c.auto, goal),
        cleared = case when val then array_remove(c.cleared, goal)
                       when goal = any (c.cleared) then c.cleared
                       else c.cleared || goal end,
        updated_at = now()
  returning done into out;
  return out;
end $$;

revoke all on function goals_check(date, text, boolean, text) from public;
grant execute on function goals_check(date, text, boolean, text) to anon, authenticated;


-- ---------------------------------------------------------------------------
-- A feed checking a goal off by itself. Never granted to anyone directly:
-- only daily_put calls it, after checking the feed key. It never re-checks a
-- goal you unchecked by hand that day.
-- ---------------------------------------------------------------------------
create or replace function goals_auto(d date, goal text)
returns void
language plpgsql security definer set search_path = public as $$
begin
  insert into goals_days as c (day, done, auto)
  values (d, array[goal], array[goal])
  on conflict (day) do update
    set done = c.done || goal, auto = c.auto || goal, updated_at = now()
    where not (goal = any (c.done)) and not (goal = any (c.cleared));
end $$;

revoke all on function goals_auto(date, text) from public, anon, authenticated;


-- ---------------------------------------------------------------------------
-- Everything the wall shows, in one call: the start day and every logged day.
-- ---------------------------------------------------------------------------
create or replace function goals_wall(k text)
returns json
language plpgsql stable security definer set search_path = public as $$
begin
  if k is null or k <> (select wall_key from goals_settings where id = 1) then
    raise exception 'not allowed' using errcode = '42501';
  end if;
  return json_build_object(
    'start_day', (select start_day from goals_settings where id = 1),
    'days', coalesce((select json_agg(json_build_object('day', day, 'done', done, 'auto', auto) order by day)
                        from goals_days), '[]'::json)
  );
end $$;

revoke all on function goals_wall(text) from public;
grant execute on function goals_wall(text) to anon, authenticated;
