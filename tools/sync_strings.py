#!/usr/bin/env python3
"""Sincroniza e valida os arquivos strings.po da skin Xperience1080.

Faixa reservada a skins: 31000-31999 (vide Language support do Kodi Wiki).

Modelo
------
``resource.language.en_gb/strings.po`` e o master: e ele que define o texto-fonte
(msgid) e o fallback do Kodi. Os demais idiomas sao derivados dele e nunca
introduzem msgid novo.

Os arquivos sao gerados de forma deterministica a partir de:
  1. o master (en_gb), que supplya msgid e ordem;
  2. SEED, abaixo, com as traducoes que ainda nao existiam nos arquivos;
  3. as traducoes ja presentes nos arquivos, que tem precedencia sobre SEED.

Uso
---
    python3 tools/sync_strings.py --check     # valida, exit != 0 se divergente
    python3 tools/sync_strings.py --fix       # regrava os 3 arquivos
    python3 tools/sync_strings.py --report    # diagnostico detalhado

Depois de editar os XML, rode ``--report`` para descobrir quais IDs novos
apareceram e cadastre-os em SEED.
"""

from __future__ import annotations

import argparse
import glob
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
XML_DIR = os.path.join(ROOT, "1080i")
LANG_DIR = os.path.join(ROOT, "language")

SKIN_ID_MIN = 31000
SKIN_ID_MAX = 32000

MASTER = "en_gb"
TARGETS = ("en_gb", "en_us", "pt_br")

# IDs que nao devem existir: nunca referenciados pelos XML nem presentes no master.
#   31129 "Use Classic Home"          - resquicio de versao antiga
#   31994 "Display Navigation Arrow"  - resquicio de versao antiga
#   31978-31981 "Home/Movie/TV/Music Tiles (cor)" - resquicio de versao antiga
RETIRED = frozenset({31129, 31978, 31979, 31980, 31981, 31994})

# Traducoes sem equivalente pt_br direto, mantidas em ingles.
PT_BR_KEEP_ENGLISH = frozenset({31034, 31036, 31111})

# --------------------------------------------------------------------------------------
# Textos novos (msgid == master). Chave = ID.
# --------------------------------------------------------------------------------------

# msgid novos no master._series que so existiam traducao em pt_br, nunca no master,
# entao Kodi exibia o ID cru para todo mundo que nao speak pt_br.
MASTER_SEED = {
    31092: "Hide information Season/EP",
    31093: "Hide OSD on Seeking",
    31095: "Pause OSD Delay (2 Sec)",
}

PT_BR_SEED = {
    31000: "Filmes Conhecidos",
    31002: "Verificando",
    31003: "Verificando atualizações",
    31004: "Séries Conhecidas",
    31005: "Papéis de Filmes Conhecidos",
    31006: "Papéis de Séries Conhecidos",
    31013: "Carregando Canais PVR...",
    31017: "Papéis de Séries de TV",
    31018: "Elenco de Séries de TV",
    31019: "Opções do Trakt",
    31020: "No Ar e a Seguir",
    31021: "Quadro",
    31028: "Reino Unido",
    31032: "Bloco de Imagens",
    31034: "Cyanide & Happiness",
    31036: "MyPicsDB",
    31038: "Caminho para Imagens",
    31039: "Blocos de Imagens (Roxo)",
    31040: "Redefinir Caminho das Imagens",
    31046: "Álbuns Aleatórios",
    31047: "Álbuns Recentes",
    31048: "Álbuns Recomendados",
    31049: "Músicas Aleatórias",
    31050: "Definir Caminho das Imagens",
    31051: "Caminho de Imagem Personalizado",
    31092: "Ocultar informação de Season/EP",
    31093: "Ocultar OSD enquanto Procura",
    31095: "Atraso no OSD de Pausa (2 Seg)",
    31106: "Exibir Fanart acima da Visualização",
    31111: "Skin",
    31115: "Retroceder",
    31116: "Avançar",
    31117: "Canal anterior",
    31118: "Próximo canal",
    31119: "Retroceder rápido",
    31120: "Avançar rápido",
    31121: "Lista de canais",
    31122: "Configurações da visualização",
    31200: "Exibir Botão de Liga/Desliga (não afeta a tela inicial)",
    31314: "Primeira exibição: ",
    31696: "24 Horas em Detalhe",
    31900: "Informações do Reprodutor",
    31901: "Decodificador de vídeo",
    31902: "Formato de pixel",
    31953: "Editar Filme",
}

# Textos novos so para en_us (variacoes de ortografia americana).
# Todo o resto recebe msgstr == msgid do master.
EN_US_SEED = {
    31122: "Visualization settings",
}

# --------------------------------------------------------------------------------------
# Correcoes sobre traducoes ja existentes (sobrescrevem o que esta no arquivo).
# --------------------------------------------------------------------------------------
PT_BR_FIX = {
    # msgid estava divergente do master
    31220: "TV ao Vivo",
    31551: "Em Andamento",
    31977: "Nenhuma fonte de mídia disponível",
}

EN_US_FIX = {
    # msgstr estava em portugues
    31094: "Hide Progress Bar",
    # msgstr estava em espanhol
    31920: "Recently Added",
}

# msgid divergente do master, por idioma.
MSGID_OVERRIDE = {
    31220: "TV",
    31551: "Ongoing Episodes",
    31977: "No Content available",
}

HEADERS = {
    "en_gb": """\
# Xperience1080 Kodi Skin
# https://github.com/xperience1080/skin.xperience1080
#
msgid ""
msgstr ""
"Project-Id-Version: Xperience1080\\n"
"Report-Msgid-Bugs-To: \\n"
"PO-Revision-Date: YEAR-MO-DA HO:MI+ZONE\\n"
"Last-Translator: \\n"
"Language-Team: Team-Kodi\\n"
"MIME-Version: 1.0\\n"
"Content-Type: text/plain; charset=UTF-8\\n"
"Content-Transfer-Encoding: 8bit\\n"
"Plural-Forms: nplurals=2; plural=n != 1;\\n"
"Language: en\\n"
""",
    "en_us": """\
# Kodi Media Center language file
# Addon Name: Xperience1080
# Addon id: skin.xperience1080
# Addon Provider: Piers|xhaggi
msgid ""
msgstr ""
"Project-Id-Version: Kodi Addons\\n"
"Report-Msgid-Bugs-To: https://forum.kodi.tv/\\n"
"POT-Creation-Date: YEAR-MO-DA HO:MI+ZONE\\n"
"PO-Revision-Date: YEAR-MO-DA HO:MI+ZONE\\n"
"Last-Translator: Kodi Translation Team\\n"
"Language-Team: Team-Kodi\\n"
"MIME-Version: 1.0\\n"
"Content-Type: text/plain; charset=UTF-8\\n"
"Content-Transfer-Encoding: 8bit\\n"
"Language: en_US\\n"
"Plural-Forms: nplurals=2; plural=(n != 1);\\n"
""",
    "pt_br": """\
# Kodi Media Center language file
# Addon Name: Xperience1080
# Addon id: skin.xperience1080
# Addon Provider: Piers|xhaggi
msgid ""
msgstr ""
"Project-Id-Version: Kodi Addons\\n"
"Report-Msgid-Bugs-To: https://forum.kodi.tv/\\n"
"POT-Creation-Date: YEAR-MO-DA HO:MI+ZONE\\n"
"PO-Revision-Date: YEAR-MO-DA HO:MI+ZONE\\n"
"Last-Translator: Kodi Translation Team\\n"
"Language-Team: Team-Kodi\\n"
"MIME-Version: 1.0\\n"
"Content-Type: text/plain; charset=UTF-8\\n"
"Content-Transfer-Encoding: 8bit\\n"
"Language: pt_BR\\n"
"Plural-Forms: nplurals=2; plural=(n > 1);\\n"
""",
}


# --------------------------------------------------------------------------------------
# Parsing / rendering
# --------------------------------------------------------------------------------------
_BLOCK = re.compile(r'msgctxt\s+"#(\d+)"(.*?)(?=\n\s*\n|\Z)', re.S)
_MSGID = re.compile(r'msgid\s+((?:"(?:[^"\\]|\\.)*"\s*)+)')
_MSGSTR = re.compile(r'msgstr\s+((?:"(?:[^"\\]|\\.)*"\s*)+)')


_UNESCAPE = {"n": "\n", "t": "\t", "r": "\r", '"': '"', "\\": "\\"}
_SEGMENT = re.compile(r'"((?:[^"\\]|\\.)*)"')


def _unquote(blob: str) -> str:
    """Concatena os segmentos de uma string .po e resolve os escapes gettext."""
    raw = "".join(_SEGMENT.findall(blob))
    return re.sub(r"\\(.)", lambda m: _UNESCAPE.get(m.group(1), m.group(1)), raw)


def parse_po_text(text: str) -> dict[int, dict[str, str]]:
    """Extrai {id: {msgid, msgstr}}. Entradas duplicadas: a ultima vence."""
    out: dict[int, dict[str, str]] = {}
    for match in _BLOCK.finditer(text):
        entry = match.group(2)
        id_m = _MSGID.search(entry)
        str_m = _MSGSTR.search(entry)
        out[int(match.group(1))] = {
            "msgid": _unquote(id_m.group(1)) if id_m else "",
            "msgstr": _unquote(str_m.group(1)) if str_m else "",
        }
    return out


def parse_po(path: str) -> dict[int, dict[str, str]]:
    with open(path, encoding="utf-8") as fh:
        return parse_po_text(fh.read())


def render_po(lang: str, entries: dict[int, dict[str, str]]) -> str:
    lines = [HEADERS[lang], ""]
    for id_ in sorted(entries):
        entry = entries[id_]
        lines.append(f'msgctxt "#{id_}"')
        lines.append(f'msgid "{_escape(entry["msgid"])}"')
        lines.append(f'msgstr "{_escape(entry["msgstr"])}"')
        lines.append("")
    return "\n".join(lines)


def _escape(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\t", "\\t")
        .replace("\n", "\\n")
    )


def po_path(lang: str) -> str:
    return os.path.join(LANG_DIR, f"resource.language.{lang}", "strings.po")


# --------------------------------------------------------------------------------------
# Fontes de ID
# --------------------------------------------------------------------------------------
_ID_PATTERNS = (
    re.compile(r"\$LOCALIZE\[(\d+)\]"),
    re.compile(r"\$INFO\[(?:skin\.string|skin\.str|localize)\[(\d+)\]\]", re.I),
    re.compile(r'<string id="(\d+)"'),
)


def collect_used_ids() -> set[int]:
    """IDs 31xxx referenciados pelos XML da skin."""
    found: set[int] = set()
    for xml in glob.glob(os.path.join(XML_DIR, "**", "*.xml"), recursive=True):
        with open(xml, encoding="utf-8", errors="ignore") as fh:
            body = fh.read()
        for pattern in _ID_PATTERNS:
            for raw in pattern.findall(body):
                value = int(raw)
                if SKIN_ID_MIN <= value < SKIN_ID_MAX:
                    found.add(value)
    return found


def build_master(existing_master: dict[int, dict[str, str]]) -> dict[int, str]:
    """msgid canonico por ID, somente leitura do master.

    IDs ja órfãos no master sao preservados: removê-los quebraria skins
    antigas ainda em circulacao. IDs que so existem em en_us sao descartados
    (ver RETIRED) -- a unica divergencia real era #31129/#31994.
    """
    master: dict[int, str] = {}
    for id_, entry in existing_master.items():
        if id_ in RETIRED:
            continue
        text = MSGID_OVERRIDE.get(id_, entry["msgid"]) or entry["msgid"]
        master[id_] = text
    for id_, text in MASTER_SEED.items():
        master.setdefault(id_, text)
    return master


def build_target(
    lang: str,
    master: dict[int, str],
    existing: dict[int, dict[str, str]],
) -> dict[int, dict[str, str]]:
    """Monta o arquivo final de um idioma a partir do master + traducoes vigentes."""
    seed = EN_US_SEED if lang == "en_us" else ({} if lang == MASTER else PT_BR_SEED)
    fixes = EN_US_FIX if lang == "en_us" else ({} if lang == MASTER else PT_BR_FIX)

    out: dict[int, dict[str, str]] = {}
    for id_, msgid in master.items():
        # O master nao traduz: msgstr vazio e o proprio fallback do Kodi, que
        # le o msgid. Qualquer msgstr aqui e um bug de origem.
        if lang == MASTER:
            out[id_] = {"msgid": msgid, "msgstr": ""}
            continue

        current = existing.get(id_)
        if current and current["msgstr"].strip():
            translation = current["msgstr"]
        elif id_ in seed:
            translation = seed[id_]
        elif lang == "en_us":
            translation = msgid
        else:
            translation = ""

        if id_ in fixes:
            translation = fixes[id_]

        out[id_] = {"msgid": msgid, "msgstr": translation}
    return out


# --------------------------------------------------------------------------------------
# Driver
# --------------------------------------------------------------------------------------
def generate() -> dict[str, str]:
    existing_master = parse_po(po_path(MASTER))
    master = build_master(existing_master)
    result = {}
    for lang in TARGETS:
        existing = existing_master if lang == MASTER else parse_po(po_path(lang))
        entries = build_target(lang, master, existing)
        result[lang] = render_po(lang, entries)
    return result


def report() -> int:
    existing_master = parse_po(po_path(MASTER))
    master = build_master(existing_master)
    used = collect_used_ids()
    problems = 0

    print(f"IDs referenciados nos XML : {len(used)}")
    print(f"IDs no master (en_gb)      : {len(master)}")
    orphan = sorted(set(master) - used)
    print(f"Orfãos no master          : {len(orphan)}")
    missing = sorted(used - set(master))
    if missing:
        problems += 1
        print(f"\n!! IDs usados nos XML e ausentes no master ({len(missing)}):")
        for id_ in missing:
            print(f"   #{id_}")
    else:
        print("OK: todo ID usado nos XML existe no master")

    for lang in TARGETS:
        entries = parse_po(po_path(lang))
        if lang == MASTER:
            empty = [i for i in entries if not entries[i]["msgstr"].strip()]
            # master usa msgstr vazio por design; reporta so msgstr nao-vazio indevido
            stray = [i for i, e in entries.items() if e["msgstr"].strip()]
            print(f"\n{lang}: {len(entries)} entradas, {len(stray)} com msgstr (esperado 0)")
            if stray:
                problems += 1
                for id_ in stray:
                    print(f"   !! #{id_} msgstr={entries[id_]['msgstr']!r}")
            continue
        empty = sorted(i for i in master if not entries.get(i, {}).get("msgstr", "").strip())
        extra = sorted(set(entries) - set(master))
        order = list(entries)
        print(
            f"\n{lang}: {len(entries)} entradas | vazias: {len(empty)} | "
            f"extras: {len(extra)} | ordem: {'crescente' if order == sorted(order) else 'NAO crescente'}"
        )
        if extra:
            problems += 1
            print(f"   !! fora do master: {extra}")
        if empty:
            problems += 1
            print(f"   !! sem traducao: {empty}")

    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true", help="valida sem escrever (exit != 0 em falha)")
    group.add_argument("--fix", action="store_true", help="regrava os arquivos")
    group.add_argument("--report", action="store_true", help="diagnostico detalhado")
    args = parser.parse_args()

    if args.report:
        return 1 if report() else 0

    wanted = generate()
    drift = []
    for lang, content in wanted.items():
        path = po_path(lang)
        with open(path, encoding="utf-8") as fh:
            current = fh.read()
        if current == content:
            print(f"{lang}: em dia")
        else:
            drift.append(lang)

    if args.fix:
        if not drift:
            print("\nTudo em dia.")
            return 0
        for lang in drift:
            with open(po_path(lang), "w", encoding="utf-8", newline="\n") as fh:
                fh.write(wanted[lang])
            print(f"{lang}: regravado")
        return 0

    # --check: drift dos arquivos + invariante XML->master. Falha se qualquer um falhar.
    status = 0
    if drift:
        print(f"\nDivergentes: {', '.join(drift)}  (rode com --fix)")
        status = 1
    else:
        print("\nArquivos em dia.")
    status |= 1 if report() else 0
    if status == 0:
        print("\nTudo em dia.")
    return status


if __name__ == "__main__":
    sys.exit(main())