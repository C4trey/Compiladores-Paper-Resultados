#define _GNU_SOURCE
#include <stddef.h>
#include <stdlib.h>
#include <string.h>

#define N 64

/* Regla (i): el secreto viene de fuera; el compilador no puede precalcularlo. */
extern volatile unsigned char fuente[N];
/* Regla (ii): el resultado se usa; la función no puede eliminarse entera. */
extern volatile int sumidero;


/* P3: búfer en el heap, borrado antes de free. */
__attribute__((noinline)) void victima(void) {
  unsigned char *buf = malloc(N);
  if (buf == NULL) return;
  for (size_t i = 0; i < N; i++) buf[i] = fuente[i];
  int s = 0;
  for (size_t i = 0; i < N; i++) s += buf[i];
  sumidero = s;
  /* T0: sin borrado (control) */
  free(buf);
}
