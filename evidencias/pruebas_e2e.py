import re, sys, urllib.request, urllib.parse, http.cookiejar, subprocess

BASE = sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:8099/'
resultados = []

class Cliente:
    def __init__(self):
        self.jar = http.cookiejar.CookieJar()
        self.op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))
    def get(self, p):
        try:
            r = self.op.open(BASE + p); return r.status, r.geturl(), r.read().decode('utf8', 'replace')
        except urllib.error.HTTPError as e:
            return e.code, BASE + p, e.read().decode('utf8', 'replace')
    def post(self, p, datos, form_url=None):
        _, _, html = self.get(form_url or p)
        m = re.search(r'name="csrf_token" value="([0-9a-f]{64})"', html)
        if m: datos = dict(datos, csrf_token=m.group(1))
        req = urllib.request.Request(BASE + p, data=urllib.parse.urlencode(datos).encode())
        try:
            r = self.op.open(req); return r.status, r.geturl(), r.read().decode('utf8', 'replace')
        except urllib.error.HTTPError as e:
            return e.code, BASE + p, e.read().decode('utf8', 'replace')

def check(nombre, cond, extra=''):
    resultados.append((nombre, bool(cond)))
    print(('PASS ' if cond else 'FAIL ') + nombre + ('' if cond else '  -> ' + extra[:300]))

def sql(q):
    out = subprocess.run(['wsl', '-e', 'bash', '-c', f'mariadb --no-defaults -S $HOME/qa-banca-db/sock -uroot -N banca_online -e "{q}"'],
                         capture_output=True).stdout.decode('utf8', 'replace').replace('\0', '')
    return out.strip()

def texto(html):
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', html))

# --- Administrador
adm = Cliente()
s, u, h = adm.post('login_admin.php', {'usuario': 'admin', 'clave': 'admin123'})
check('Admin inicia sesión con admin/admin123', 'admin_panel.php' in u, u)
s, u, h = adm.post('admin_cajeros.php', {'accion': 'agregar', 'nombre': 'Cajero Prueba', 'usuario': 'cajero1', 'clave': 'cajero1234', 'confirmar': 'cajero1234'})
check('Admin agrega cajero', 'Cajero agregado correctamente' in h, texto(h))
check('Listado muestra el cajero', 'cajero1' in h and 'No hay cajeros' not in h)
s, u, h = adm.post('admin_cajeros.php', {'accion': 'agregar', 'nombre': 'X', 'usuario': 'cajero1', 'clave': 'cajero1234', 'confirmar': 'cajero1234'})
check('Cajero duplicado rechazado', 'Ya existe un cajero' in h)
s, u, h = adm.post('admin_cajeros.php', {'accion': 'agregar', 'nombre': 'X', 'usuario': 'cajero2', 'clave': 'cajero1234', 'confirmar': 'otra12345'})
check('Confirmación de clave distinta rechazada', 'no coinciden' in h)

# --- Cajero
caj = Cliente()
s, u, h = caj.post('login_cajero.php', {'usuario': 'cajero1', 'clave': 'cajero1234'})
check('Cajero inicia sesión', 'cajero_panel.php' in u, u)
for no, nom, dpi, monto in [('1001', 'Ana Pérez', '1234567890101', '1000'), ('2002', 'Luis Gómez', '2234567890101', '100'), ('3003', 'Marta Ruiz', '3234567890101', '0')]:
    s, u, h = caj.post('cajero_crear_cuenta.php', {'nombre': nom, 'no_cuenta': no, 'dpi': dpi, 'monto': monto})
    check(f'Crear cuenta {no} con Q{monto}', 'Cuenta creada correctamente' in h, texto(h))
s, u, h = caj.post('cajero_crear_cuenta.php', {'nombre': 'Dup', 'no_cuenta': '1001', 'dpi': '1234567890101', 'monto': '5'})
check('Cuenta duplicada rechazada', 'Ya existe una cuenta' in h)
s, u, h = caj.post('cajero_deposito.php', {'no_cuenta': '1001', 'monto': '50'})
check('Depósito Q50', 'Depósito realizado correctamente' in h, texto(h))
s, u, h = caj.post('cajero_deposito.php', {'no_cuenta': '9999', 'monto': '50'})
check('Depósito a cuenta inexistente rechazado', 'La cuenta no existe' in h)
s, u, h = caj.post('cajero_deposito.php', {'no_cuenta': '1001', 'monto': '0'})
check('Depósito cero rechazado', 'Depósito realizado' not in h)
s, u, h = caj.post('cajero_retiro.php', {'no_cuenta': '1001', 'monto': '25'})
check('Retiro Q25', 'Retiro realizado correctamente' in h, texto(h))
s, u, h = caj.post('cajero_retiro.php', {'no_cuenta': '2002', 'monto': '500'})
check('Retiro sin saldo rechazado', 'Saldo insuficiente' in h)
check('Saldo 1001 = 1025.00', sql("select saldo from cuentas where no_cuenta='1001'") == '1025.00')

# --- Registro de clientes
pub = Cliente()
s, u, h = pub.post('registro.php', {'no_cuenta': '7777', 'correo': 'x@example.com', 'dpi': '1234567890101', 'clave': 'clave12345', 'confirmar': 'clave12345'})
check('Registro con cuenta inexistente muestra mensaje (sin error 500)', s == 200 and 'no existe' in h, f'{s} {texto(h)}')
s, u, h = pub.post('registro.php', {'no_cuenta': '1001', 'correo': 'ana@example.com', 'dpi': '9999999999999', 'clave': 'clave12345', 'confirmar': 'clave12345'})
check('Registro con DPI distinto rechazado', 'DPI no coincide' in h)
s, u, h = pub.post('registro.php', {'no_cuenta': '1001', 'correo': 'ana@example.com', 'dpi': '1234567890101', 'clave': 'clave12345', 'confirmar': 'clave12345'})
check('Registro correcto de cliente', 'Usuario registrado correctamente' in h, texto(h))
s, u, h = pub.post('registro.php', {'no_cuenta': '1001', 'correo': 'otra@example.com', 'dpi': '1234567890101', 'clave': 'clave12345', 'confirmar': 'clave12345'})
check('Segundo usuario para la misma cuenta rechazado', 'Ya existe un usuario' in h)
s, u, h = pub.post('registro.php', {'no_cuenta': '2002', 'correo': 'ana@example.com', 'dpi': '2234567890101', 'clave': 'clave12345', 'confirmar': 'clave12345'})
check('Correo duplicado rechazado', 'ya está registrado' in h)
s, u, h = pub.post('registro.php', {'no_cuenta': '2002', 'correo': 'luis@example.com', 'dpi': '2234567890101', 'clave': 'clave12345', 'confirmar': 'clave12345'})
check('Registro de segundo cliente', 'Usuario registrado correctamente' in h)

# --- Cliente
ana = Cliente()
s, u, h = ana.post('login_usuario.php', {'correo': 'ana@example.com', 'clave': 'clave12345'})
check('Cliente inicia sesión', 'usuario_panel.php' in u, u)
check('Panel muestra saldo Q1,025.00', '1,025.00' in h, texto(h))
s, u, h = ana.post('usuario_terceros.php', {'no_cuenta': '1001', 'monto_maximo': '30', 'max_transacciones': '2', 'alias': 'Yo'})
check('Tercero con cuenta propia rechazado', 'propia cuenta' in h)
s, u, h = ana.post('usuario_terceros.php', {'no_cuenta': '8888', 'monto_maximo': '30', 'max_transacciones': '2', 'alias': 'Nadie'})
check('Tercero con cuenta inexistente rechazado', 'no existe' in h)
s, u, h = ana.post('usuario_terceros.php', {'no_cuenta': '2002', 'monto_maximo': '30', 'max_transacciones': '2', 'alias': 'Luis'})
check('Agregar tercero', 'agregada correctamente' in h, texto(h))
tid = sql("select id from cuentas_terceros where correo_usuario='ana@example.com'")
s, u, h = ana.post('usuario_transferencia.php', {'id_tercero': tid, 'monto': '40'})
check('Transferencia mayor al máximo rechazada', 'máximo' in h and 'correctamente' not in h, texto(h))
s, u, h = ana.post('usuario_transferencia.php', {'id_tercero': tid, 'monto': '25'})
check('Transferencia Q25', 'Transferencia realizada correctamente' in h, texto(h))
s, u, h = ana.post('usuario_transferencia.php', {'id_tercero': tid, 'monto': '10'})
check('Segunda transferencia Q10', 'Transferencia realizada correctamente' in h, texto(h))
s, u, h = ana.post('usuario_transferencia.php', {'id_tercero': tid, 'monto': '5'})
check('Tercera transferencia del día rechazada (límite 2)', 'máxima de transferencias' in h or 'máximo de transferencias' in h, texto(h))
check('Saldos tras transferencias 990.00 / 135.00',
      sql("select group_concat(saldo order by no_cuenta) from cuentas where no_cuenta in ('1001','2002')") == '990.00,135.00')
s, u, h = ana.get('usuario_estado.php')
t = texto(h)
check('Estado de cuenta lista depósito, retiro y transferencias', all(x in t for x in ['DEPOSITO', 'RETIRO', 'TRANSFERENCIA']), t)

luis = Cliente()
luis.post('login_usuario.php', {'correo': 'luis@example.com', 'clave': 'clave12345'})
s, u, h = luis.get('usuario_terceros.php')
check('Otro cliente no ve los terceros de Ana', 'Luis' not in re.sub(r'<header.*?</header>', '', h, flags=re.S) or 'No tiene' in h)
s, u, h = luis.post('usuario_transferencia.php', {'id_tercero': tid, 'monto': '1'})
check('Otro cliente no puede usar el tercero de Ana', 'correctamente' not in h)
s, u, h = luis.get('admin_panel.php')
check('Cliente no entra al panel de admin', 'login_admin.php' in u, u)

# --- Monitor, detalles y logs
s, u, h = adm.get('admin_monitor.php')
t = texto(h)
check('Monitor responde', s == 200 and 'Depósitos vs retiros' in h, t)
check('Monitor: 3 cuentas hoy y 2 clientes hoy', re.search(r'Cuentas creadas hoy 3', t) and re.search(r'Usuarios cliente hoy 2', t), t)
check('Gráfica con Q50.00 y Q25.00', 'Q50.00' in h and 'Q25.00' in h)
for tipo in ['cuentas', 'usuarios', 'transacciones', 'depositos', 'retiros']:
    s, u, h = adm.get('admin_detalle.php?tipo=' + tipo)
    check(f'Detalle {tipo}', s == 200 and 'No hay registros' not in h, texto(h))
s, u, h = adm.get('logs.php')
check('Logs muestra solicitudes y códigos', s == 200 and 'Total de Solicitudes' in h and '302' in h, texto(h))

# --- Bloqueo de cajero
adm.post('admin_cajeros.php', {'accion': 'estado', 'usuario': 'cajero1', 'activo': '0'})
s, u, h = caj.get('cajero_deposito.php')
check('Cajero bloqueado pierde acceso', 'login_cajero.php' in u, u)
s, u, h = Cliente().post('login_cajero.php', {'usuario': 'cajero1', 'clave': 'cajero1234'})
check('Cajero bloqueado no puede iniciar sesión', 'cajero_panel.php' not in u)
adm.post('admin_cajeros.php', {'accion': 'estado', 'usuario': 'cajero1', 'activo': '1'})
s, u, h = Cliente().post('login_cajero.php', {'usuario': 'cajero1', 'clave': 'cajero1234'})
check('Cajero desbloqueado vuelve a entrar', 'cajero_panel.php' in u)

ok = sum(1 for _, r in resultados if r)
print(f'\n{ok}/{len(resultados)} pruebas correctas')
