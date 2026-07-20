from datetime import datetime
from pathlib import Path
import re

from flask import current_app, url_for
from werkzeug.routing import BuildError


def row_to_dict(row, cursor=None):
    if row is None:
        return None

    if isinstance(row, dict):
        return row

    if hasattr(row, "_asdict"):
        return row._asdict()

    if cursor is not None and cursor.description:
        columns = [col[0] for col in cursor.description]
        return dict(zip(columns, row))

    try:
        return dict(row)
    except Exception:
        return None


def rows_to_dicts(rows, cursor=None):
    if not rows:
        return []
    return [row_to_dict(row, cursor) for row in rows]


def fetchone_dict(cur, sql, params=()):
    cur.execute(sql, params)
    row = cur.fetchone()
    return row_to_dict(row, cur)


def fetchall_dict(cur, sql, params=()):
    cur.execute(sql, params)
    rows = cur.fetchall()
    return rows_to_dicts(rows, cur)


def safe_sql_identifier(name: str) -> str:
    if not name or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
        raise ValueError(f"Identificador SQL inválido: {name}")
    return name


def utc_now():
    return datetime.utcnow()


def slugify(label: str) -> str:
    value = (label or "").lower().strip()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    if not value:
        value = "recurso"
    return value


def rule_exists(endpoint_name: str) -> bool:
    return any(rule.endpoint == endpoint_name for rule in current_app.url_map.iter_rules())

def resolve_endpoint_href(endpoint_name: str):
    print(">>> resolve_endpoint_href************+", endpoint_name, flush=True)
    
    if not endpoint_name:
        current_app.logger.warning("MENU endpoint vacío")
        return "#"

    endpoint_name = endpoint_name.strip()

    current_app.logger.warning(
        "MENU intentando resolver endpoint=%s",
        endpoint_name
    )

    if "://" in endpoint_name or endpoint_name.startswith("/"):
        current_app.logger.warning(
            "MENU endpoint es URL directa=%s",
            endpoint_name
        )
        return endpoint_name

    try:
        url = url_for(endpoint_name)

        current_app.logger.warning(
            "MENU endpoint resuelto=%s -> %s",
            endpoint_name,
            url
        )

        return url

    except BuildError as e:
        current_app.logger.exception(
            "MENU BuildError endpoint=%s error=%s",
            endpoint_name,
            e
        )

    if "." not in endpoint_name:
        try:
            url = url_for(f"menu.{endpoint_name}")

            current_app.logger.warning(
                "MENU endpoint resuelto menu.%s -> %s",
                endpoint_name,
                url
            )

            return url

        except BuildError as e:
            current_app.logger.exception(
                "MENU BuildError menu.%s error=%s",
                endpoint_name,
                e
            )

        candidates = [
            rule.endpoint
            for rule in current_app.url_map.iter_rules()
            if rule.endpoint.endswith(f".{endpoint_name}")
        ]

        current_app.logger.warning(
            "MENU candidatos endpoint=%s -> %s",
            endpoint_name,
            candidates
        )

        if len(candidates) == 1:
            try:
                url = url_for(candidates[0])

                current_app.logger.warning(
                    "MENU endpoint candidato resuelto=%s -> %s",
                    candidates[0],
                    url
                )

                return url

            except BuildError as e:
                current_app.logger.exception(
                    "MENU BuildError candidato=%s error=%s",
                    candidates[0],
                    e
                )

    current_app.logger.error(
        "MENU no pudo resolver endpoint=%s. Endpoints=%s",
        endpoint_name,
        sorted(current_app.view_functions.keys())
    )

    return "#"
 

def resolve_endpoint_href(endpoint_name):
    from flask import url_for
    from werkzeug.routing import BuildError

    print(">>> resolve_endpoint_href RECIBIDO:", repr(endpoint_name), flush=True)

    endpoint_name = (endpoint_name or "").strip()

    if not endpoint_name:
        print(">>> resolve_endpoint_href VACIO -> #", flush=True)
        return "#"

    try:
        href = url_for(endpoint_name)
        print(">>> resolve_endpoint_href OK:", repr(endpoint_name), "->", repr(href), flush=True)
        return href
    except BuildError as e:
        print(">>> resolve_endpoint_href FAIL:", repr(endpoint_name), e, flush=True)
        return "#"

def ensure_autogen_templates(slug: str, label: str):
    base_dir = Path(current_app.root_path) / "templates" / "autogen"
    base_dir.mkdir(parents=True, exist_ok=True)

    list_tpl = base_dir / f"{slug}_list.html"
    form_tpl = base_dir / f"{slug}_form.html"

    if not list_tpl.exists():
        list_tpl.write_text(
            f"""{{% extends 'base.html' %}}
{{% block title %}}{label}{{% endblock %}}
{{% block content %}}
<div class="d-flex align-items-center justify-content-between mb-3">
  <h1 class="h5 mb-0">{label}</h1>
  <a class="btn btn-primary" href="{{{{ url_for('{slug}_new') }}}}"><i class="bi bi-plus"></i> Nuevo</a>
</div>

<table class="table table-sm table-dark align-middle">
  <thead>
    <tr>
      <th>ID</th><th>Campo 1</th><th>Campo 2</th><th>Campo 3</th><th>Email 1</th><th>Email 2</th><th></th>
    </tr>
  </thead>
  <tbody>
  {{% for r in rows %}}
    <tr>
      <td>{{{{ r.id }}}}</td>
      <td>{{{{ r.campo1 or '' }}}}</td>
      <td>{{{{ r.campo2 or '' }}}}</td>
      <td>{{{{ r.campo3 or '' }}}}</td>
      <td>{{{{ r.email1 or '' }}}}</td>
      <td>{{{{ r.email2 or '' }}}}</td>
      <td class="text-end">
        <a class="btn btn-sm btn-outline-light" href="{{{{ url_for('{slug}_edit', item_id=r.id) }}}}">Editar</a>
        <form class="d-inline" method="post" action="{{{{ url_for('{slug}_delete', item_id=r.id) }}}}" onsubmit="return confirm('¿Eliminar registro?');">
          <button class="btn btn-sm btn-outline-danger">Borrar</button>
        </form>
      </td>
    </tr>
  {{% endfor %}}
  </tbody>
</table>
{{% endblock %}}
""",
            encoding="utf-8",
        )

    if not form_tpl.exists():
        form_tpl.write_text(
            f"""{{% extends 'base.html' %}}
{{% block title %}}{label} - {{% if item %}}Editar{{% else %}}Nuevo{{% endif %}}{{% endblock %}}
{{% block content %}}
<h4 class="mb-3">{label} - {{% if item %}}Editar{{% else %}}Nuevo{{% endif %}}</h4>
<form method="post" class="row g-3">
  <div class="col-md-4">
    <label class="form-label">Campo 1</label>
    <input name="campo1" class="form-control" value="{{{{ item.campo1 if item else '' }}}}">
  </div>
  <div class="col-md-4">
    <label class="form-label">Campo 2</label>
    <input name="campo2" class="form-control" value="{{{{ item.campo2 if item else '' }}}}">
  </div>
  <div class="col-md-4">
    <label class="form-label">Campo 3</label>
    <input name="campo3" class="form-control" value="{{{{ item.campo3 if item else '' }}}}">
  </div>
  <div class="col-md-6">
    <label class="form-label">Email 1</label>
    <input name="email1" type="email" class="form-control" value="{{{{ item.email1 if item else '' }}}}">
  </div>
  <div class="col-md-6">
    <label class="form-label">Email 2</label>
    <input name="email2" type="email" class="form-control" value="{{{{ item.email2 if item else '' }}}}">
  </div>

  <div class="col-12">
    <button class="btn btn-primary">Guardar</button>
    <a href="{{{{ url_for('{slug}') }}}}" class="btn btn-outline-secondary">Cancelar</a>
  </div>
</form>
{{% endblock %}}
""",
            encoding="utf-8",
        )