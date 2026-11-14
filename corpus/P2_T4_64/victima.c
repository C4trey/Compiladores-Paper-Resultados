#define _GNU_SOURCE
#include <stddef.h>
#include <stdlib.h>
#include <string.h>

#define N 64

/* Regla (i): el secreto viene de fuera; el compilador no puede precalcularlo. */
extern volatile unsigned char fuente[N];
/* Regla (ii): el resultado se usa; la función no puede eliminarse entera. */
extern volatile int sumidero;
static void *(*volatile memset_v)(void *, int, size_t) = memset;

/* P2: campo de clave dentro de una estructura local. */
struct sesion { int id; unsigned char clave[N]; };

__attribute__((noinline)) void victima(void) {
  struct sesion ses;
  ses.id = sumidero;
  for (size_t i = 0; i < N; i++) ses.clave[i] = fuente[i];
  int s = ses.id;
  for (size_t i = 0; i < N; i++) s += ses.clave[i];
  sumidero = s;
  memset_v(ses.clave, 0, N);
}
