"""Tables for people who redistribute (Procon, patient groups, journalists): CSVs derived from the
same operator records as dados/todas.json, nothing new collected. Written under dados/tabelas/ by
build_site.

The format is the ANS's own and what a spreadsheet in Portuguese opens as is: `;` between fields,
decimal comma, UTF-8 with a BOM. No ranking: each table is sorted by date or by registro, never
by a score.
"""

from __future__ import annotations

import csv
import io
from datetime import date, timedelta

FECHAMENTOS_DIAS = 365


def _decimal(v: float | None) -> str:
    return "" if v is None else f"{v:.2f}".replace(".", ",")


def _csv(header: list[str], rows: list[list[str]]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";", lineterminator="\r\n")
    w.writerow(header)
    w.writerows(rows)
    return "\ufeff" + buf.getvalue()


def portabilidade_vigente(registros: list[dict]) -> str:
    """One row per Resolução Operacional in force: the clients may switch plans without a new
    waiting period. Newest first."""
    rows = [
        [
            o["registro"],
            o["nome"],
            o.get("uf") or "",
            o["situacao"],
            p["ro"],
            p["data"],
            p.get("link") or "",
        ]
        for o in registros
        for p in o["portabilidade_vigente"]
    ]
    rows.sort(key=lambda r: (r[5], r[0]), reverse=True)
    return _csv(
        ["registro", "operadora", "uf", "situacao", "resolucao_operacional", "data", "link"], rows
    )


def fechamentos(registros: list[dict], hoje: date) -> str:
    """Operators whose ANS registration was cancelled in the last FECHAMENTOS_DIAS days, with the
    reason as the ANS writes it. Newest first."""
    desde = (hoje - timedelta(days=FECHAMENTOS_DIAS)).isoformat()
    rows = [
        [o["registro"], o["nome"], o.get("uf") or "", o["modalidade"], c["data"], c["motivo"]]
        for o in registros
        if (c := o.get("cancelamento")) and c["data"] >= desde
    ]
    rows.sort(key=lambda r: (r[4], r[0]), reverse=True)
    return _csv(["registro", "operadora", "uf", "modalidade", "data", "motivo"], rows)


def ressarcimento(registros: list[dict]) -> str:
    """SUS reimbursement per operator, as the ANS publishes it: amounts in reais, accumulated;
    the index is (pago + parcelado) / cobrado, in percent. By registro."""
    rows = []
    for o in sorted(registros, key=lambda o: o["registro"]):
        r = o.get("ressarcimento")
        if not r:
            continue
        rows.append(
            [
                o["registro"],
                o["nome"],
                r["competencia"],
                _decimal(r["valor_cobrado"]),
                _decimal(r["valor_pago"]),
                _decimal(r.get("valor_parcelado")),
                _decimal(r["indice_pagamento"]),
                _decimal(r["indice_pagamento_5anos"]),
            ]
        )
    return _csv(
        [
            "registro",
            "operadora",
            "competencia",
            "valor_cobrado",
            "valor_pago",
            "valor_parcelado",
            "indice_pagamento",
            "indice_pagamento_5anos",
        ],
        rows,
    )


def tabelas(registros: list[dict], hoje: date) -> dict[str, str]:
    """File name under dados/tabelas/ → CSV text."""
    return {
        "portabilidade-vigente.csv": portabilidade_vigente(registros),
        "fechamentos-12-meses.csv": fechamentos(registros, hoje),
        "ressarcimento-sus.csv": ressarcimento(registros),
    }
