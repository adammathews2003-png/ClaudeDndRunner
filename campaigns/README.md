# campaigns/

One folder per campaign. **Each campaign folder is its own git repository**: its files
(locations, NPCs, PCs, scenarios, tables, state, sessions) and its history (session
archives, time-loop baselines) live with it. The engine repository ignores everything
here except this README.

- Pick the campaign for a command: `python engine/gm.py --campaign <name> …` or
  `python engine/table.py --campaign <name>`; otherwise the name in `campaigns/.active`
  is used (a local file, not committed).
- New campaign: `python engine/gm.py scaffold <name> --area "<starting area>" [--activate]`
  (or `/new-campaign`; authored campaigns: `/campaign-new`). It `git init`s the folder
  with the engine repo's own git identity.
- `gm.py session archive` and `gm.py loop …` commit inside the campaign's repository.
- To back a campaign up, give its repository a remote of its own
  (`git -C campaigns/<name> remote add origin …`).

The engine's tests never use these folders: they run on frozen copies in
`engine/tests/fixtures/`.
