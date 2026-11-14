/* Arnés y oráculo dinámico. SIEMPRE se compila con -O0 y sin -flto,
 * para que el compilador no altere la medición. */
#include <stdio.h>

#define N 64                 /* tamaño del secreto */
#define SONDA (2 * N)        /* la sonda mide el doble del secreto (ver Metodología) */
#define UMBRAL 16            /* bytes consecutivos del patrón para declarar residuo */

volatile unsigned char fuente[N];
volatile int sumidero;
void victima(void);

/* Lee la zona de pila que acaba de usar victima() y busca el secreto (0xA5). */
__attribute__((noinline)) int escanear(void) {
  volatile unsigned char sonda[SONDA];  /* sin inicializar a propósito */
  int racha = 0, mejor = 0;
  for (int i = 0; i < SONDA; i++) {
    if (sonda[i] == 0xA5) { if (++racha > mejor) mejor = racha; }
    else racha = 0;
  }
  return mejor;   /* bytes consecutivos del secreto encontrados */
}

int main(void) {
  for (int i = 0; i < N; i++) fuente[i] = 0xA5;
  victima();
  int r = escanear();
  printf("%s %d\n", r >= UMBRAL ? "RESIDUO" : "LIMPIO", r);
  return 0;
}
