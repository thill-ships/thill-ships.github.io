"""Print one game's ESPN data compactly, for building wall-board demos.

Finds the most recent game between TEAM and OPPONENT (ESPN team ids) in the
given seasons and prints, one line per item:
  GAME    the header: teams, ranks, scores by quarter, network, date
  DRIVE   each drive: team, result, start and end, then
  PLAY    each play: quarter, clock, down/distance/spot, type, yards, text
  TEAM    team box score stats
  PLAYER  per-player box score lines
  OTHER   the other FBS games that day (for the bottom of the board)
With RAW set, also prints the raw summary and scoreboard JSON, gzipped and
base64-encoded. Read-only: never writes anything.
"""
import json
import os
import urllib.request

BASE = 'https://site.api.espn.com/apis/site/v2/sports/football/college-football'


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'wall-demo'}), timeout=30) as r:
        return json.load(r)


def out(tag, obj):
    print(tag, json.dumps(obj, separators=(',', ':')))


team = os.environ.get('TEAM') or '252'
opp = os.environ.get('OPPONENT') or '87'
seasons = (os.environ.get('SEASONS') or '2026 2025').split()

found = None
for season in seasons:
    sched = get(f'{BASE}/teams/{team}/schedule?season={season}')
    for ev in sched.get('events', []):
        comp = ev['competitions'][0]
        ids = [c['team']['id'] for c in comp['competitors']]
        out('SCHED', {'season': season, 'id': ev['id'], 'date': ev['date'], 'name': ev.get('shortName'),
                      'state': comp['status']['type']['state']})
        if opp in ids and comp['status']['type']['state'] == 'post' and not found:
            found = ev['id']
    if found:
        break

if not found:
    print('NO COMPLETED GAME FOUND between', team, 'and', opp, 'in', seasons)
    raise SystemExit(0)

s = get(f'{BASE}/summary?event={found}')
if os.environ.get('RAW'):
    # The untouched JSON, gzipped and base64'd onto one line each, for building fixtures.
    import base64, gzip
    day0 = (s['header']['competitions'][0].get('date') or '')[:10].replace('-', '')
    sb = get(f'{BASE}/scoreboard?groups=80&limit=300&dates={day0}')
    for tag, obj in (('RAWSUMMARY', s), ('RAWSCOREBOARD', sb)):
        print(tag, base64.b64encode(gzip.compress(json.dumps(obj, separators=(',', ':')).encode())).decode())
comp = s['header']['competitions'][0]
out('GAME', {
    'id': found, 'date': comp.get('date'),
    'teams': [{'id': c['team']['id'], 'abbr': c['team'].get('abbreviation'), 'name': c['team'].get('displayName'),
               'homeAway': c.get('homeAway'), 'rank': c.get('rank'), 'score': c.get('score'),
               'lines': [l.get('displayValue') for l in c.get('linescores', [])]} for c in comp['competitors']],
    'tv': [b.get('media', {}).get('shortName') for b in comp.get('broadcasts', [])],
})

for d in (s.get('drives') or {}).get('previous', []):
    out('DRIVE', {'team': d.get('team', {}).get('abbreviation'), 'result': d.get('displayResult') or d.get('result'),
                  'desc': d.get('description'), 'start': d.get('start', {}).get('text'), 'end': d.get('end', {}).get('text'),
                  'startQ': d.get('start', {}).get('period', {}).get('number'),
                  'startClock': d.get('start', {}).get('clock', {}).get('displayValue')})
    for p in d.get('plays', []):
        st, en = p.get('start', {}), p.get('end', {})
        out('PLAY', {'q': p.get('period', {}).get('number'), 'clk': p.get('clock', {}).get('displayValue'),
                     'dn': st.get('down'), 'dist': st.get('distance'), 'yl': st.get('yardLine'), 'spot': st.get('possessionText'),
                     'endYl': en.get('yardLine'), 'endSpot': en.get('possessionText'),
                     'type': p.get('type', {}).get('text'), 'yds': p.get('statYardage'),
                     'score': p.get('scoringPlay'), 'a': p.get('awayScore'), 'h': p.get('homeScore'), 'text': p.get('text')})

for t in s.get('boxscore', {}).get('teams', []):
    out('TEAM', {'team': t['team'].get('abbreviation'),
                 'stats': {x.get('label') or x.get('name'): x.get('displayValue') for x in t.get('statistics', [])}})
for t in s.get('boxscore', {}).get('players', []):
    for cat in t.get('statistics', []):
        for a in cat.get('athletes', []):
            out('PLAYER', {'team': t['team'].get('abbreviation'), 'cat': cat.get('name'),
                           'name': a['athlete'].get('shortName') or a['athlete'].get('displayName'),
                           'labels': cat.get('labels'), 'stats': a.get('stats')})

day = (comp.get('date') or '')[:10].replace('-', '')
if day:
    board = get(f'{BASE}/scoreboard?groups=80&limit=300&dates={day}')
    for ev in board.get('events', []):
        c = ev['competitions'][0]
        out('OTHER', {'name': ev.get('shortName'), 'state': c['status']['type']['state'],
                      'teams': [{'id': x['team']['id'], 'abbr': x['team'].get('abbreviation'),
                                 'rank': (x.get('curatedRank') or {}).get('current'), 'score': x.get('score')}
                                for x in c['competitors']],
                      'tv': [b.get('names', [None])[0] for b in c.get('broadcasts', [])]})
