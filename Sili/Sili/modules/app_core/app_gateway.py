# modules/app_core/app_gateway.py
# ==========================================================
# Gateway de URLs GET.
# Enmascara rutas de lectura con /g/<token> y reinyecta
# internamente el request hacia la ruta real.
# ==========================================================

from urllib.parse import urlsplit, parse_qsl, urlencode

from flask import current_app, request, abort, Response, redirect, url_for
from itsdangerous import URLSafeSerializer, BadSignature, BadData


def template_exists(path_rel: str) -> bool:
    # ------------------------------------------------------
    # Verifica si una plantilla existe antes de usarla.
    # ------------------------------------------------------
    try:
        current_app.jinja_env.get_or_select_template(path_rel)
        return True
    except Exception:
        return False


def build_method_map(app):
    # ------------------------------------------------------
    # Construye un mapa endpoint -> métodos HTTP permitidos.
    # ------------------------------------------------------
    methods = {}
    for rule in app.url_map.iter_rules():
        methods[rule.endpoint] = set(rule.methods or [])
    return methods


def register_gateway(app):
    # ------------------------------------------------------
    # Registra tanto el despachador del gateway como la
    # redirección automática de rutas GET puras.
    # ------------------------------------------------------
    _register_gateway_dispatch(app)
    _register_gateway_redirect(app)


def _register_gateway_dispatch(app):
    serializer = URLSafeSerializer(app.secret_key, salt="gw.v1")
    method_map = build_method_map(app)
    from flask import url_for as _real_url_for

    def _short_url_for(endpoint: str, **values):
        # --------------------------------------------------
        # Reemplaza url_for en templates para que endpoints
        # GET puros devuelvan una URL /g/<token>.
        # --------------------------------------------------
        if endpoint == "static":
            return _real_url_for(endpoint, **values)

        m = method_map.get(endpoint, set()) or set()
        allowed = set(m) - {"HEAD", "OPTIONS"}

        if allowed != {"GET"}:
            return _real_url_for(endpoint, **values)

        original = _real_url_for(endpoint, **values)

        if original.startswith("/g/") or original.startswith("http://") or original.startswith("https://"):
            return original

        token = serializer.dumps({"p": original})
        return _real_url_for("gateway_disp", token=token)

    app.jinja_env.globals["url_for"] = _short_url_for

    @app.route("/g/<token>", methods=["GET"], endpoint="gateway_disp")
    def gateway_disp(token: str):
        # --------------------------------------------------
        # Desencripta la ruta real y la despacha internamente
        # conservando query string y cabeceras relevantes.
        # --------------------------------------------------
        try:
            data = serializer.loads(token)
            raw_path = data.get("p", "/")

            current_app.logger.warning("GATEWAY data=%s", data)
            current_app.logger.warning("GATEWAY raw_path=%s", raw_path)

            if not isinstance(raw_path, str) or not raw_path.startswith("/"):
                current_app.logger.warning("GATEWAY raw_path inválido=%s", raw_path)
                abort(400)

        except (BadSignature, BadData):
            current_app.logger.exception("GATEWAY token inválido o expirado")
            abort(404)
        except Exception:
            current_app.logger.exception("GATEWAY error desencriptando token")
            abort(400)

        try:
            parts = urlsplit(raw_path)

            token_qs_pairs = parse_qsl(parts.query, keep_blank_values=True)
            req_qs_pairs = parse_qsl(
                (request.query_string or b"").decode("utf-8", "ignore"),
                keep_blank_values=True
            )

            merged = dict(token_qs_pairs)
            for k, v in req_qs_pairs:
                merged.setdefault(k, v)

            forward_qs_str = urlencode(merged, doseq=True)

            current_app.logger.warning("GATEWAY request.path=%s", request.path)
            current_app.logger.warning("GATEWAY request.method=%s", request.method)
            current_app.logger.warning("GATEWAY parts.path=%s", parts.path)
            current_app.logger.warning("GATEWAY parts.query=%s", parts.query)
            current_app.logger.warning("GATEWAY forward_qs=%s", forward_qs_str)

            try:
                adapter = current_app.url_map.bind("")
                match_result = adapter.match(parts.path, method=request.method)
                current_app.logger.warning("GATEWAY match=%s", match_result)
            except Exception as e:
                current_app.logger.exception(
                    "GATEWAY no pudo matchear parts.path=%s method=%s error=%s",
                    parts.path,
                    request.method,
                    e
                )

            if request.headers.get("X-From-Gateway") == "1":
                current_app.logger.warning("GATEWAY loop detectado para raw_path=%s", raw_path)
                return current_app.response_class("Loop detectado", status=400)

            fwd_headers = {
                k: v
                for k, v in request.headers.items()
                if k.lower() != "host"
            }
            fwd_headers["X-From-Gateway"] = "1"

            has_body = request.method in ("POST", "PUT", "PATCH")
            body = request.get_data() if has_body else None

            with current_app.test_request_context(
                path=parts.path,
                method=request.method,
                query_string=forward_qs_str,
                data=body,
                headers=fwd_headers,
                content_type=request.content_type,
                environ_overrides={
                    "REMOTE_ADDR": request.remote_addr or "127.0.0.1"
                },
            ):
                current_app.logger.warning(
                    "GATEWAY despachando interno path=%s method=%s qs=%s",
                    parts.path,
                    request.method,
                    forward_qs_str
                )

                resp = current_app.full_dispatch_request()

                current_app.logger.warning(
                    "GATEWAY response type=%s status=%s",
                    type(resp),
                    getattr(resp, "status", None)
                )

                return resp if isinstance(resp, Response) else resp

        except Exception:
            current_app.logger.exception("Gateway fallo para path=%s", raw_path)
            abort(500)

def _register_gateway_redirect(app):
    serializer = URLSafeSerializer(app.secret_key, salt="gw.v1")

    @app.before_request
    def _gw_auto_redirect():
        # --------------------------------------------------
        # Redirige automáticamente rutas GET puras a su
        # versión enmascarada del gateway.
        # --------------------------------------------------
        if request.method != "GET":
            return
        if request.path.startswith("/g/"):
            return
        if request.endpoint in ("static",) or request.path == "/favicon.ico":
            return
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return
        if request.headers.get("X-From-Gateway") == "1":
            return

        try:
            allowed = None
            for rule in current_app.url_map.iter_rules():
                if rule.endpoint == (request.endpoint or ""):
                    allowed = set(rule.methods or set()) - {"HEAD", "OPTIONS"}
                    break

            if allowed != {"GET"}:
                return
        except Exception:
            return

        full = request.path
        if request.query_string:
            full = f"{request.path}?{request.query_string.decode('utf-8', 'ignore')}"

        if full.startswith("/g/"):
            return

        token = serializer.dumps({"p": full})
        return redirect(url_for("gateway_disp", token=token), code=302)