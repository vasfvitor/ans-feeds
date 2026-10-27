# ans-feeds

Research and validation of ANS open data for a scorecard of health plan operators.
The `ans_feeds` package rebuilds static Atom feeds of operator events (cancellations, new registrations,
technical direction, special portability) from the committed snapshots. The research behind it is in
`pesquisa/VALIDACAO.md` (in Portuguese, like the data).

## Rules

- Commit by path (`git add` with explicit paths), without asking, one subject per commit; never push.
  Commit messages in English, without prefixes (as in `anvisa-feeds`).
- Runtime uses only the Python standard library; the only dependencies are dev ones (pytest, ruff), managed
  with `uv` (`uv sync`, `uv run pytest`, `uv run ruff check .`). Nothing else without a plan.
- Code, comments, README and commit messages in English; visitor-facing text (pages, feed titles and
  content) in pt-BR; ANS domain nouns stay in Portuguese.
- Downloads go to `pesquisa/downloads/YYYY-MM-DD/` (outside git), with the HTTP headers in `headers/`.
  Scripts live in `pesquisa/scripts/`, never in the downloads folder, and read the files with
  `python3 -I`, taking the path as an argument.
- `curl` for the FTP (`dadosabertos.ans.gov.br`, no `robots.txt`) and for `www.gov.br/ans` (its
  `robots.txt` does not block `/ans`; it answers 200 to `curl`, measured on 2026-10-22).
- Respect `robots.txt`: `www.ans.gov.br` and `www.in.gov.br` (DOU) are `Disallow: /`. The
  `index.php?option=…` queries, `component/legislacao` (RO and RN texts) and the DOU search stay out of
  any automation; record the link, do not scrape.
- LGPD: no NIP row (`pda-013`) goes into the repo; only per-operator aggregates, and at this stage not
  even those.
- No file above 100 MB in git (GitHub rejects it).

## Layout

- `src/ans_feeds/`: the package (`ans-feeds build --snapshots snapshots --site site`); tests in `tests/`.
  Besides the feeds, the build publishes `dados/` (search index and one JSON per operator) for the public
  portal; the contract is `src/ans_feeds/dados_schema.md`. Facts with base and source only: no score of
  our own, no contact data, no prudential class as a health grade. `dados/todas.json` holds every
  operator in one file, and it is what the portal build reads: one file per operator meant ~1,340
  requests, and GitHub Pages answers 429 to that kind of burst.
- `.github/workflows/feeds.yml`: daily snapshot (10:30 UTC), commit, build and Pages deploy;
  `ci.yml`: ruff, pytest and a real build on every push. Pushing and enabling are the user's.
- `snapshots/YYYY-MM-DD/`: copies of what the ANS overwrites (daily CADOP, IGR and other
  reprocessed files, quarterly RN 623 PDFs), only what changed since the previous snapshot, with
  `SHA256SUMS` and `FONTES.tsv`. `snapshots/ESTADO.tsv` keeps the `Last-Modified` and sha256 of
  the latest version of each file; generate with `bash scripts/snapshot.sh` (curl and coreutils only).
- `pesquisa/fixtures/`: header + 50 records of each CSV (`*_head.csv`), rows with odd cases
  (`*_casos.csv`), `headers_*.txt` and `manifest.json`; all byte for byte, `-text` in `.gitattributes`.
  Recipe from the `anvisa` repo's `CONTRIBUTING.md`. Regenerate with
  `python3 -I pesquisa/scripts/fixtures.py pesquisa/downloads/2026-10-22 pesquisa/downloads/2026-10-23 pesquisa/fixtures`
  (each file comes from the last folder that has it).
- `pesquisa/scripts/`: `perfil.py` (format of each CSV), `validar.py` (validation questions),
  `rn623.py` (RN 623 list reconstruction), `pda055.py` (pooled adjustment), `cadop_diff.py` (diff of two
  CADOP snapshots).
