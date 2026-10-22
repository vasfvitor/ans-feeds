"""Respostas medidas às perguntas da validação (IGR, junção pelo registro, IDSS, penalidades, CADOP).

Só biblioteca padrão. Rodar com `python3 -I pesquisa/scripts/validar.py DIR_DOWNLOADS`.
"""

import collections
import csv
import io
import re
import sys
from decimal import Decimal, ROUND_HALF_UP

D = sys.argv[1].rstrip("/")


def ler(nome):
    dados = open(f"{D}/{nome}", "rb").read()
    try:
        texto = dados.decode("utf-8")
    except UnicodeDecodeError:
        texto = dados.decode("latin-1")
    return list(csv.DictReader(io.StringIO(texto, newline=""), delimiter=";"))


def num(v):
    return Decimal(v.replace(",", "."))


def norm(reg):
    reg = reg.strip()
    return reg.zfill(6) if reg.isdigit() else reg


def titulo(t):
    print(f"\n### {t}")


ativas = ler("Relatorio_cadop.csv")
canceladas = ler("Relatorio_cadop_canceladas.csv")
igr = ler("pda-023-igr.csv")
tr = ler("pda-048-taxa_de_resolutividade.csv")
idss = ler("pda-020-historico-idss-2016_2025.csv")
dt = ler("pda-040-regimes_especiais_direcao_tecnica.csv")
prud = ler("pda-056-classificacao_prudencial.csv")
gar = ler("monit_garantia_atendimento.csv")
ress = ler("202609_Indice_de_Efetivo_Pagamento.csv")
hc = ler("HC_2026.csv")
pen = ler("penalidades_aplicadas_a_operadoras.csv")

# --- CADOP ---------------------------------------------------------------
titulo("CADOP")
reg_at = {norm(r["REGISTRO_OPERADORA"]) for r in ativas}
reg_ca = {norm(r["REGISTRO_OPERADORA"]) for r in canceladas}
print(f"ativas={len(reg_at)} canceladas={len(reg_ca)} nas_duas={len(reg_at & reg_ca)} {sorted(reg_at & reg_ca)[:10]}")
print("modalidades ativas:", collections.Counter(r["MODALIDADE"] for r in ativas).most_common())
cnpj_rep = collections.Counter(r["CNPJ"] for r in canceladas)
print(f"CNPJs repetidos nas canceladas: {sum(1 for n in cnpj_rep.values() if n > 1)} (máx {max(cnpj_rep.values())} registros)")
print("MOTIVO_DO_DESCREDENCIAMENTO:")
for m, n in collections.Counter(r["MOTIVO_DO_DESCREDENCIAMENTO"] for r in canceladas).most_common():
    print(f"  {n:5d} {m}")
datas = sorted(r["DATA_DESCREDENCIAMENTO"] for r in canceladas)
print(f"DATA_DESCREDENCIAMENTO {datas[0]} → {datas[-1]}; últimas 8:")
for r in sorted(canceladas, key=lambda r: r["DATA_DESCREDENCIAMENTO"])[-8:]:
    print(f"  {r['DATA_DESCREDENCIAMENTO']} {r['REGISTRO_OPERADORA']} {r['MODALIDADE'][:25]:25} {r['MOTIVO_DO_DESCREDENCIAMENTO']}")
por_ano = collections.Counter(r["DATA_DESCREDENCIAMENTO"][:4] for r in canceladas)
print("cancelamentos por ano (2019→):", {a: por_ano[a] for a in sorted(por_ano) if a >= "2019"})
reg_dat = sorted(r["DATA_REGISTRO_ANS"] for r in ativas)
print(f"DATA_REGISTRO_ANS ativas {reg_dat[0]} → {reg_dat[-1]}")

# --- IGR -----------------------------------------------------------------
titulo("IGR (pda-023)")
comps = collections.Counter(r["COMPETENCIA"] for r in igr)
cs = sorted(comps)
print(f"competências {cs[0]} → {cs[-1]} ({len(cs)}); linhas nas 3 últimas: {[(c, comps[c]) for c in cs[-3:]]}")
defas = collections.Counter((r["COMPETENCIA"], r["COMPETENCIA_BENEFICIARIO"]) for r in igr if r["COMPETENCIA"] >= "2026-01")
print("competência → competência_beneficiário (2026):", sorted(defas))
atual = collections.Counter((r["COMPETENCIA"] >= "2025-01", r["DT_ATUALIZACAO"] or "(vazio)") for r in igr)
print("DT_ATUALIZACAO por (comp ≥ 2025-01, valor):", dict(atual))
vazio_ate = max(r["COMPETENCIA"] for r in igr if not r["DT_ATUALIZACAO"])
cheio_de = min(r["COMPETENCIA"] for r in igr if r["DT_ATUALIZACAO"])
print(f"DT_ATUALIZACAO vazio até {vazio_ate}; preenchido a partir de {cheio_de}")
chave = collections.Counter((r["REGISTRO_OPERADORA"], r["COBERTURA"], r["COMPETENCIA"]) for r in igr)
print(f"(registro, cobertura, competência) repetidos: {sum(1 for n in chave.values() if n > 1)}")
print("COBERTURA:", collections.Counter(r["COBERTURA"] for r in igr))
print("PORTE:", collections.Counter(r["PORTE_OPERADORA"] for r in igr))

ok = {"100000": 0, "10000": 0}
falhas = []
for r in igr:
    q, b, v = num(r["QTD_RECLAMACOES"]), num(r["QTD_BENEFICIARIOS"]), num(r["IGR"])
    for base in ok:
        if b and (q / b * Decimal(base)).quantize(Decimal("0.01"), ROUND_HALF_UP) == v:
            ok[base] += 1
    if b and (q / b * 100000).quantize(Decimal("0.01"), ROUND_HALF_UP) != v:
        falhas.append(r)
print(f"linhas onde IGR = QTD_RECLAMACOES/QTD_BENEFICIARIOS × base (2 casas): ×100000={ok['100000']} ×10000={ok['10000']} de {len(igr)}")
for r in falhas[:5]:
    print("  não bate ×100000:", {k: r[k] for k in ("REGISTRO_OPERADORA", "COMPETENCIA", "IGR", "QTD_RECLAMACOES", "QTD_BENEFICIARIOS")})
zero_benef = sum(1 for r in igr if num(r["QTD_BENEFICIARIOS"]) == 0)
print(f"linhas com QTD_BENEFICIARIOS = 0: {zero_benef}")
print("10 maiores operadoras (MH) na última competência, IGR conferido:")
ult = sorted((r for r in igr if r["COMPETENCIA"] == cs[-1] and r["COBERTURA"] == "Assistência médica"),
             key=lambda r: -int(r["QTD_BENEFICIARIOS"]))[:10]
for r in ult:
    q, b = int(r["QTD_RECLAMACOES"]), int(r["QTD_BENEFICIARIOS"])
    print(f"  {r['REGISTRO_OPERADORA']} {r['RAZAO_SOCIAL'][:38]:38} {q:5d} / {b:9d} × 100000 = {q / b * 100000:7.2f}  CSV={r['IGR']}")
sem_reclamacao = sum(1 for r in igr if r["QTD_RECLAMACOES"] == "0")
print(f"linhas com QTD_RECLAMACOES = 0: {sem_reclamacao} (o CSV só traz operadora-mês com reclamação?)")
por_op_ult = {r["REGISTRO_OPERADORA"] for r in igr if r["COMPETENCIA"] == cs[-1]}
mh_at = {norm(r["REGISTRO_OPERADORA"]) for r in ativas if r["MODALIDADE"] != "Administradora de Benefícios"}
print(f"operadoras na última competência: {len(por_op_ult)}; ativas não-administradoras: {len(mh_at)}; ativas não-adm ausentes do IGR em {cs[-1]}: {len(mh_at - por_op_ult)}")
adm = {norm(r["REGISTRO_OPERADORA"]) for r in ativas if r["MODALIDADE"] == "Administradora de Benefícios"}
print(f"administradoras de benefícios com linha no IGR (qualquer competência): {len(adm & {r['REGISTRO_OPERADORA'] for r in igr})}")

# --- TR ------------------------------------------------------------------
titulo("TR (pda-048)")
ct = sorted({r["CD_COMPETENCIA"] for r in tr})
print(f"competências {ct[0]} → {ct[-1]} ({len(ct)}); faltam meses? {len(ct)} vs esperado", end=" ")
a0, m0 = map(int, ct[0].split("-"))
a1, m1 = map(int, ct[-1].split("-"))
print((a1 - a0) * 12 + m1 - m0 + 1)
print("TP_NATUREZA:", collections.Counter(r["TP_NATUREZA"] for r in tr))
tr_ok = sum(1 for r in tr if int(r["NR_DENOMINADOR"]) and (num(r["NR_NUMERADOR"]) / num(r["NR_DENOMINADOR"]) * 100).quantize(Decimal("0.01"), ROUND_HALF_UP) == num(r["VL_TR"]))
print(f"VL_TR = NUMERADOR/DENOMINADOR × 100: {tr_ok} de {len(tr)}")

# --- IDSS ----------------------------------------------------------------
titulo("IDSS (pda-020 2016_2025)")
cols = [c for c in idss[0] if re.fullmatch(r"ID[A-Z]{2}_\d{4}_\d{4}", c)]
nd = collections.Counter(r[c] for r in idss for c in cols if not re.fullmatch(r"[\d,]+", r[c]))
print(f"células de índice: {len(idss) * len(cols)}; não numéricas: {dict(nd)}")
nd_idss = {c[5:]: sum(1 for r in idss if r[c] == "ND") for c in cols if c.startswith("IDSS_")}
print("ND por ano no IDSS:", nd_idss)
todos_nd = [r for r in idss if all(r[c] == "ND" for c in cols)]
print(f"operadoras com todas as {len(cols)} células ND: {len(todos_nd)}")
for r in idss:
    if re.search(r"SUL ?AM[EÉ]RICA", r["RAZAO_SOCIAL"], re.I):
        ndc = sum(1 for c in cols if r[c] == "ND")
        st = "ativa" if r["REGISTRO_OPERADORA"] in reg_at else "cancelada" if r["REGISTRO_OPERADORA"] in reg_ca else "fora do CADOP"
        print(f"  Sul América: {r['REGISTRO_OPERADORA']} {r['RAZAO_SOCIAL'][:45]:45} {r['MODALIDADE'][:28]:28} ND={ndc}/{len(cols)} {st}; IDSS por ano: {[r[c] for c in cols if c.startswith('IDSS_')]}")
nd_status = collections.Counter(("ativa" if r["REGISTRO_OPERADORA"] in reg_at else "cancelada") for r in todos_nd)
print("todas-ND por situação no CADOP:", dict(nd_status))
print("faixa por valor (oficial: 1 = 0,80–1,00 … 5 = 0,00–0,19); longo para 3 operadoras:")
for r in sorted(idss, key=lambda r: r["REGISTRO_OPERADORA"])[:1] + [r for r in idss if r["REGISTRO_OPERADORA"] in ("005711", "368253")]:
    for c in cols:
        if c.startswith("IDSS_"):
            v = r[c]
            print(f"  {r['REGISTRO_OPERADORA']};{c[5:9]};{c[10:]};IDSS;{v}")

# --- Junção pelo registro ------------------------------------------------
titulo("Junção pelo registro com CADOP ativas ∪ canceladas")
cad = reg_at | reg_ca
fontes = {
    "IGR": [r["REGISTRO_OPERADORA"] for r in igr],
    "TR": [r["CD_REGISTRO_ANS"] for r in tr],
    "IDSS": [r["REGISTRO_OPERADORA"] for r in idss],
    "prudencial": [r["REGISTRO_OPERADORA"] for r in prud],
    "garantia": [r["REGISTRO_OPERADORA"] for r in gar],
    "ressarcimento 202609": [r["CODIGO_OPERADORA"] for r in ress],
    "HC 2026": [r["CD_OPERADORA"] for r in hc],
    "direção técnica": [r["REGISTRO_OPERADORA"] for r in dt],
    "penalidades": [r["REGISTRO_OPERADORA"] for r in pen if r["REGISTRO_OPERADORA"].strip()],
}
for nome, regs in fontes.items():
    brutos = set(regs)
    n = {norm(x) for x in brutos}
    sem_zero = sum(1 for x in brutos if x.strip().isdigit() and len(x.strip()) < 6)
    fora = sorted(n - cad)
    em_at = len(n & reg_at)
    print(f"{nome:22} distintos={len(n):5d} sem_zero_à_esquerda={sem_zero:4d} em_ativas={em_at:5d} em_canceladas={len(n & reg_ca):5d} "
          f"fora={len(fora):3d} ({100 * (len(n) - len(fora)) / len(n):.2f}% casam) {fora[:15]}")
    sem_norm = len(brutos & cad)
    if sem_norm != len(n) - len(fora):
        print(f"{'':22} sem normalizar casariam só {sem_norm}")

# --- Direção técnica -----------------------------------------------------
titulo("Direção técnica (pda-040)")
for r in dt:
    if not re.fullmatch(r"\d{6}", r["REGISTRO_OPERADORA"]):
        print(f"  registro fora do padrão: {r['REGISTRO_OPERADORA']!r} RO {r['RESOLUCAO_OPERACIONAL']} {r['DATA_PUBLICACAO']} {r['RAZAO_SOCIAL'][:40]}")
print("últimas 5:", [(r["DATA_PUBLICACAO"], r["RESOLUCAO_OPERACIONAL"], r["REGISTRO_OPERADORA"]) for r in sorted(dt, key=lambda r: r["DATA_PUBLICACAO"])[-5:]])
print("por ano (2018→):", {a: n for a, n in sorted(collections.Counter(r["ANO"] for r in dt).items()) if a >= "2018"})

# --- Prudencial, garantia, ressarcimento, HC -----------------------------
titulo("Prudencial, garantia, ressarcimento, HC")
print("prudencial trimestres:", sorted(collections.Counter(r["DT_TRIMESTRE_REFERENCIA"] for r in prud).items()))
print("prudencial classes:", collections.Counter(r["TP_CLASSIFICACAO"] for r in prud))
gc = sorted({(r["DT_INICIO_COMPETENCIA"], r["COMPETENCIA"]) for r in gar})
print(f"garantia: {gc[0][1]} → {gc[-1][1]} ({len(gc)} trimestres); faixas {collections.Counter(r['POSICAO'] for r in gar)}")
print("ressarcimento SITUACAO_OPERADORA:", collections.Counter(r["SITUACAO_OPERADORA"] for r in ress))
print("HC competências:", sorted(collections.Counter(r["COMPETENCIA"] for r in hc).items()))

# --- Penalidades ---------------------------------------------------------
titulo("Penalidades")
print("NR_COMPETENCIA_CARGA:", collections.Counter(r["NR_COMPETENCIA_CARGA"] for r in pen))


def iso(d):
    return f"{d[6:]}-{d[3:5]}-{d[:2]}" if d else ""


dec = sorted(iso(r["DT_DECISAO_1A"]) for r in pen)
pub = sorted(iso(r["DT_PUBLICACAO_1A_FINAL"]) for r in pen)
print(f"DT_DECISAO_1A {dec[0]} → {dec[-1]}; DT_PUBLICACAO_1A_FINAL {pub[0]} → {pub[-1]}")
mx = max(max(iso(r[c]) for c in r if c.startswith("DT_")) for r in pen)
print(f"data mais recente em qualquer coluna DT_*: {mx}")
ano = collections.Counter(iso(r["DT_DECISAO_1A"])[:4] for r in pen)
print("decisões 1ª instância por ano:", dict(sorted(ano.items())))
ultimos12 = [r for r in pen if iso(r["DT_DECISAO_1A"]) >= "2024-03"]
print(f"linhas com decisão 1A em 2024-03 → 2025-02: {sum(1 for r in ultimos12 if iso(r['DT_DECISAO_1A']) < '2025-03')}")
print(f"bytes/linha médio: {41160878 / len(pen):.0f}")
print("TIPO_PROCESSO:", collections.Counter(r["TIPO_PROCESSO"] for r in pen))
print("TIPO_PENALIDADE:", collections.Counter(r["TIPO_PENALIDADE"] for r in pen))
print("SITUACAO_OPERADORA:", collections.Counter(r["SITUACAO_OPERADORA"] for r in pen))
dup = collections.Counter(r["NR_PROCESSO"] for r in pen)
print(f"NR_PROCESSO repetidos: {sum(1 for n in dup.values() if n > 1)}")
print(f"NR_GRU com tabulação no início: {sum(1 for r in pen if r['NR_GRU'].startswith(chr(9)))}")
