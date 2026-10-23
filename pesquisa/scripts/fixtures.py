"""Corta as fixtures de pesquisa/fixtures/: cabeçalho + 50 registros por CSV, byte a byte, e headers_<nome>.txt.

Receita do CONTRIBUTING.md do anvisa. Só biblioteca padrão.
Rodar com `python3 -I pesquisa/scripts/fixtures.py DIR_DOWNLOADS [DIR_DOWNLOADS…] pesquisa/fixtures`; cada arquivo
vem da última pasta (`…/AAAA-MM-DD`) que o tenha, e essa data vai para o manifest.
"""

import csv
import io
import json
import os
import re
import sys

REGISTROS = 50
# Linhas que os 50 primeiros registros não cobrem, por regex sobre os bytes da linha (até 3 por regex).
CASOS = {
    "garantia": {"registro sem zero à esquerda (inteiro sem aspas)": rb'^[^;]*;[^;]*;[^;]*;\d{1,5};'},
    "hc": {"registro de 5 dígitos": rb'^"?\d{5}"?;'},
    "ressarcimento_indice": {"registro de 5 dígitos": rb'^[^;]*;"?\d{5}"?;'},
    "igr": {"DT_ATUALIZACAO vazio (competência ≤ 2019-04)": rb';"?"?\r?$',
            "registro repetido com duas razões sociais em 2019-04": rb'^"304212";.*"2019-04"',
            "IGR com 1 casa (2015-2018)": rb'^"303267";[^;]*;"Assist[^;]*;2,00;2;97402;'},
    "penalidades": {"registro vazio": rb'^[^;]*;[^;]*;[^;]*;[^;]*;;',
                    "registro de 5 dígitos": rb'^[^;]*;[^;]*;[^;]*;[^;]*;"?\d{5}"?;'},
    "idss_2016_2025": {"todas as células ND (Sul América 000043, incorporada em 2013)": rb'^"000043";'},
    "reajuste_agrupamento": {"subagrupado (PCT_UNICO vazio, percentuais por segmentação)": rb'^"\d{6}";\d{4};"Subagrupado";',
                             "reajuste negativo": rb'^"\d{6}";\d{4};[^;]*;-',
                             "354511 no ciclo 2025 (90,35% e QT_BENEF 13 vezes o do ciclo anterior)": rb'^"354511";2025;'},
}
ARQUIVOS = {
    "cadop_ativas": ("Relatorio_cadop.csv", "operadoras_de_plano_de_saude_ativas/"),
    "cadop_canceladas": ("Relatorio_cadop_canceladas.csv", "operadoras_de_plano_de_saude_canceladas/"),
    "igr": ("pda-023-igr.csv", "IGR/IGR_versao_2023/"),
    "tr": ("pda-048-taxa_de_resolutividade.csv", "taxa_de_resolutividade/"),
    "idss_2016_2025": ("pda-020-historico-idss-2016_2025.csv", "historico_idss-020/"),
    "direcao_tecnica": ("pda-040-regimes_especiais_direcao_tecnica.csv", "regimes_especiais_direcao_tecnica/"),
    "prudencial": ("pda-056-classificacao_prudencial.csv", "classificacao_prudencial-056/"),
    "garantia": ("monit_garantia_atendimento.csv", "monitoramento_garantia_atendimento/"),
    "ressarcimento_indice": ("202609_Indice_de_Efetivo_Pagamento.csv", "ressarcimento_ao_SUS_indice_efetivo_pagamento/"),
    "hc": ("HC_2026.csv", "hc_ressarcimento_sus/"),
    "penalidades": ("penalidades_aplicadas_a_operadoras.csv", "penalidades_aplicadas_a_operadoras/"),
    "reajuste_agrupamento": ("pda-055-Percentuais_de_Reajuste_de_Agrupamento.csv", "percentuais_de_reajuste_de_agrupamento-055/"),
}


def main():
    origens, destino = [p.rstrip("/") for p in sys.argv[1:-1]], sys.argv[-1].rstrip("/")
    primeiro = os.path.basename(origens[0])
    entradas = []
    for nome, (arq, pasta) in ARQUIVOS.items():
        origem = [o for o in origens if os.path.exists(f"{o}/{arq}")][-1]
        dia = os.path.basename(origem)
        dados = open(f"{origem}/{arq}", "rb").read()
        try:
            texto, enc = dados.decode("utf-8"), "UTF-8"
        except UnicodeDecodeError:
            texto, enc = dados.decode("latin-1"), "Latin-1 (ISO-8859-1)"
        if all(b < 128 for b in dados):
            enc = "ASCII"
        registros = list(csv.reader(io.StringIO(texto, newline=""), delimiter=";"))
        linhas = dados.count(b"\n")
        # Nenhum campo tem quebra de linha: um registro por linha, então cortar por linha é cortar por registro.
        assert len(registros) == linhas, (nome, len(registros), linhas)
        fim = 0
        for _ in range(REGISTROS + 1):
            fim = dados.index(b"\n", fim) + 1
        open(f"{destino}/{nome}_head.csv", "wb").write(dados[:fim])
        casos = {}
        if nome in CASOS:
            linhas_b = dados.split(b"\n")
            cab, corpo = linhas_b[0], [l for l in linhas_b[1:] if l]
            escolhidas = set()
            for desc, rx in CASOS[nome].items():
                achadas = [i for i, l in enumerate(corpo) if re.search(rx, l)][:3]
                assert achadas, (nome, desc)
                casos[desc] = len(achadas)
                escolhidas.update(achadas)
            with open(f"{destino}/{nome}_casos.csv", "wb") as f:
                f.write(cab + b"\n" + b"".join(corpo[i] + b"\n" for i in sorted(escolhidas)))
        brutos = open(f"{origem}/headers/{arq}.txt", "rb").read().decode("latin-1").replace("\r\n", "\n").strip("\n")
        # O proxy do sandbox antepõe a resposta do CONNECT; ela não é da ANS.
        brutos = brutos.split("\n\n")[-1]
        crlf = "CRLF" if b"\r\n" in dados else "LF"
        nota = (f"body: {len(dados):,} bytes, {enc}, {crlf}, {len(registros) - 1:,} records (not kept); "
                f"{nome}_head.csv is the header plus the first {REGISTROS} of those records, cut byte for byte.")
        open(f"{destino}/headers_{nome}.txt", "w", encoding="utf-8", newline="\n").write(f"{brutos}\n\n{nota}\n")
        entradas.append({"name": nome, "method": "GET", "path": f"/FTP/PDA/{pasta}{arq}", "status": 200,
                         **({"recorded": dia} if dia != primeiro else {}),
                         "file": f"headers_{nome}.txt", "sample": f"{nome}_head.csv",
                         "note": f"{len(dados):,} bytes, {enc}, {len(registros) - 1:,} records, not kept",
                         **({"cases": f"{nome}_casos.csv", "cases_cover": casos} if casos else {})})
        print(f"{nome}: {fim:,} de {len(dados):,} bytes")
    manifest = {
        "recorded": primeiro,
        "notes": ("Arquivos reais do FTP de dados abertos da ANS, https://dadosabertos.ans.gov.br/FTP/PDA/ (sem auth, "
                  "sem robots.txt). headers_*.txt guarda a resposta HTTP (curl -D) e uma nota; *_head.csv o cabeçalho "
                  "mais os primeiros 50 registros, copiados byte a byte (nunca reencodar; .gitattributes marca -text). "
                  "Nenhum campo tem quebra de linha. Os casos que os 50 primeiros não cobrem estão em *_casos.csv "
                  "(cabeçalho + linhas inteiras escolhidas por regex, também byte a byte; ver cases_cover)."),
        "responses": entradas,
    }
    with open(f"{destino}/manifest.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
        f.write("\n")


main()
