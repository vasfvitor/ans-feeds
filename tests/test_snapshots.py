from datetime import datetime, timezone

from conftest import SNAPSHOTS, write_day

from ans_feeds import snapshots


def lines(path):
    return path.read_text(encoding="utf-8").split()


def test_versions_skip_days_without_the_file(tree):
    write_day(tree, "2026-10-22", {"a.csv": "x", "b.csv": "1"})
    write_day(tree, "2026-10-23", {"a.csv": "y"}, at="2026-10-23T10:30:00Z")
    (tree / "lixo").mkdir()
    assert snapshots.days(tree) == ["2026-10-22", "2026-10-23"]
    assert [d for d, _ in snapshots.versions(tree, "a.csv")] == ["2026-10-22", "2026-10-23"]
    assert snapshots.latest(tree, "b.csv") == tree / "2026-10-22" / "b.csv"
    assert snapshots.latest(tree, "c.csv") is None


def test_collected_at_reads_fontes(tree):
    write_day(tree, "2026-10-22", {"a.csv": "x"})
    write_day(tree, "2026-10-23", {"a.csv": "y"}, at="2026-10-23T10:30:00Z")
    assert snapshots.collected_at(tree, "2026-10-22", "a.csv") is None
    assert snapshots.collected_at(tree, "2026-10-23", "a.csv") == datetime(
        2026, 10, 23, 10, 30, tzinfo=timezone.utc
    )


def test_first_seen_leaves_the_baseline_out(tree):
    write_day(tree, "2026-10-22", {"a.csv": "k1 k2"})
    write_day(tree, "2026-10-23", {"a.csv": "k1 k2 k3"}, at="2026-10-23T10:30:00Z")
    write_day(tree, "2026-10-24", {"b.csv": "z"}, at="2026-10-24T10:30:00Z")
    write_day(tree, "2026-10-25", {"a.csv": "k2 k3 k4"}, at="2026-10-25T10:31:00Z")
    seen = snapshots.first_seen(tree, "a.csv", lines)
    assert set(seen) == {"k3", "k4"}
    assert seen["k3"] == ("2026-10-23", datetime(2026, 10, 23, 10, 30, tzinfo=timezone.utc))
    assert seen["k4"][0] == "2026-10-25"


def test_real_tree():
    assert snapshots.days(SNAPSHOTS)[:2] == ["2026-10-22", "2026-10-23"]
    assert snapshots.latest(SNAPSHOTS, "Relatorio_cadop_canceladas.csv").parent.name == "2026-10-22"
    assert [d for d, _ in snapshots.versions(SNAPSHOTS, "Relatorio_cadop.csv")][:2] == [
        "2026-10-22",
        "2026-10-23",
    ]


def test_falhas_reads_what_the_last_run_could_not_update(tree):
    assert snapshots.falhas(tree) == []  # no file: nothing failed
    (tree / "FALHAS.tsv").write_text(
        "2026-10-29\tpda-023-igr.csv\t1354 bytes contra 6756 na versão anterior\n", encoding="utf-8"
    )
    assert snapshots.falhas(tree) == [
        {
            "dia": "2026-10-29",
            "fonte": "pda-023-igr.csv",
            "motivo": "1354 bytes contra 6756 na versão anterior",
        }
    ]


def test_a_failed_source_gets_the_subject_the_portal_labels():
    from ans_feeds.site import assunto_da_fonte

    assert assunto_da_fonte("pda-023-igr.csv") == "reclamacoes"
    assert assunto_da_fonte("202609_Indice_de_Efetivo_Pagamento.csv") == "ressarcimento"
    assert assunto_da_fonte("HC_2027.csv") == "ressarcimento"
    assert assunto_da_fonte("listas RN 623") == assunto_da_fonte("Lista_1T2026.pdf") == "rn623"
    assert assunto_da_fonte("Relatorio_cadop.csv") == "cadastro"
    assert assunto_da_fonte("outra.csv") is None
