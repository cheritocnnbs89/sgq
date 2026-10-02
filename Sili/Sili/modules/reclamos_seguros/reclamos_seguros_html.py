# modules/reclamos_seguros/reclamos_seguros_html.py
# -*- coding: utf-8 -*-
"""Descripcion del caso como HTML de un editor tipo correo: limpieza por lista blanca (solo
libreria estandar), conversion a texto y preparacion para el correo (imagenes como CID).

Lo que se guarda en BD es SIEMPRE el resultado de limpiar_html(); nunca el HTML crudo del
navegador. Las imagenes solo se aceptan si apuntan al endpoint propio de imagenes subidas."""
from __future__ import annotations

import html as _html
import os
import re
from html.parser import HTMLParser

from flask import current_app
from markupsafe import Markup

_ETIQUETAS = {"p", "br", "strong", "b", "em", "i", "u", "s", "ul", "ol", "li",
              "blockquote", "h1", "h2", "h3", "a", "img"}
_VACIAS = {"br", "img"}
_NORMALIZA = {"b": "strong", "i": "em"}
_DESCARTAR_CONTENIDO = {"script", "style", "iframe", "object", "embed", "noscript",
                        "template", "textarea", "title", "head", "svg", "math", "select"}
_RE_IMG = re.compile(r"^/reclamos-seguros/imagen/[0-9a-f]{32}\.(?:png|jpg|jpeg|gif|webp)$")
_ESQUEMAS_LINK = ("http://", "https://", "mailto:")
_RE_ES_HTML = re.compile(r"^\s*<(p|h[1-3]|ul|ol|blockquote|img)\b", re.IGNORECASE)
_RE_IMG_LIMPIA = re.compile(
    r'<img src="/reclamos-seguros/imagen/([0-9a-f]{32})\.(png|jpg|jpeg|gif|webp)" alt="">')


class _Limpiador(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.pila: list[tuple[str, bool]] = []
        self._saltar: str | None = None
        self._prof = 0

    def handle_starttag(self, tag, attrs):
        if self._saltar:
            if tag == self._saltar:
                self._prof += 1
            return
        if tag in _DESCARTAR_CONTENIDO:
            self._saltar, self._prof = tag, 1
            return
        if tag not in _ETIQUETAS:
            return  # etiqueta desconocida: se descarta, su texto se conserva
        tag = _NORMALIZA.get(tag, tag)
        a = dict(attrs)
        if tag == "img":
            src = (a.get("src") or "").strip()
            if _RE_IMG.match(src):
                self.out.append(f'<img src="{src}" alt="">')
            return
        if tag == "br":
            self.out.append("<br>")
            return
        if tag == "a":
            href = (a.get("href") or "").strip()
            ok = href.lower().startswith(_ESQUEMAS_LINK) and len(href) < 2000
            if ok:
                self.out.append('<a href="%s" target="_blank" rel="noopener noreferrer">'
                                % _html.escape(href, quote=True))
            self.pila.append(("a", ok))
            return
        self.out.append(f"<{tag}>")
        self.pila.append((tag, True))

    def handle_endtag(self, tag):
        if self._saltar:
            if tag == self._saltar:
                self._prof -= 1
                if self._prof <= 0:
                    self._saltar = None
            return
        tag = _NORMALIZA.get(tag, tag)
        if tag in _VACIAS or tag not in _ETIQUETAS:
            return
        for i in range(len(self.pila) - 1, -1, -1):
            if self.pila[i][0] == tag:
                while len(self.pila) > i:
                    t, emitido = self.pila.pop()
                    if emitido:
                        self.out.append(f"</{t}>")
                return

    def handle_data(self, data):
        if not self._saltar:
            self.out.append(_html.escape(data, quote=False))

    def cerrar(self):
        while self.pila:
            t, emitido = self.pila.pop()
            if emitido:
                self.out.append(f"</{t}>")


def limpiar_html(raw) -> str:
    p = _Limpiador()
    p.feed(raw or "")
    p.close()
    p.cerrar()
    return "".join(p.out).strip()


def a_texto(h) -> str:
    s = limpiar_html(h)
    s = s.replace("<li>", "\u2022 ")
    s = re.sub(r"</(?:p|li|h[1-3]|blockquote|ul|ol)>|<br>", "\n", s)
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"\n{3,}", "\n\n", _html.unescape(s)).strip()


def tiene_contenido(h) -> bool:
    return bool(a_texto(h)) or "<img " in (h or "")


def es_html(d) -> bool:
    return bool(_RE_ES_HTML.match(d or ""))


def visible(descripcion) -> Markup:
    """Para plantillas: HTML limpio si es del editor; texto plano escapado si es de un caso
    anterior al editor."""
    d = (descripcion or "").replace("\r\n", "\n")
    if es_html(d):
        return Markup(limpiar_html(d))
    return Markup(_html.escape(d).replace("\n", "<br>"))


def carpeta_imagenes() -> str:
    d = os.path.join(current_app.root_path, "uploads_privados", "reclamos_seguros", "_imagenes")
    os.makedirs(d, exist_ok=True)
    return d


def para_correo(descripcion):
    """(html, imagenes). Las imagenes subidas se reemplazan por cid: y se devuelven como
    [(cid, bytes, subtipo)] para adjuntarlas inline al correo."""
    d = (descripcion or "").replace("\r\n", "\n")
    if not es_html(d):
        return _html.escape(d).replace("\n", "<br>"), []
    limpio = limpiar_html(d)
    imagenes: list[tuple[str, bytes, str]] = []

    def _sub(m):
        nombre = f"{m.group(1)}.{m.group(2)}"
        try:
            with open(os.path.join(carpeta_imagenes(), nombre), "rb") as f:
                data = f.read()
        except OSError:
            return ""
        cid = f"img{len(imagenes) + 1}@sgq"
        imagenes.append((cid, data, "jpeg" if m.group(2) in ("jpg", "jpeg") else m.group(2)))
        return f'<img src="cid:{cid}" alt="" style="max-width:100%;height:auto">'

    return _RE_IMG_LIMPIA.sub(_sub, limpio), imagenes
