# modules/xml_bp.py
from flask import Blueprint, render_template, request, jsonify
import xml.etree.ElementTree as ET
import re

xml_bp = Blueprint('xml', __name__, template_folder='templates')

# ------------ utilidades ------------
def _strip_ns(elem):
    elem.tag = elem.tag.split('}')[-1]
    for e in list(elem):
        _strip_ns(e)

def _txt(e, path, default=''):
    n = e.find(path)
    return (n.text.strip() if n is not None and n.text else default)

def _sfloat(s):
    if s is None:
        return 0.0
    s = str(s).strip().replace(',', '.')
    try:
        return float(s)
    except Exception:
        return 0.0

# ------------ parser SRI ------------
def parse_sri_invoice(xml_bytes: bytes) -> dict:
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        xml_bytes = re.sub(rb'^[^\<]*', b'', xml_bytes)
        root = ET.fromstring(xml_bytes)
    _strip_ns(root)

    num_aut = fecha_aut = ''
    fac = None
    if root.tag.lower() in ('autorizacion', 'respuestaautorizacioncomprobante'):
        num_aut = _txt(root, 'numeroAutorizacion')
        fecha_aut = _txt(root, 'fechaAutorizacion')
        comp = root.find('comprobante')
        if comp is not None and comp.text:
            inner_txt = comp.text.strip()
            inner_txt = inner_txt[inner_txt.find('<'):]
            fac = ET.fromstring(inner_txt.encode('utf-8')); _strip_ns(fac)
            if fac.tag != 'factura':
                fac = fac.find('.//factura')
        if fac is None:
            fac = root.find('.//factura')
    else:
        fac = root if root.tag == 'factura' else root.find('.//factura')

    if fac is None:
        raise ValueError('No se encontró <factura> en el XML.')

    it = fac.find('infoTributaria') or ET.Element('infoTributaria')
    inf = fac.find('infoFactura') or ET.Element('infoFactura')

    estab = _txt(it, 'estab'); ptoEmi = _txt(it, 'ptoEmi'); sec = _txt(it, 'secuencial')
    serie = '-'.join(filter(None, [estab, ptoEmi, sec])) or sec

    total_sin = _sfloat(_txt(inf, 'totalSinImpuestos'))
    iva_base = iva_val = 0.0
    tot_imp = inf.find('totalConImpuestos')
    if tot_imp is not None:
        for ti in tot_imp.findall('totalImpuesto'):
            codigo = _txt(ti, 'codigo')
            base = _sfloat(_txt(ti, 'baseImponible'))
            valor = _sfloat(_txt(ti, 'valor'))
            if codigo == '2' and valor >= 0:
                iva_base += base; iva_val += valor
    base_0 = max(0.0, round(total_sin - iva_base, 2))

    forma_pago = ''
    pagos = inf.find('pagos')
    if pagos is not None:
        fp = pagos.find('pago/formaPago')
        if fp is not None and fp.text:
            forma_pago = fp.text.strip()
    if not forma_pago:
        forma_pago = _txt(inf, 'formaPago')

    oc = ''; venc = ''
    info_ad = fac.find('infoAdicional')
    if info_ad is not None:
        for campo in info_ad.findall('campoAdicional'):
            nombre = (campo.attrib.get('nombre', '') or '').lower()
            val = (campo.text or '').strip()
            if not oc and any(k in nombre for k in ['orden', 'o.c', 'oc', 'noorden', 'ordencompra', 'n° orden', 'nro orden']):
                oc = val
            if not venc and any(k in nombre for k in ['venc', 'máx', 'max', 'pago', 'f. pago', 'fecha pago']):
                venc = val

    items = len(fac.findall('detalles/detalle'))

    return {
        'Archivo': '',
        'EmisorRUC': _txt(it, 'ruc'),
        'EmisorRazonSocial': _txt(it, 'razonSocial') or _txt(it, 'nombreComercial'),
        'Serie': serie,
        'FechaImpresion': _txt(inf, 'fechaEmision'),
        'BaseIVA': f'{iva_base:.2f}',
        'Base0': f'{base_0:.2f}',
        'IVA': f'{iva_val:.2f}',
        'Total': _txt(inf, 'importeTotal'),
        'ClaveAcceso': _txt(it, 'claveAcceso'),
        'NumAutorizacion': num_aut,
        'FechaAutorizacion': fecha_aut,
    }

# ------------ rutas ------------
@xml_bp.get('/')
def index():
    return render_template('xml/index.html')

@xml_bp.post('/api/parse')
def api_parse():
    files = request.files.getlist('files[]')
    results = []
    for f in files:
        if not f or not f.filename.lower().endswith('.xml'):
            continue
        try:
            row = parse_sri_invoice(f.read())
            row['Archivo'] = f.filename
            results.append(row)
        except Exception as e:
            results.append({'Archivo': f.filename,
                            'EmisorRUC':'ERROR', 'EmisorRazonSocial':str(e),
                            'Serie':'', 'FechaImpresion':'', 'BaseIVA':'',
                            'Base0':'', 'IVA':'', 'Total':'', 'ClaveAcceso':'',
                            'NumAutorizacion':'', 'FechaAutorizacion':''})
    return jsonify({'data': results})
