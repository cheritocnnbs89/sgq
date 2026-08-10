"""
Auditoría de vulnerabilidades de dependencias Python.
Uso: python tools/security_audit.py
Requiere: pip install pip-audit

Los módulos afectados se detectan automáticamente escaneando el código fuente
del proyecto — no hay nada hardcodeado, funciona con módulos nuevos también.
"""

import subprocess
import sys
import json
import os
import re
from datetime import datetime
from collections import defaultdict

# Mapa de nombres de import → nombre del paquete pip
# (algunos paquetes se importan con un nombre distinto al del paquete)
IMPORT_TO_PACKAGE = {
    "flask":        "flask",
    "flask_wtf":    "flask",
    "werkzeug":     "werkzeug",
    "PIL":          "pillow",
    "pillow":       "pillow",
    "pypdf":        "pypdf",
    "PyPDF2":       "pypdf",
    "cryptography": "cryptography",
    "requests":     "requests",
    "urllib3":      "urllib3",
    "click":        "click",
    "idna":         "idna",
    "weasyprint":   "weasyprint",
    "xhtml2pdf":    "weasyprint",
    "boto3":        "boto3",
    "botocore":     "boto3",
    "openpyxl":     "openpyxl",
    "reportlab":    "reportlab",
    "openai":       "openai",
    "pyodbc":       "pyodbc",
    "dotenv":       "python-dotenv",
    "yaml":         "pyyaml",
    "pandas":       "pandas",
    "numpy":        "numpy",
    "matplotlib":   "matplotlib",
    "scipy":        "scipy",
    "cv2":          "opencv-python-headless",
    "pyhanko":      "pyHanko",
    "schedule":     "schedule",
}

# Patrón para capturar imports: "import X", "from X import ..."
IMPORT_RE = re.compile(
    r'^\s*(?:import|from)\s+([\w]+)',
    re.MULTILINE
)


def scan_source_modules(root_dir: str) -> dict[str, list[str]]:
    """
    Escanea todos los .py del proyecto y devuelve un dict:
      { "nombre_paquete_pip": ["ruta/modulo1.py", "ruta/modulo2.py", ...] }
    Las rutas son relativas a root_dir.
    """
    usage: dict[str, set[str]] = defaultdict(set)

    for dirpath, dirnames, filenames in os.walk(root_dir):
        # Ignorar carpetas irrelevantes
        dirnames[:] = [
            d for d in dirnames
            if d not in {"__pycache__", ".git", ".venv", "venv", "env",
                         "node_modules", "audit_reports", "respaldo"}
        ]
        for fname in filenames:
            if not fname.endswith(".py"):
                continue
            full_path = os.path.join(dirpath, fname)
            rel_path  = os.path.relpath(full_path, root_dir).replace("\\", "/")
            try:
                source = open(full_path, encoding="utf-8", errors="ignore").read()
            except OSError:
                continue

            for match in IMPORT_RE.finditer(source):
                top_level = match.group(1)
                pkg = IMPORT_TO_PACKAGE.get(top_level)
                if pkg:
                    usage[pkg].add(rel_path)

    return {pkg: sorted(files) for pkg, files in usage.items()}


def _ensure_pip_audit():
    """Instala pip-audit si no está disponible."""
    try:
        subprocess.run(
            [sys.executable, "-m", "pip_audit", "--version"],
            capture_output=True, check=True
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Instalando pip-audit...")
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "pip-audit"],
            check=True
        )


def run_audit() -> list[dict]:
    """Ejecuta pip-audit y retorna los resultados como lista de dicts."""
    result = subprocess.run(
        [sys.executable, "-m", "pip_audit", "--format", "json"],
        capture_output=True, text=True
    )
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        print("Error al parsear la salida de pip-audit:")
        print(result.stdout)
        print(result.stderr)
        sys.exit(1)

    findings = []
    for dep in data.get("dependencies", []):
        vulns = dep.get("vulns", [])
        if not vulns:
            continue
        findings.append({
            "name":    dep["name"],
            "version": dep["version"],
            "vulns":   vulns,
        })
    return findings


def print_report(findings: list[dict], module_map: dict[str, list[str]], save_json: bool = True):
    now = datetime.now()
    timestamp = now.strftime("%Y-%m-%d %H:%M")
    filename  = f"audit_{now.strftime('%Y%m%d_%H%M')}.json"

    total_vulns = sum(len(f["vulns"]) for f in findings)

    print()
    print("=" * 70)
    print("  SGQ — Auditoría de Vulnerabilidades de Dependencias")
    print(f"  {timestamp}")
    print("=" * 70)

    if not findings:
        print()
        print("  ✅  Sin vulnerabilidades conocidas. Todas las librerías están al día.")
        print()
        return

    print(f"\n  {total_vulns} vulnerabilidades en {len(findings)} paquetes\n")

    for f in findings:
        name    = f["name"]
        version = f["version"]
        vulns   = f["vulns"]

        # Módulos detectados automáticamente en el código fuente
        modules = module_map.get(name.lower(), [])
        if not modules:
            modules = ["(no se encontraron imports directos — puede ser dependencia transitiva)"]

        # Fix versions — la más alta disponible
        fix_versions = sorted(set(
            v for vuln in vulns
            for v in (vuln.get("fix_versions") or [])
        ))
        fix_str = fix_versions[-1] if fix_versions else "Sin fix disponible"

        print(f"  {'─' * 66}")
        print(f"  📦  {name}  {version}  →  {fix_str}")

        # Todos los CVEs, sin cortar
        all_ids = ", ".join(v["id"] for v in vulns)
        print(f"      CVEs ({len(vulns)}): {all_ids}")

        print(f"\n      Módulos del proyecto que lo usan ({len(modules)}):")
        for m in modules:
            print(f"        • {m}")

        if fix_versions:
            print(f"\n      Comando: pip install --upgrade {name}=={fix_str}")
        else:
            print(f"\n      ⚠  Sin fix publicado — monitorear en https://osv.dev")
        print()

    print("=" * 70)
    print(f"  Total: {total_vulns} vulnerabilidades en {len(findings)} paquetes")
    print("=" * 70)
    print()

    if save_json:
        report = {
            "generated_at":         timestamp,
            "total_vulnerabilities": total_vulns,
            "total_packages":        len(findings),
            "findings": [
                {
                    "package": f["name"],
                    "version": f["version"],
                    "vulns":   [v["id"] for v in f["vulns"]],
                    "fix":     sorted(set(
                        v2 for v in f["vulns"] for v2 in (v.get("fix_versions") or [])
                    )),
                    "modules": module_map.get(f["name"].lower(), []),
                }
                for f in findings
            ],
        }
        out_dir  = os.path.join(os.path.dirname(__file__), "audit_reports")
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, filename)
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2, ensure_ascii=False)
        print(f"  Reporte JSON guardado en: {out_path}")
        print()


def compare_with_last():
    """Muestra comparación con el reporte anterior si existe."""
    out_dir = os.path.join(os.path.dirname(__file__), "audit_reports")
    if not os.path.isdir(out_dir):
        return

    reports = sorted(
        f for f in os.listdir(out_dir)
        if f.startswith("audit_") and f.endswith(".json")
    )
    if len(reports) < 2:
        return

    with open(os.path.join(out_dir, reports[-2]), encoding="utf-8") as fh:
        last = json.load(fh)

    last_vulns   = {v for f in last["findings"] for v in f["vulns"]}
    last_pkgs    = {f["package"] for f in last["findings"]}

    print(f"  📊  Comparación con reporte anterior ({last['generated_at']})")
    print(f"  {'─' * 66}")
    print(f"  Anterior: {last['total_vulnerabilities']} vulns en {last['total_packages']} paquetes")
    print(f"  CVEs anteriores: {', '.join(sorted(last_vulns)) or '—'}")
    print()


if __name__ == "__main__":
    # Directorio raíz del proyecto (un nivel arriba de tools/)
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    print(f"\n  Escaneando módulos del proyecto en: {project_root}")
    module_map = scan_source_modules(project_root)
    print(f"  Paquetes detectados en el código: {len(module_map)}")

    _ensure_pip_audit()
    findings = run_audit()
    compare_with_last()
    print_report(findings, module_map, save_json=True)
