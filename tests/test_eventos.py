from collections import Counter
from datetime import date, datetime, timezone

from conftest import FIXTURES, SNAPSHOTS, write_day

from ans_feeds import eventos


def fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def test_registro_normalization():
    assert eventos.registro("27") == "000027"
    assert eventos.registro("303623 ") == "303623"
    assert eventos.registro("X00002") is None


def test_events_from_fixture_heads(tree):
    write_day(
        tree,
        "2026-10-22",
        {
            eventos.ATIVAS: fixture("cadop_ativas_head.csv"),
            eventos.CANCELADAS: fixture("cadop_canceladas_head.csv"),
            eventos.DIRECAO_TECNICA: fixture("direcao_tecnica_head.csv"),
        },
    )
    canc = eventos.cancelamentos(tree)
    regs = eventos.registros(tree)
    dt = eventos.direcao_tecnica(tree)
    assert len(canc) == 50 and len(regs) == 100 and len(dt) == 50
    first = next(e for e in canc if e.registro == "410942")
    assert first.chave == "410942/2003-12-19"
    assert first.data == date(2003, 12, 19)
    assert first.detalhes["Motivo"] == "Pedido de cancelamento"
    assert "Telefone" not in first.detalhes and "E-mail" not in first.detalhes
    x = next(e for e in dt if e.chave.endswith("/X00002"))
    assert x.registro is None and x.chave == "156/X00002"
    # baseline only: nobody has a collection time
    assert all(e.visto_em is None for e in canc + regs + dt)
    assert canc[0].updated.utcoffset().total_seconds() == -3 * 3600


def test_visto_em_for_a_cancellation_that_shows_up_later(tree):
    head = fixture("cadop_canceladas_head.csv")
    write_day(tree, "2026-10-22", {eventos.CANCELADAS: head})
    nova = (
        b'"999999";"00000000000191";"OPERADORA NOVA LTDA";;"Medicina de Grupo";;;;;"Recife";"PE";'
        b';;;;;;;;"2020-01-02";"2026-10-30";"Liquida\xc3\xa7\xc3\xa3o Extrajudicial"\n'
    )
    write_day(tree, "2026-10-31", {eventos.CANCELADAS: head + nova}, at="2026-10-31T10:30:05Z")
    canc = {e.chave: e for e in eventos.cancelamentos(tree)}
    e = canc["999999/2026-10-30"]
    assert e.destaque
    assert e.visto_em == datetime(2026, 10, 31, 10, 30, 5, tzinfo=timezone.utc)
    assert e.updated == e.visto_em
    assert sum(1 for x in canc.values() if x.visto_em) == 1


def test_real_snapshots():
    canc = eventos.cancelamentos(SNAPSHOTS)
    regs = eventos.registros(SNAPSHOTS)
    dt = eventos.direcao_tecnica(SNAPSHOTS)
    for lista in (canc, regs, dt):
        dup = [k for k, n in Counter(e.id for e in lista).items() if n > 1]
        assert not dup, dup
        assert all("//" not in e.id and not e.id.endswith("/") for e in lista)
    assert max(e.data for e in canc) >= date(2026, 10, 9)
    ro3077 = [e for e in dt if e.detalhes["Resolução Operacional"] == "3077"]
    assert ro3077 and ro3077[0].data == date(2025, 12, 11)
    assert next(e for e in regs if e.registro == "425010").data == date(2026, 7, 24)
    assert canc[0].fonte.startswith("https://dadosabertos.ans.gov.br/")
