"""Definiciones compartidas por todos los experimentos.

Contiene:
  - las técnicas de borrado T0-T9 y los patrones de uso P1-P3 (Tablas 2 y 3 del artículo),
  - las plantillas de C a partir de las cuales se genera el corpus,
  - los dos oráculos (estático diferencial y dinámico) y la clasificación combinada.
"""
import os
import re
import subprocess

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORPUS = os.path.join(RAIZ, "corpus")
RESULTADOS = os.path.join(RAIZ, "resultados")

# Compiladores del estudio (Tabla 5). Se pueden cambiar con la variable COMPILADORES.
COMPILADORES = os.environ.get("COMPILADORES", "gcc-13 gcc-15 clang-18 clang-22").split()
NIVELES = ["O0", "O1", "O2", "O3", "Os", "Oz"]
TECNICAS = ["T0", "T1", "T2", "T3", "T4", "T5", "T6", "T7", "T8", "T9"]
PATRONES = ["P1", "P2", "P3"]
TAMANOS = [64, 4096]

# Opciones comunes a TODAS las compilaciones (ver Metodología):
#  -std=gnu2x          : necesario para declarar memset_explicit (C23); se usa en todo por igualdad.
#  -U_FORTIFY_SOURCE   : Ubuntu activa _FORTIFY_SOURCE por defecto en GCC y no en Clang.
BASE = ["-std=gnu2x", "-U_FORTIFY_SOURCE"]

# Opciones adicionales propias de una técnica.
EXTRA = {"T8": ["-fno-builtin-memset"]}

UMBRAL = 16          # bytes consecutivos del patrón para declarar residuo
PATRON_BYTE = 0xA5   # valor con que se llena el secreto


def es_gcc(cc):
    return cc.startswith("gcc")


# ---------------------------------------------------------------------------
# Técnicas de borrado. {p} es la expresión del búfer; N es el tamaño.
# ---------------------------------------------------------------------------
TECNICA_DECL = {
    "T4": "static void *(*volatile memset_v)(void *, int, size_t) = memset;",
    "T9": "void limpiar(void *p, size_t n);   /* definida en util.c */",
}

TECNICA_CODIGO = {
    "T0": "/* T0: sin borrado (control) */",
    "T1": "memset({p}, 0, N);",
    "T2": "for (size_t i = 0; i < N; i++) ({p})[i] = 0;",
    "T3": "{{ volatile unsigned char *vp = (volatile unsigned char *)({p});\n"
          "    for (size_t i = 0; i < N; i++) vp[i] = 0; }}",
    "T4": "memset_v({p}, 0, N);",
    "T5": "memset({p}, 0, N);\n  __asm__ __volatile__(\"\" : : \"r\"({p}) : \"memory\");",
    "T6": "explicit_bzero({p}, N);",
    "T7": "memset_explicit({p}, 0, N);",
    "T8": "memset({p}, 0, N);   /* compilado con -fno-builtin-memset */",
    "T9": "limpiar({p}, N);",
}

UTIL_T9 = """#include <string.h>
#include <stddef.h>

/* T9: función de borrado definida en otra unidad de compilación. */
void limpiar(void *p, size_t n) { memset(p, 0, n); }
"""

# ---------------------------------------------------------------------------
# Patrones de uso (función bajo prueba).
# ---------------------------------------------------------------------------
CABECERA = """#define _GNU_SOURCE
#include <stddef.h>
#include <stdlib.h>
#include <string.h>

#define N {n}

/* Regla (i): el secreto viene de fuera; el compilador no puede precalcularlo. */
extern volatile unsigned char fuente[N];
/* Regla (ii): el resultado se usa; la función no puede eliminarse entera. */
extern volatile int sumidero;
{decl}
"""

PATRON_CODIGO = {
    "P1": """/* P1: arreglo local en la pila. Regla (iii): su dirección nunca escapa. */
__attribute__((noinline)) void victima(void) {{
  unsigned char buf[N];
  for (size_t i = 0; i < N; i++) buf[i] = fuente[i];
  int s = 0;
  for (size_t i = 0; i < N; i++) s += buf[i];
  sumidero = s;
  {borrado}
}}
""",
    "P2": """/* P2: campo de clave dentro de una estructura local. */
struct sesion {{ int id; unsigned char clave[N]; }};

__attribute__((noinline)) void victima(void) {{
  struct sesion ses;
  ses.id = sumidero;
  for (size_t i = 0; i < N; i++) ses.clave[i] = fuente[i];
  int s = ses.id;
  for (size_t i = 0; i < N; i++) s += ses.clave[i];
  sumidero = s;
  {borrado}
}}
""",
    "P3": """/* P3: búfer en el heap, borrado antes de free. */
__attribute__((noinline)) void victima(void) {{
  unsigned char *buf = malloc(N);
  if (buf == NULL) return;
  for (size_t i = 0; i < N; i++) buf[i] = fuente[i];
  int s = 0;
  for (size_t i = 0; i < N; i++) s += buf[i];
  sumidero = s;
  {borrado}
  free(buf);
}}
""",
}
PUNTERO = {"P1": "buf", "P2": "ses.clave", "P3": "buf"}

# ---------------------------------------------------------------------------
# Arneses (oráculo dinámico). Se compilan SIEMPRE con -O0 y sin LTO.
# ---------------------------------------------------------------------------
ARNES_PILA = """/* Arnés del oráculo dinámico para los patrones en pila (P1, P2). */
#include <stdio.h>
#include <stddef.h>

#define N {n}
#define SONDA (2 * N)   /* la sonda mide el doble del secreto */
#define UMBRAL {umbral}

volatile unsigned char fuente[N];
volatile int sumidero;
void victima(void);

/* Ocupa la pila que acaba de liberar victima() y busca restos del secreto. */
__attribute__((noinline)) int escanear(void) {{
  volatile unsigned char sonda[SONDA];   /* sin inicializar a propósito */
  int racha = 0, mejor = 0;
  for (int i = 0; i < SONDA; i++) {{
    if (sonda[i] == {byte}) {{ if (++racha > mejor) mejor = racha; }}
    else racha = 0;
  }}
  return mejor;
}}

int main(void) {{
  for (int i = 0; i < N; i++) fuente[i] = {byte};
  victima();
  int r = escanear();
  printf("%s %d\\n", r >= UMBRAL ? "RESIDUO" : "LIMPIO", r);
  return 0;
}}
"""

ARNES_HEAP = """/* Arnés del oráculo dinámico para el patrón en heap (P3). */
#include <stdio.h>
#include <stdlib.h>

#define N {n}
#define UMBRAL {umbral}

volatile unsigned char fuente[N];
volatile int sumidero;
void victima(void);

int main(void) {{
  for (int i = 0; i < N; i++) fuente[i] = {byte};
  victima();
  /* Pide un bloque del mismo tamaño: el asignador reutiliza el que liberó victima().
     Se examina desde el byte 16 porque glibc sobrescribe los primeros 16 bytes. */
  volatile unsigned char *q = malloc(N);
  int racha = 0, mejor = 0;
  for (int i = 16; i < N; i++) {{
    if (q[i] == {byte}) {{ if (++racha > mejor) mejor = racha; }}
    else racha = 0;
  }}
  printf("%s %d\\n", mejor >= UMBRAL ? "RESIDUO" : "LIMPIO", mejor);
  free((void *)q);
  return 0;
}}
"""


def fuente_victima(patron, tecnica, n):
    decl = TECNICA_DECL.get(tecnica, "")
    borrado = TECNICA_CODIGO[tecnica].format(p=PUNTERO[patron])
    return CABECERA.format(n=n, decl=decl) + "\n" + PATRON_CODIGO[patron].format(borrado=borrado)


def fuente_arnes(patron, n):
    plantilla = ARNES_HEAP if patron == "P3" else ARNES_PILA
    return plantilla.format(n=n, umbral=UMBRAL, byte=hex(PATRON_BYTE))


# ---------------------------------------------------------------------------
# Utilidades de ejecución
# ---------------------------------------------------------------------------
def ejecutar(cmd, cwd=None, timeout=60):
    """Ejecuta un comando y devuelve (código, stdout, stderr)."""
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    return p.returncode, p.stdout, p.stderr


def correr_binario(ruta, veces=3):
    """Oráculo dinámico: ejecuta el binario varias veces.
    Devuelve (dinamico, racha, determinista)."""
    salidas = []
    for _ in range(veces):
        code, out, _ = ejecutar([ruta], timeout=10)
        salidas.append(out.strip() if code == 0 else f"ERROR {code}")
    # Se juzga el determinismo por la clasificación (RESIDUO/LIMPIO): la racha exacta
    # puede variar en 1 byte suelto por la aleatorización de direcciones (ASLR).
    clases = [x.split()[0] for x in salidas]
    determinista = len(set(clases)) == 1
    if clases[0] not in ("RESIDUO", "LIMPIO"):
        return "ERROR", -1, determinista
    return clases[0], max(int(x.split()[1]) for x in salidas), determinista


# ---------------------------------------------------------------------------
# Oráculo estático diferencial
# ---------------------------------------------------------------------------
def extraer_funcion_asm(texto, nombre="victima"):
    """Devuelve las instrucciones normalizadas de una función en un archivo .s."""
    lineas, dentro = [], False
    for linea in texto.splitlines():
        if not dentro:
            # Clang escribe "victima:  # @victima": se ignora el comentario.
            if linea.split("#")[0].strip() == f"{nombre}:":
                dentro = True
            continue
        s = linea.split("#")[0].strip()
        if s.startswith(".cfi_endproc") or s.startswith(".Lfunc_end") or s.startswith(".size"):
            break
        if not s or s.startswith(".") and not s.startswith(".L") or s.endswith(":"):
            continue
        lineas.append(re.sub(r"\.L\w+", ".L", s))   # las etiquetas locales cambian de nombre
    return lineas


def extraer_funciones_objdump(texto, nombres=("victima", "limpiar")):
    """Instrucciones normalizadas de varias funciones de un ejecutable (para LTO)."""
    resultado, actual = [], None
    for linea in texto.splitlines():
        m = re.match(r"^[0-9a-f]+ <([^>]+)>:$", linea)
        if m:
            actual = m.group(1) if m.group(1) in nombres else None
            if actual:
                resultado.append(f"<{actual}>")
            continue
        if actual and "\t" in linea:
            instr = linea.split("\t", 1)[1].strip()
            instr = re.sub(r"\b[0-9a-f]{4,}\b", "ADDR", instr)   # direcciones absolutas
            instr = re.sub(r"0x[0-9a-f]+\(%rip\)", "OFF(%rip)", instr)
            resultado.append(instr)
    return resultado


def categoria(tecnica, estatico, dinamico):
    """Clasificación combinada (Tabla 3 del artículo)."""
    if tecnica == "T0":
        return "control"
    if "ERROR" in (estatico, dinamico) or "NO_COMPILA" in (estatico, dinamico):
        return "error"
    return {
        ("PRESENTE", "LIMPIO"): "protegido",
        ("ELIMINADO", "RESIDUO"): "vulnerable",
        ("PRESENTE", "RESIDUO"): "ineficaz",       # queda código del borrado, pero el secreto sigue
        ("ELIMINADO", "LIMPIO"): "no_concluyente",
    }[(estatico, dinamico)]
