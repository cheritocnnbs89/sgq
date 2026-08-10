"""
Escáner estático de postura de seguridad — SGQ Quimpac.
Detecta anti-patrones de seguridad en el código fuente del proyecto.

Uso:  python tools/security_posture.py
      python tools/security_posture.py --only-new   # solo muestra hallazgos nuevos vs reporte anterior

Los reportes se guardan en tools/posture_reports/ y se comparan con la corrida anterior
para detectar regresiones o mejoras.
"""

from __future__ import annotations

import ast
import json
import os
import re
import sys
import argparse
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Iterator

# ---------------------------------------------------------------------------
# Modelo de datos
# ---------------------------------------------------------------------------

STRIDE = {
    "S": "Spoofing",
    "T": "Tampering",
    "R": "Repudiation",
    "I": "Information Disclosure",
    "D": "Denial of Service",
    "E": "Elevation of Privilege",
}

SEV_ORDER = {"ALTO": 0, "MEDIO": 1, "BAJO": 2}


@dataclass
class Finding:
    check:    str           # slug del check
    stride:   str           # letra(s) STRIDE
    severity: str           # ALTO / MEDIO / BAJO
    file:     str           # ruta relativa
    line:     int
    snippet:  str           # línea(s) de código relevante
    detail:   str           # explicación concisa


# ---------------------------------------------------------------------------
# Utilidades de escaneo
# ---------------------------------------------------------------------------

SKIP_DIRS = {"__pycache__", ".git", ".venv", "venv", "env",
             "node_modules", "posture_reports", "audit_reports", "respaldo", "migrations"}


def py_files(root: Path) -> Iterator[Path]:
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fname in filenames:
            if fname.endswith(".py"):
                yield Path(dirpath) / fname


def html_files(root: Path) -> Iterator[Path]:
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fname in filenames:
            if fname.endswith((".html", ".jinja2", ".j2")):
                yield Path(dirpath) / fname


def rel(path: Path, root: Path) -> str:
    return str(path.relative_to(root)).replace("\\", "/")


def read_lines(path: Path) -> list[str]:
    try:
        return path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return []


# ---------------------------------------------------------------------------
# Checks individuales
# ---------------------------------------------------------------------------

def check_routes_without_auth(root: Path) -> list[Finding]:
    """Rutas HTTP sin decorador de autenticación (@require_login / @login_required)."""
    findings = []
    AUTH_DECS = re.compile(r"@.*(require_login|login_required|admin_required|rol_required)")
    ROUTE_DEC  = re.compile(r"@\w+\.route\s*\(")
    DEF_LINE   = re.compile(r"^\s*def\s+\w+")

    for path in py_files(root):
        lines = read_lines(path)
        i = 0
        while i < len(lines):
            if ROUTE_DEC.search(lines[i]):
                # Buscar hacia adelante hasta llegar al def, recogiendo decoradores
                j = i
                has_auth = False
                while j < len(lines) and j < i + 10:
                    if AUTH_DECS.search(lines[j]):
                        has_auth = True
                    if DEF_LINE.match(lines[j]) and j > i:
                        break
                    j += 1
                if not has_auth and j < len(lines):
                    findings.append(Finding(
                        check="route_without_auth",
                        stride="E",
                        severity="ALTO",
                        file=rel(path, root),
                        line=i + 1,
                        snippet=lines[i].strip(),
                        detail="Ruta HTTP sin decorador de autenticación — cualquier usuario puede acceder.",
                    ))
            i += 1
    return findings


def check_sql_injection(root: Path) -> list[Finding]:
    """Queries SQL construidas con f-strings o concatenación de strings."""
    findings = []
    SQL_KW = re.compile(r"\b(SELECT|INSERT|UPDATE|DELETE|EXEC|EXECUTE|FROM|WHERE)\b", re.IGNORECASE)
    FSTR   = re.compile(r'f["\'].*\{')
    CONCAT = re.compile(r'["\'].*["\'\s]\s*\+\s*\w')  # "..." + var

    for path in py_files(root):
        lines = read_lines(path)
        for i, line in enumerate(lines):
            stripped = line.strip()
            if not SQL_KW.search(stripped):
                continue
            if FSTR.search(stripped) or CONCAT.search(stripped):
                findings.append(Finding(
                    check="sql_injection",
                    stride="T",
                    severity="ALTO",
                    file=rel(path, root),
                    line=i + 1,
                    snippet=stripped[:120],
                    detail="Query SQL con interpolación dinámica — usar parámetros posicionales (?, %s).",
                ))
    return findings


def check_hardcoded_secrets(root: Path) -> list[Finding]:
    """Credenciales o secretos hardcodeados en el código fuente."""
    findings = []
    PATTERNS = [
        re.compile(r'(?i)(password|passwd|secret|api_key|apikey|token|bearer)\s*=\s*["\'][^"\']{4,}["\']'),
        re.compile(r'(?i)(AWS_SECRET|AWS_ACCESS|SAS_TOKEN|CONNECTION_STRING)\s*=\s*["\'][^"\']{8,}["\']'),
    ]
    SAFE_VALS = {"", "changeme", "your-secret", "placeholder", "***", "None", "os.environ"}

    for path in py_files(root):
        lines = read_lines(path)
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            for pat in PATTERNS:
                m = pat.search(stripped)
                if m:
                    val = m.group(0).split("=", 1)[-1].strip().strip('"\'')
                    if any(s in val for s in SAFE_VALS):
                        continue
                    if "os.environ" in stripped or "getenv" in stripped:
                        continue
                    findings.append(Finding(
                        check="hardcoded_secret",
                        stride="I",
                        severity="ALTO",
                        file=rel(path, root),
                        line=i + 1,
                        snippet=stripped[:80] + "…" if len(stripped) > 80 else stripped,
                        detail="Credencial o secreto hardcodeado — mover a variables de entorno (.env).",
                    ))
    return findings


def check_dangerous_functions(root: Path) -> list[Finding]:
    """Uso de eval(), exec(), os.system(), subprocess con shell=True."""
    findings = []
    DANGEROUS = [
        (re.compile(r'\beval\s*\('), "eval() ejecuta código arbitrario"),
        (re.compile(r'\bexec\s*\('), "exec() ejecuta código arbitrario"),
        (re.compile(r'\bos\.system\s*\('), "os.system() permite inyección de comandos"),
        (re.compile(r'subprocess\.(call|run|Popen).*shell\s*=\s*True'), "subprocess con shell=True permite inyección"),
        (re.compile(r'\bpickle\.(loads?|Unpickler)'), "pickle.loads con datos externos permite RCE"),
    ]

    for path in py_files(root):
        lines = read_lines(path)
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            for pat, detail in DANGEROUS:
                if pat.search(stripped):
                    findings.append(Finding(
                        check="dangerous_function",
                        stride="T",
                        severity="ALTO",
                        file=rel(path, root),
                        line=i + 1,
                        snippet=stripped[:120],
                        detail=detail,
                    ))
    return findings


def check_xml_without_defusedxml(root: Path) -> list[Finding]:
    """Parseo de XML sin usar defusedxml (riesgo XXE)."""
    findings = []
    UNSAFE = re.compile(r'\b(xml\.etree|ElementTree|ET\.parse|ET\.fromstring|lxml\.etree)\b')
    SAFE   = re.compile(r'\bdefusedxml\b')

    for path in py_files(root):
        source = "\n".join(read_lines(path))
        if SAFE.search(source):
            continue
        lines = source.splitlines()
        for i, line in enumerate(lines):
            if UNSAFE.search(line) and not line.strip().startswith("#"):
                findings.append(Finding(
                    check="xxe_risk",
                    stride="T",
                    severity="MEDIO",
                    file=rel(path, root),
                    line=i + 1,
                    snippet=line.strip()[:120],
                    detail="Parseo XML sin defusedxml — vulnerable a XXE si el XML viene de usuarios.",
                ))
    return findings


def check_open_redirect(root: Path) -> list[Finding]:
    """redirect() con valor proveniente de request.args / request.form sin validar."""
    findings = []
    PAT = re.compile(r'redirect\s*\(\s*request\.(args|form|values|json)\s*\.get\s*\(')

    for path in py_files(root):
        lines = read_lines(path)
        for i, line in enumerate(lines):
            if PAT.search(line) and not line.strip().startswith("#"):
                findings.append(Finding(
                    check="open_redirect",
                    stride="S",
                    severity="MEDIO",
                    file=rel(path, root),
                    line=i + 1,
                    snippet=line.strip()[:120],
                    detail="Redirección abierta — validar que la URL destino sea interna antes de redirigir.",
                ))
    return findings


def check_token_expiration(root: Path) -> list[Finding]:
    """Rutas /g/<token> o similares sin verificación de expiración."""
    findings = []
    GATEWAY = re.compile(r'["\']/(g|gateway|link|approve|verify)/[<\{]')
    EXPIRY  = re.compile(r'(expir|caducar|exp_date|valid_until|created_at)', re.IGNORECASE)

    for path in py_files(root):
        lines = read_lines(path)
        for i, line in enumerate(lines):
            if GATEWAY.search(line):
                # Revisar las siguientes 40 líneas en busca de check de expiración
                window = "\n".join(lines[i:min(i + 40, len(lines))])
                if not EXPIRY.search(window):
                    findings.append(Finding(
                        check="token_no_expiry",
                        stride="S",
                        severity="ALTO",
                        file=rel(path, root),
                        line=i + 1,
                        snippet=line.strip()[:120],
                        detail="Endpoint de token sin verificación de expiración — agregar validez máxima (ej. 72h).",
                    ))
    return findings


def check_file_upload_mime(root: Path) -> list[Finding]:
    """Subidas de archivo sin validación de MIME type real (solo extensión)."""
    findings = []
    UPLOAD = re.compile(r'(\.save\s*\(|request\.files)', )
    MIME   = re.compile(r'(magic\.|mimetypes\.|imghdr\.|filetype\.)')
    EXT    = re.compile(r'(splitext|\.rsplit.*\.|\.(endswith|split)\s*\(["\']\.)')

    for path in py_files(root):
        lines = read_lines(path)
        source = "\n".join(lines)
        for i, line in enumerate(lines):
            if UPLOAD.search(line):
                # Buscar en el bloque cercano (±30 líneas)
                start = max(0, i - 10)
                end   = min(len(lines), i + 30)
                block = "\n".join(lines[start:end])
                has_mime = MIME.search(block)
                has_ext  = EXT.search(block)
                if has_ext and not has_mime:
                    findings.append(Finding(
                        check="upload_mime_not_validated",
                        stride="T",
                        severity="MEDIO",
                        file=rel(path, root),
                        line=i + 1,
                        snippet=line.strip()[:120],
                        detail="Subida de archivo valida solo extensión, no contenido real — usar python-magic.",
                    ))
                    break  # un hallazgo por función es suficiente
    return findings


def check_debug_mode(root: Path) -> list[Finding]:
    """Flask corriendo con debug=True o DEBUG=True en producción."""
    findings = []
    PAT = re.compile(r'(?i)(app\.run.*debug\s*=\s*True|DEBUG\s*=\s*True)')

    for path in py_files(root):
        lines = read_lines(path)
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if PAT.search(stripped):
                findings.append(Finding(
                    check="debug_mode_on",
                    stride="I",
                    severity="MEDIO",
                    file=rel(path, root),
                    line=i + 1,
                    snippet=stripped[:120],
                    detail="Modo debug activo — expone traceback completo y habilita el debugger interactivo.",
                ))
    return findings


def check_missing_csrf_ajax(root: Path) -> list[Finding]:
    """Endpoints que modifican estado y reciben JSON sin verificación CSRF visible."""
    findings = []
    # Busca rutas POST/DELETE que retornan jsonify sin mención de csrf
    METHODS = re.compile(r'methods\s*=\s*\[.*["\']POST["\']')
    JSON_RET = re.compile(r'return\s+jsonify\s*\(')
    CSRF_CHK = re.compile(r'(csrf|CSRFProtect|validate_csrf|X-CSRFToken)', re.IGNORECASE)

    for path in py_files(root):
        lines = read_lines(path)
        source = "\n".join(lines)
        # Si el módulo tiene CSRFProtect global, está cubierto
        if re.search(r'CSRFProtect\s*\(', source):
            continue
        for i, line in enumerate(lines):
            if METHODS.search(line) and JSON_RET.search(source[source.find(line):source.find(line) + 600]):
                block_start = max(0, i - 2)
                block_end   = min(len(lines), i + 25)
                block = "\n".join(lines[block_start:block_end])
                if not CSRF_CHK.search(block):
                    findings.append(Finding(
                        check="missing_csrf_ajax",
                        stride="T",
                        severity="BAJO",
                        file=rel(path, root),
                        line=i + 1,
                        snippet=line.strip()[:120],
                        detail="Endpoint POST/JSON sin verificación CSRF explícita — confirmar cobertura de CSRFProtect global.",
                    ))
    return findings


def check_path_traversal(root: Path) -> list[Finding]:
    """Operaciones de archivo con input del usuario sin usar secure_filename."""
    findings = []
    FILE_OPS = re.compile(r'\b(open\s*\(|os\.path\.join\s*\(|Path\s*\()')
    USER_IN  = re.compile(r'request\.(args|form|values|json|files)')
    SECURE   = re.compile(r'secure_filename')

    for path in py_files(root):
        lines = read_lines(path)
        for i, line in enumerate(lines):
            if FILE_OPS.search(line) and USER_IN.search(line):
                start = max(0, i - 5)
                end   = min(len(lines), i + 5)
                block = "\n".join(lines[start:end])
                if not SECURE.search(block):
                    findings.append(Finding(
                        check="path_traversal",
                        stride="T",
                        severity="ALTO",
                        file=rel(path, root),
                        line=i + 1,
                        snippet=line.strip()[:120],
                        detail="Operación de archivo con input del usuario sin secure_filename() — riesgo de path traversal.",
                    ))
    return findings


def check_xss_templates(root: Path) -> list[Finding]:
    """Templates que usan |safe en variables de usuario."""
    findings = []
    SAFE_FILTER = re.compile(r'\{\{.*\|\s*safe\s*\}\}')

    for path in html_files(root):
        lines = read_lines(path)
        for i, line in enumerate(lines):
            if SAFE_FILTER.search(line):
                findings.append(Finding(
                    check="xss_unsafe_filter",
                    stride="T",
                    severity="MEDIO",
                    file=rel(path, root),
                    line=i + 1,
                    snippet=line.strip()[:120],
                    detail="Filtro |safe en template Jinja2 — verificar que el valor provenga solo de admins o esté sanitizado.",
                ))
    return findings


# ---------------------------------------------------------------------------
# Registro de checks
# ---------------------------------------------------------------------------

ALL_CHECKS = [
    ("Rutas sin autenticación",      check_routes_without_auth),
    ("Inyección SQL",                check_sql_injection),
    ("Secretos hardcodeados",        check_hardcoded_secrets),
    ("Funciones peligrosas",         check_dangerous_functions),
    ("XXE — XML sin defusedxml",     check_xml_without_defusedxml),
    ("Redirección abierta",          check_open_redirect),
    ("Tokens sin expiración",        check_token_expiration),
    ("Subida sin validar MIME",      check_file_upload_mime),
    ("Modo debug activo",            check_debug_mode),
    ("CSRF en endpoints AJAX",       check_missing_csrf_ajax),
    ("Path traversal",               check_path_traversal),
    ("XSS — filtro |safe",           check_xss_templates),
]


# ---------------------------------------------------------------------------
# Reporte y comparación
# ---------------------------------------------------------------------------

SEV_ICON = {"ALTO": "🔴", "MEDIO": "🟡", "BAJO": "🔵"}
COL = {
    "ALTO":  "\033[91m",
    "MEDIO": "\033[93m",
    "BAJO":  "\033[94m",
    "RESET": "\033[0m",
    "BOLD":  "\033[1m",
    "DIM":   "\033[2m",
    "GREEN": "\033[92m",
    "RED":   "\033[91m",
}

_USE_COLOR = sys.stdout.isatty()


def c(text: str, *codes: str) -> str:
    if not _USE_COLOR:
        return text
    return "".join(COL[k] for k in codes) + text + COL["RESET"]


def finding_key(f: Finding) -> str:
    """Clave estable para comparar hallazgos entre corridas (ignora número de línea exacto)."""
    return f"{f.check}::{f.file}::{f.snippet[:60]}"


def print_report(findings: list[Finding], new_keys: set[str], fixed_count: int, only_new: bool):
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    counts  = {s: sum(1 for f in findings if f.severity == s) for s in SEV_ORDER}

    print()
    print(c("=" * 70, "BOLD"))
    print(c("  SGQ — Escáner de Postura de Seguridad", "BOLD"))
    print(f"  {now_str}")
    print(c("=" * 70, "BOLD"))

    if not findings:
        print()
        print(c("  ✅  Sin hallazgos. Código limpio.", "GREEN", "BOLD"))
        print()
        return

    total = len(findings)
    parts = []
    for sev, cnt in counts.items():
        if cnt:
            parts.append(c(f"{cnt} {sev}", sev))
    print(f"\n  {total} hallazgos: " + "  ·  ".join(parts))
    if fixed_count:
        print(c(f"  ✅  {fixed_count} resueltos desde el reporte anterior", "GREEN"))
    if new_keys:
        print(c(f"  🆕  {len(new_keys)} nuevos desde el reporte anterior", "RED"))
    print()

    # Agrupar por severidad
    for sev in ("ALTO", "MEDIO", "BAJO"):
        group = [f for f in findings if f.severity == sev]
        if not group:
            continue
        if only_new:
            group = [f for f in group if finding_key(f) in new_keys]
        if not group:
            continue

        print(c(f"  {'─' * 66}", "DIM"))
        print(c(f"  {SEV_ICON[sev]}  {sev}", sev, "BOLD") + f"  ({len(group)} hallazgos)")
        print()

        for f in group:
            is_new = finding_key(f) in new_keys
            tag    = c(" NEW", "RED", "BOLD") if is_new else ""
            stride_label = " · ".join(f"{s} — {STRIDE[s]}" for s in f.stride)
            print(f"  {c(f.check, 'BOLD')}{tag}")
            print(f"  {c(f.file, 'DIM')}:{f.line}")
            print(f"  STRIDE: {stride_label}")
            print(f"  {c(f.detail, 'DIM')}")
            print(f"  {c('▸ ' + f.snippet, 'DIM')}")
            print()

    print(c("=" * 70, "BOLD"))
    print(f"  Total: {total} hallazgos en {len(set(f.file for f in findings))} archivos")
    print(c("=" * 70, "BOLD"))
    print()


def save_json(findings: list[Finding], out_dir: Path) -> Path:
    now  = datetime.now()
    data = {
        "generated_at": now.strftime("%Y-%m-%d %H:%M"),
        "total": len(findings),
        "by_severity": {
            s: sum(1 for f in findings if f.severity == s)
            for s in ("ALTO", "MEDIO", "BAJO")
        },
        "findings": [asdict(f) for f in findings],
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"posture_{now.strftime('%Y%m%d_%H%M')}.json"
    out_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return out_path


def load_last_report(out_dir: Path) -> dict | None:
    if not out_dir.exists():
        return None
    reports = sorted(out_dir.glob("posture_*.json"))
    if not reports:
        return None
    return json.loads(reports[-1].read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="SGQ Security Posture Scanner")
    parser.add_argument("--only-new", action="store_true",
                        help="Mostrar solo hallazgos nuevos respecto al reporte anterior")
    parser.add_argument("--no-save", action="store_true",
                        help="No guardar reporte JSON")
    parser.add_argument("--ci", action="store_true",
                        help="Salir con código 1 si hay hallazgos ALTO (para pipelines CI/CD)")
    args = parser.parse_args()

    # Raíz del proyecto = dos niveles arriba de tools/
    tools_dir   = Path(__file__).parent
    project_root = tools_dir.parent
    out_dir      = tools_dir / "posture_reports"

    print(f"\n  Escaneando: {project_root}")

    # Cargar reporte anterior
    last_report = load_last_report(out_dir)
    last_keys: set[str] = set()
    last_total = 0
    if last_report:
        last_keys  = {f"{f['check']}::{f['file']}::{f['snippet'][:60]}"
                      for f in last_report["findings"]}
        last_total = last_report["total"]

    # Ejecutar todos los checks
    all_findings: list[Finding] = []
    for name, check_fn in ALL_CHECKS:
        results = check_fn(project_root)
        all_findings.extend(results)
        status = f"{len(results):>3} hallazgo{'s' if len(results) != 1 else ''}"
        print(f"  {c('✓', 'GREEN')} {name:<40} {status}")

    # Ordenar por severidad y archivo
    all_findings.sort(key=lambda f: (SEV_ORDER[f.severity], f.file, f.line))

    # Calcular nuevos y resueltos
    current_keys = {finding_key(f) for f in all_findings}
    new_keys     = current_keys - last_keys
    fixed_count  = len(last_keys - current_keys)

    # Imprimir
    print_report(all_findings, new_keys, fixed_count, args.only_new)

    # Guardar
    if not args.no_save:
        out_path = save_json(all_findings, out_dir)
        print(f"  Reporte JSON guardado en: {out_path}")
        if last_report:
            print(f"  Comparado con: {last_report['generated_at']} ({last_total} hallazgos previos)")
        print()

    # Exit code no-cero solo en modo CI
    if args.ci:
        high_count = sum(1 for f in all_findings if f.severity == "ALTO")
        sys.exit(1 if high_count > 0 else 0)


if __name__ == "__main__":
    main()
