-- ============================================================================
-- Daily board -- database schema
--
-- Run AFTER cross/schema.sql, in the same Supabase project:
--   Supabase Dashboard -> SQL Editor -> New query -> paste this whole file -> Run
-- Safe to re-run.
--
-- The board's panels are fed from outside, every few minutes:
--   calendar, gmail, upkeep  <- the Google Apps Script in your Google account
--   garmin                   <- the Garmin sync (daily/garmin/)
-- Each one sends a small summary here with the FEED key. The wall reads all
-- of them, plus the habits, with the WALL key. Nobody else can do either.
-- ============================================================================

-- One row per feed: its latest summary, replaced each time it syncs.
create table if not exists daily_feeds (
  source     text primary key check (source in ('calendar','gmail','upkeep','garmin')),
  payload    jsonb not null,
  updated_at timestamptz not null default now()
);

alter table daily_feeds enable row level security;
drop policy if exists daily_feeds_owner on daily_feeds;
create policy daily_feeds_owner on daily_feeds
  for select to authenticated using (cross_is_owner());


-- ---------------------------------------------------------------------------
-- A feed reporting in. Garmin also checks off Sweat for every day it saw an
-- activity on (payload.active_days), unless you unchecked it by hand.
-- ---------------------------------------------------------------------------
create or replace function daily_put(k text, src text, payload jsonb)
returns void
language plpgsql security definer set search_path = public as $$
declare d text;
begin
  if k is null or k <> (select feed_key from cross_settings where id = 1) then
    raise exception 'not allowed' using errcode = '42501';
  end if;
  if length(payload::text) > 100000 then
    raise exception 'too big' using errcode = '22023';
  end if;

  insert into daily_feeds (source, payload, updated_at) values (src, payload, now())
  on conflict (source) do update set payload = excluded.payload, updated_at = now();

  if src = 'garmin' and jsonb_typeof(payload -> 'active_days') = 'array' then
    for d in select jsonb_array_elements_text(payload -> 'active_days') loop
      if d ~ '^\d{4}-\d{2}-\d{2}$' and d::date between current_date - 3 and current_date + 1 then
        perform cross_auto(d::date, 'sweat');
      end if;
    end loop;
  end if;
end $$;

revoke all on function daily_put(text, text, jsonb) from public;
grant execute on function daily_put(text, text, jsonb) to anon, authenticated;


-- ---------------------------------------------------------------------------
-- Everything the wall shows, in one call.
-- ---------------------------------------------------------------------------
create or replace function daily_wall(k text)
returns json
language plpgsql stable security definer set search_path = public as $$
begin
  if k is null or k <> (select wall_key from cross_settings where id = 1) then
    raise exception 'not allowed' using errcode = '42501';
  end if;
  return json_build_object(
    'cross', cross_wall(k),
    'feeds', coalesce((select json_object_agg(source,
                json_build_object('payload', payload, 'updated_at', updated_at)) from daily_feeds), '{}'::json)
  );
end $$;

revoke all on function daily_wall(text) from public;
grant execute on function daily_wall(text) to anon, authenticated;
