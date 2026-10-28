from datetime import datetime, timezone

from conftest import write_day

from ans_feeds import feed_operadora
from ans_feeds.operadoras import IGR

IDSS_2025 = "pda-020-historico-idss-2016_2025.csv"  # the name today; it grows a year at a time


def igr(*competencias: str) -> str:
    return "COMPETENCIA;REGISTRO_OPERADORA\n" + "".join(f"{c};005711\n" for c in competencias)


def test_quarters_and_score_years_are_dated_by_the_collection_that_first_held_them(tree):
    write_day(
        tree,
        "2026-10-22",
        {IGR: igr("2026-01", "2026-02", "2026-03", "2026-04"), IDSS_2025: "IDSS_2025_2024;X\n"},
        at="2026-10-22T10:00:00Z",
    )
    write_day(
        tree,
        "2026-11-05",
        {IGR: igr("2026-01", "2026-02", "2026-03", "2026-04", "2026-05", "2026-06")},
        at="2026-11-05T10:30:00Z",
    )
    trimestres, anos = feed_operadora.vistos(tree)
    assert trimestres == {
        "1T2026": datetime(2026, 10, 22, 10, tzinfo=timezone.utc),
        "2T2026": datetime(2026, 11, 5, 10, 30, tzinfo=timezone.utc),
    }
    assert anos == {"2025_2024": datetime(2026, 10, 22, 10, tzinfo=timezone.utc)}


def test_quarter_in_words():
    assert feed_operadora.trimestre_extenso("3T2026") == "julho a setembro de 2026"
    assert feed_operadora.trimestre_extenso("1T2025") == "janeiro a março de 2025"


def test_a_renamed_score_file_is_the_next_version_and_its_new_year_is_dated(tree):
    # the ANS adds a year by renaming the file (…2016_2025.csv → …2016_2026.csv): the new year is
    # new against the old name's version, not swallowed as the baseline of a "new" file
    write_day(tree, "2026-10-22", {IDSS_2025: "IDSS_2025_2024;X\n"}, at="2026-10-22T10:00:00Z")
    write_day(
        tree,
        "2027-06-30",
        {"pda-020-historico-idss-2016_2026.csv": "IDSS_2025_2024;IDSS_2026_2025;X\n"},
        at="2027-06-30T10:00:00Z",
    )
    _, anos = feed_operadora.vistos(tree)
    assert anos == {
        "2025_2024": datetime(2026, 10, 22, 10, tzinfo=timezone.utc),
        "2026_2025": datetime(2027, 6, 30, 10, tzinfo=timezone.utc),
    }
