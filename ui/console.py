"""
Interfaz de consola sin dependencias: colores ANSI, paneles y tablas.
Funciona en la terminal de VS Code, Windows Terminal y PowerShell.
"""

import os
import shutil
import sys

if os.name == "nt":  # activa secuencias ANSI en consolas de Windows
    os.system("")
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass

NO_COLOR = bool(os.environ.get("NO_COLOR")) or not sys.stdout.isatty()


def _c(code):
    return "" if NO_COLOR else f"\033[{code}m"


RESET, BOLD, DIM = _c(0), _c(1), _c(2)
RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, GRAY = (_c(c) for c in (31, 32, 33, 34, 35, 36, 90))
BRED, BGREEN, BYELLOW, BCYAN = (_c(c) for c in ("1;31", "1;32", "1;33", "1;36"))


def width():
    return min(shutil.get_terminal_size((110, 30)).columns, 120)


def _vis(s):
    import re
    return len(re.sub(r"\033\[[0-9;]*m", "", str(s)))


def pad(s, n, align="<"):
    s = str(s)
    gap = max(0, n - _vis(s))
    if align == ">":
        return " " * gap + s
    if align == "^":
        return " " * (gap // 2) + s + " " * (gap - gap // 2)
    return s + " " * gap


def banner(title, subtitle=""):
    w = width()
    print()
    print(BCYAN + "╔" + "═" * (w - 2) + "╗" + RESET)
    print(BCYAN + "║" + RESET + BOLD + pad(title, w - 2, "^") + RESET + BCYAN + "║" + RESET)
    if subtitle:
        print(BCYAN + "║" + RESET + GRAY + pad(subtitle, w - 2, "^") + RESET + BCYAN + "║" + RESET)
    print(BCYAN + "╚" + "═" * (w - 2) + "╝" + RESET)


def section(title):
    w = width()
    print()
    print(BOLD + CYAN + "■ " + title.upper() + RESET + " " + GRAY + "─" * max(0, w - len(title) - 3) + RESET)


def kv(pairs, cols=2, key_w=18):
    """Pares clave-valor en columnas."""
    pairs = list(pairs)
    w = width()
    col_w = w // cols
    for i in range(0, len(pairs), cols):
        line = ""
        for k, v in pairs[i:i + cols]:
            line += pad(GRAY + str(k) + RESET, key_w) + pad(v, col_w - key_w)
        print("  " + line.rstrip())


def fmt_num(v, dec=2, pct=False, sign=False):
    if v is None:
        return GRAY + "-" + RESET
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v)
    if f != f:
        return GRAY + "-" + RESET
    s = f"{f:+,.{dec}f}" if sign else f"{f:,.{dec}f}"
    return s + ("%" if pct else "")


def colored(v, s=None, good=0.0):
    """Verde si v>good, rojo si v<good."""
    s = s if s is not None else fmt_num(v, sign=True)
    try:
        f = float(v)
    except (TypeError, ValueError):
        return s
    return (GREEN if f > good else RED if f < good else "") + s + RESET


def verdict_badge(text):
    t = str(text).upper()
    if any(k in t for k in ("FAVORABLE", "SIGNIFICATIVA", "LONG", "INTEGRA")) and "DES" not in t:
        col = BGREEN
    elif any(k in t for k in ("DESFAVORABLE", "SIN VENTAJA", "SHORT", "ALERTA")):
        col = BRED
    elif any(k in t for k in ("MARGINAL", "PROBABLE", "DEBIL", "REDUCIDO", "CONFLICTO")):
        col = BYELLOW
    else:
        col = BOLD
    return f"{col}[ {text} ]{RESET}"


def score_bar(score, n=24):
    if score is None:
        return "-"
    k = int(round(max(0, min(100, score)) / 100 * n))
    col = GREEN if score >= 65 else YELLOW if score >= 45 else RED
    return col + "█" * k + RESET + GRAY + "░" * (n - k) + RESET + f" {score:.0f}/100"


def table(rows, columns=None, headers=None, aligns=None, max_rows=40, formats=None):
    """rows: lista de dicts o DataFrame."""
    try:
        import pandas as pd
        if isinstance(rows, pd.DataFrame):
            columns = columns or list(rows.columns)
            rows = rows.to_dict("records")
    except ImportError:
        pass
    rows = list(rows)[:max_rows]
    if not rows:
        print(GRAY + "  (sin datos)" + RESET)
        return
    columns = columns or list(rows[0].keys())
    headers = headers or columns
    formats = formats or {}

    def cell(r, c):
        v = r.get(c)
        if c in formats:
            return formats[c](v)
        if isinstance(v, float):
            return fmt_num(v, 3 if abs(v) < 10 else 2)
        return "-" if v is None else str(v)

    cells = [[cell(r, c) for c in columns] for r in rows]
    ws = [max(_vis(h), *(_vis(x[i]) for x in cells)) for i, h in enumerate(headers)]
    aligns = aligns or [">" if isinstance(rows[0].get(c), (int, float)) else "<" for c in columns]
    sep = GRAY + "│" + RESET
    print("  " + sep.join(" " + BOLD + pad(h, w, a) + RESET + " " for h, w, a in zip(headers, ws, aligns)))
    print("  " + GRAY + "┼".join("─" * (w + 2) for w in ws) + RESET)
    for x in cells:
        print("  " + sep.join(" " + pad(v, w, a) + " " for v, w, a in zip(x, ws, aligns)))


def bullet(text, kind="info"):
    icon = {"info": CYAN + "•", "ok": GREEN + "✔", "warn": YELLOW + "▲", "bad": RED + "✖"}[kind]
    print(f"  {icon}{RESET} {text}")


def menu(title, options, footer=None):
    """
    options: lista de (clave, etiqueta) o ("", "SECCION") para separadores.
    Devuelve la clave elegida.
    """
    section(title)
    keys = []
    for k, label in options:
        if k == "":
            print("  " + GRAY + label.upper() + RESET)
            continue
        keys.append(str(k))
        print(f"    {BCYAN}{k:>2}{RESET}  {label}")
    if footer:
        print("  " + GRAY + footer + RESET)
    while True:
        op = input(f"\n  {BOLD}›{RESET} Opcion: ").strip()
        if op in keys:
            return op
        print(RED + "  Opcion invalida" + RESET)


def ask(prompt, default=None, cast=str):
    suffix = f" {GRAY}[{default}]{RESET}" if default not in (None, "") else ""
    while True:
        raw = input(f"  {prompt}{suffix}: ").strip()
        if raw == "":
            return default
        try:
            return cast(raw.replace(",", ".")) if cast in (int, float) else cast(raw)
        except ValueError:
            print(RED + "  Valor invalido" + RESET)


def confirm(prompt, default=True):
    d = "S/n" if default else "s/N"
    raw = input(f"  {prompt} ({d}): ").strip().lower()
    if not raw:
        return default
    return raw.startswith("s") or raw.startswith("y")


def progress(i, n, label=""):
    w = 28
    k = int(w * i / max(n, 1))
    end = "\n" if i >= n else "\r"
    sys.stdout.write(f"  {CYAN}{'█' * k}{GRAY}{'░' * (w - k)}{RESET} {i}/{n} {label[:40]:<40}{end}")
    sys.stdout.flush()


def open_file(path):
    """Abre un archivo con la aplicacion predeterminada (navegador para HTML)."""
    import webbrowser
    from pathlib import Path
    try:
        webbrowser.open(Path(path).resolve().as_uri())
    except Exception:  # noqa: BLE001
        pass
