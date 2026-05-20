import os
import smtplib
from email.mime.text import MIMEText
from .db import get_config_value

def send_email(recipients, subject, message):
    host = get_config_value('smtp_host') or os.environ.get('SMTP_HOST')
    port = get_config_value('smtp_port') or os.environ.get('SMTP_PORT', '587')
    user = get_config_value('smtp_user') or os.environ.get('SMTP_USER')
    password = get_config_value('smtp_pass') or os.environ.get('SMTP_PASS')
    sender = get_config_value('smtp_from') or os.environ.get('SMTP_FROM') or user

    try:
        port_int = int(port) if port else 587
    except Exception:
        port_int = 587

    if not host or not user or not password:
        print('[NOTIFICATION] SMTP no configurado; imprimiendo correo.')
        print('  Para:', recipients)
        print('  Asunto:', subject)
        print('  Mensaje:\n', message)
        return

    msg = MIMEText(message, 'plain', 'utf-8')
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = ', '.join(recipients)

    try:
        with smtplib.SMTP(host, port_int) as server:
            server.starttls()
            server.login(user, password)
            server.sendmail(sender, recipients, msg.as_string())
    except Exception as exc:
        print('[ERROR] Error al enviar correo:', exc)
        print('  Para:', recipients)
        print('  Asunto:', subject)
        print('  Mensaje:\n', message)

import threading
def send_email_async(recipients, subject, message):
    try:
        t = threading.Thread(target=send_email, args=(recipients, subject, message))
        t.daemon = True
        t.start()
    except Exception as exc:
        print('[ERROR] No se pudo iniciar hilo de correo:', exc)
