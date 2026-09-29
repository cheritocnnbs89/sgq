# modules/app_core/app_usuarios_activos.py
# -*- coding: utf-8 -*-
"""Visibilidad en terminal de qué usuarios están conectados ahora mismo -- sin tabla
ni pantalla nueva: un before_request actualiza un registro en memoria (por proceso)
y un hilo en segundo plano imprime una foto cada pocos minutos. Si el proceso corre
con varios workers, cada uno ve solo a los usuarios que le tocó atender -- para el
uso que se le quiere dar (ver rápido quién anda activo) alcanza igual."""
from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta

from flask import session

# Mismo criterio que el cierre de sesión por inactividad: pasado este tiempo sin
# ninguna petición, se deja de considerar "en línea" al usuario.
MINUTOS_INACTIVIDAD = 60
INTERVALO_IMPRESION_SEGUNDOS = 5 * 60

_activos: dict[int, dict] = {}
_lock = threading.Lock()


def _registrar_actividad() -> None:
    uid = session.get("usuario_id")
    if not uid:
        return
    nombre = session.get("usuario") or f"usuario#{uid}"
    rol = session.get("rol") or ""
    ahora = datetime.now()
    with _lock:
        previo = _activos.get(uid)
        _activos[uid] = {"nombre": nombre, "rol": rol, "last_seen": ahora}
    # Solo imprime cuando el usuario "vuelve" (no tenía actividad reciente) -- si
    # imprimiera en cada petición, llenaría la terminal con una línea por clic.
    if not previo or (ahora - previo["last_seen"]) > timedelta(minutes=5):
        print(f"[usuarios-activos] {ahora:%H:%M:%S} conectado: {nombre} ({rol})", flush=True)


def _imprimir_snapshot_periodico() -> None:
    while True:
        time.sleep(INTERVALO_IMPRESION_SEGUNDOS)
        ahora = datetime.now()
        limite = timedelta(minutes=MINUTOS_INACTIVIDAD)
        with _lock:
            vencidos = [uid for uid, d in _activos.items() if ahora - d["last_seen"] > limite]
            for uid in vencidos:
                del _activos[uid]
            snapshot = sorted(_activos.values(), key=lambda d: d["last_seen"], reverse=True)
        if snapshot:
            nombres = ", ".join(d["nombre"] for d in snapshot)
            print(f"[usuarios-activos] {ahora:%H:%M:%S} en línea ({len(snapshot)}): {nombres}", flush=True)
        else:
            print(f"[usuarios-activos] {ahora:%H:%M:%S} nadie conectado", flush=True)


def register_usuarios_activos(app) -> None:
    @app.before_request
    def _antes_de_cada_request():
        _registrar_actividad()

    hilo = threading.Thread(target=_imprimir_snapshot_periodico, daemon=True, name="UsuariosActivos")
    hilo.start()
