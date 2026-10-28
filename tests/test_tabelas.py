import csv
import io
import json
from datetime import date

import pytest
from conftest import SNAPSHOTS

from ans_feeds import tabelas
from ans_feeds.cli import BASE_TAG, BASE_URL, PORTAL_URL
from ans_feeds.site import build_site


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    out = tmp_path_factory.mktemp("site")
    build_site(SNAPSHOTS, out, base_url=BASE_URL, base_tag=BASE_TAG, portal_url=PORTAL_URL)
    return out


def ler(path):
    raw = path.read_bytes()
    assert raw.startswith("﻿".encode())  # a spreadsheet in Portuguese opens it as UTF-8
    return list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig")), delimiter=";"))


def test_tables_hold_what_todas_holds(site):
    pasta = site / "dados" / "tabelas"
    todas = json.loads((site / "dados" / "todas.json").read_text(encoding="utf-8"))
    ops = {o["registro"]: o for o in todas["operadoras"]}

    port = ler(pasta / "portabilidade-vigente.csv")
    assert len(port) == sum(len(o["portabilidade_vigente"]) for o in ops.values()) > 0
    assert [r["data"] for r in port] == sorted((r["data"] for r in port), reverse=True)
    univida = [r for r in port if r["registro"] == "422134"]
    assert {r["resolucao_operacional"] for r in univida} == {"3049", "3022"}

    fech = ler(pasta / "fechamentos-12-meses.csv")
    desde = date.fromisoformat(todas["date"]).replace(
        year=date.fromisoformat(todas["date"]).year - 1
    )
    assert fech and all(r["data"] >= desde.isoformat() for r in fech)
    assert {
        "registro": "422134",
        "data": "2026-09-22",
        "motivo": "Liquidação Extrajudicial",
    }.items() <= next(r for r in fech if r["registro"] == "422134").items()

    sus = ler(pasta / "ressarcimento-sus.csv")
    assert len(sus) == sum(1 for o in ops.values() if o["ressarcimento"])
    abertta = next(r for r in sus if r["registro"] == "314668")
    assert abertta["valor_parcelado"] == "33664,10" and abertta["indice_pagamento"] == "100,00"


def test_decimal_comma_and_empty_for_missing():
    assert tabelas._decimal(1234.5) == "1234,50"
    assert tabelas._decimal(None) == ""
