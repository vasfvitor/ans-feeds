# ans-feeds

Events of Brazilian health plan operators, from the open data of the ANS (Agência Nacional de Saúde
Suplementar), published as static Atom feeds at <https://ans.feeds.abelhaninja.de>.

| feed | what |
|---|---|
| `geral.xml` | all events (latest 100) |
| `cancelamento.xml` | operators whose ANS registration was cancelled, with the reason |
| `registro.xml` | new ANS registrations |
| `direcao-tecnica.xml` | Resoluções Operacionais that put an operator under technical direction |
| `portabilidade.xml` | special and extraordinary portability (beneficiaries may switch plans without new waiting periods) |

Fiscal direction and extrajudicial liquidation have no source that can be collected automatically
(the Diário Oficial and the old ANS site disallow robots); cancellations by liquidation are
highlighted instead.

## How it works

- `scripts/snapshot.sh` (curl and coreutils only) runs daily in GitHub Actions and stores in
  `snapshots/YYYY-MM-DD/` only the files that changed: the CADOP (active and cancelled operators),
  the IGR, technical direction and other files from `dadosabertos.ans.gov.br`, plus the RN 623 lists
  and the portability page from `gov.br/ans`. `snapshots/ESTADO.tsv` keeps the `Last-Modified` and
  sha256 of the latest version of each file.
- `ans-feeds build` rebuilds the whole site from the snapshots. Every event carries the date of the
  act, so the history comes from the current files; the snapshots add when the ANS first published
  it. Two builds of the same snapshots are byte for byte equal.
- The research behind the choices (formats, keys, what is stale at the source) is in
  `pesquisa/VALIDACAO.md`, in Portuguese.

## Personal data

The CADOP lists the name, e-mail and phone of each operator's legal representative. It is the ANS's
own open data, kept unchanged in the snapshots; the feeds and pages do not show e-mails or phones.
No row of the NIP complaints data is stored.

## Development

```sh
uv sync
uv run pytest
uv run ruff check . && uv run ruff format --check .
uv run ans-feeds build --snapshots snapshots --site site
```

The runtime uses only the Python standard library.

## License

MIT. The data belongs to the ANS and is published under its open data terms.
