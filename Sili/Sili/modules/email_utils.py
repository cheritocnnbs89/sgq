import os
import smtplib
import mimetypes
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from .db import get_config_value

def send_email(recipients, subject, message, attachments=None):
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

    _subtype = 'html' if message.lstrip().startswith(('<', '<!')) else 'plain'

    if attachments:
        msg = MIMEMultipart()
        msg.attach(MIMEText(message, _subtype, 'utf-8'))
        for path, filename in attachments:
            mime_type, _ = mimetypes.guess_type(path)
            main_type, sub_type = (mime_type or 'application/octet-stream').split('/', 1)
            with open(path, 'rb') as f:
                part = MIMEBase(main_type, sub_type)
                part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', 'attachment', filename=filename)
            msg.attach(part)
    else:
        msg = MIMEText(message, _subtype, 'utf-8')

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
def send_email_async(recipients, subject, message, attachments=None):
    try:
        t = threading.Thread(target=send_email, args=(recipients, subject, message, attachments))
        t.daemon = True
        t.start()
    except Exception as exc:
        print('[ERROR] No se pudo iniciar hilo de correo:', exc)
