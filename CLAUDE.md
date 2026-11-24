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
  `robots.txt` does not block `/ans`; it answers 200 to `curl`, measured on 2026-10-22). Since
  2026-11-21 `www.gov.br` resets the TLS handshake from GitHub's runners (`curl: (35) Recv failure:
  Connection reset by peer`, run 45276519530) while it still answers 200 from the laptop: the RN 623
  lists and the special-portability page fail in CI every day until that changes.
- Respect `robots.txt`: `www.ans.gov.br` and `www.in.gov.br` (DOU) are `Disallow: /`. The
  `index.php?option=…` queries, `component/legislacao` (RO and RN texts) and the DOU search stay out of
  any automation; record the link, do not scrape.
- LGPD: no NIP row (`pda-013`) goes into the repo; only per-operator aggregates, and at this stage not
  even those.
- No file above 100 MB in git (GitHub rejects it).
- `RUNBOOK.md` (Portuguese, for the user, not for an agent) explains every way a workflow here turns
  red. Adding or changing an alarm (`::error::`, `::warning::`, a `FALHA:` reason, an `exit 1` or a raise
  that ends a workflow) or an error message means updating its entry in the same commit, quoting the
  message exactly as the log prints it.

## Public text and data on a page

This section is the same in the five health site repos (anvisa-hub, anvisa-dash, portal-saude,
anvisa-feeds, ans): a change to it goes to all five in the same round. Rules only one site needs stay
outside it. Each rule below comes from a defect found on these sites in the 2026-11-24 audit.

Data:

- Every number, date, count and name of a source comes from the data at build time. A fact that cannot
  (a phone line's hours, a legal deadline) lives in one config entry with its source link and the date it
  was checked, and the page shows both. A sentence like "nenhum número é digitado à mão" stays only
  while it holds.
- Name the source where the value is shown: the publisher and the specific file, table or page, linked.
  "Dados da ANVISA" alone is not a source. A table we derive names the publisher's files it comes from,
  never only our own script. Every page that shows, compares or ranks data has its sources, not only the
  main pages.
- A value carries the date of its copy next to it, not only in a folded section: the source's own date
  (Last-Modified, publication or list date, said as such) and our collection date where they differ.
  "Atualizado em" or "dados de" alone is ambiguous: say whose date it is. A list's file date is not the
  publisher's list date unless the data says so.
- Freshness is read from the data, never promised. No fixed sentence about cadence ("o site é refeito
  todo dia", "mostra a nova em até um dia", "nos dias úteis por volta das 12h30", "republicados
  diariamente"): say the date of the copy shown. Static output never says "hoje", "agora", "atual" or
  "vigente"; it says the date.
- A source that failed or lags is named, with the date of the copy shown and the first day it failed,
  on the pages that use it and not on the others. A producer that records failures keeps the first
  failure day across runs (it is part of the contract). When the publisher is known to be ahead of the
  copy we read (a newer list on its own page), the page says so.
- A comparison says what it compares: "coleta de 23/11 contra a de 20/11", "lista de 09/10 contra a de
  09/09". A diff that spans a missed day says so.
- Missing is said in words ("a ANS não informou o valor de março de 2026"). Null is never shown as 0,
  "nada", an empty cell, a zero-height bar or a dropped row; null, 0 and "does not apply" are separate
  branches. An unknown or new category value never falls into the reassuring branch (a value other than
  "Sim" or "Não" is "não informado", not "sem glúten"), and a company's declaration is labelled as one.
- A value the site computes (a count, rate, ranking, threshold, classification, "típica") says how, once,
  next to it or behind one link. The rule is on the page, not only in a code comment. Our own
  transformations are said: the data is "como a ANVISA publica, convertida para Parquet; entradas e
  saídas calculadas aqui", never just "sem alteração".
- A known caveat of a field is stated where the field appears (a footnote marker is explained on the
  same screen) and in the dictionary when there is one.
- The raw data (our JSON or Parquet and the publisher's file) and the data's licence are one link away
  from every page that shows it. The code licence (MIT) is never given as the data's licence, in JSON-LD
  either.
- A failure to load data in the browser is said ("não foi possível carregar as medidas"), never left
  looking like "nenhuma medida".

Writing (public text is pt-BR, for people who do not know the jargon):

- Say what the data shows and stop. No filler intro ("Aqui você encontra", "Nesta página"), no heading
  repeated by the sentence under it, no closing summary, no definition given twice on a page.
- No stock phrases or slogans: "saiba mais", "clique aqui", "tudo o que você precisa", "simples assim",
  "só fatos", "na dúvida, confira", "de forma rápida e fácil", "respostas diretas", any "sem X, sem Y"
  pair, any run of three adjectives. A link says where it goes; never "fonte" or "aqui" alone.
- No praise of the site: "transparente", "completo", "confiável", "com a fonte de cada número". A
  property of the site is said once, on its about page, and only while every page meets it. A disclaimer
  ("não substitui a consulta oficial", "sem vínculo com a ANVISA") appears once per page, in the footer,
  with the official link.
- A general claim needs the data behind it: "todos", "sempre", "nunca", "costumam", "muitas", "com
  frequência" only when the build counts it. Absence from our copy is "não está na lista da ANVISA de
  {data}", never "não está liberado no Brasil".
- Explain a term once, plainly, as to an adult: abbreviations spelled out the first time (preço fábrica
  (PF)), no English where Portuguese exists ("coletas", not "snapshots"), no analogies or wordplay, no
  reassurance or advice not asked for, no vague hedge in place of a known fact ("às vezes demora" when
  the collection has failed since a date). No emojis.

## Layout

- `src/ans_feeds/`: the package (`ans-feeds build --snapshots snapshots --site site`); tests in `tests/`.
  Tests on the real `snapshots/` check only invariants; a value checked by hand goes on the
  `congelados` fixture (`conftest.py`, the tree up to `CONGELADO`), never on today's tree, which grows daily.
  Besides the feeds, the build publishes `dados/` (search index and one JSON per operator) for the public
  portal; the contract is `src/ans_feeds/dados_schema.md`. Facts with base and source only: no score of
  our own, no contact data, no prudential class as a health grade. `dados/todas.json` holds every
  operator in one file, and it is what the portal build reads: one file per operator meant ~1,340
  requests, and GitHub Pages answers 429 to that kind of burst.
- `operadora/<registro>.xml` (`feed_operadora.py`): one feed per operator in `dados`, for the portal's
  "Acompanhar". Its entries link to the portal's short `/plano/<registro>/` address (`PORTAL_URL` in
  `cli.py`), so that route must keep working on the portal.
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
