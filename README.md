# thill-ships.github.io

A small collection of static apps on GitHub Pages. Each folder is one self-contained
`index.html`; the ones that keep data use [Supabase](https://supabase.com) behind email
logins and Row Level Security.

| Path | What it is | Data |
|---|---|---|
| `pickem/` | Big 12 pick'em league: every game, every week, one leaderboard | Supabase, individual accounts |
| `props/` | Season-long BYU props: lock your answers in to see everyone else's | Supabase, individual accounts |
| `big12/` | Big 12 War Room: a Monday-morning contender board with simulated title odds | Supabase, one shared login |
| `golf/` | Practice tracker with cloud sync and a read-only coach link | Supabase, individual accounts |
| everything else | Personal pages | Browser only |

The root hub and the personal pages sit behind a password (`gate.js`). It is a privacy
curtain, not a security boundary: this repo is public, so anything that genuinely needs
protecting is enforced in the database, never in the page.

## Security notes

- The `sb_publishable_…` keys in the pages are Supabase **publishable** keys. They are
  designed to ship in browser code; every row they can reach is governed by the policies in
  `pickem/schema.sql` and `big12/schema.sql`.
- The **service_role** key never appears in this repo. The scheduled jobs under
  `.github/workflows/` read it from GitHub Actions secrets.
- Passwords are handled by Supabase Auth (bcrypt hashed). The apps pass them straight to
  `signInWithPassword` and never store or log them.
- Nobody's email address is readable from the browser except their own. The player tables
  grant `select` on the display columns only; the reminder job reads emails with the
  service key.

Setup walkthroughs: [`pickem/SETUP.md`](pickem/SETUP.md), [`big12/SETUP.md`](big12/SETUP.md).
