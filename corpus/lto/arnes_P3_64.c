/* Arnés del oráculo dinámico para el patrón en heap (P3). */
#include <stdio.h>
#include <stdlib.h>

#define N 64
#define UMBRAL 16

volatile unsigned char fuente[N];
volatile int sumidero;
void victima(void);

int main(void) {
  for (int i = 0; i < N; i++) fuente[i] = 0xa5;
  victima();
  /* Pide un bloque del mismo tamaño: el asignador reutiliza el que liberó victima().
     Se examina desde el byte 16 porque glibc sobrescribe los primeros 16 bytes. */
  volatile unsigned char *q = malloc(N);
  int racha = 0, mejor = 0;
  for (int i = 16; i < N; i++) {
    if (q[i] == 0xa5) { if (++racha > mejor) mejor = racha; }
    else racha = 0;
  }
  printf("%s %d\n", mejor >= UMBRAL ? "RESIDUO" : "LIMPIO", mejor);
  free((void *)q);
  return 0;
}
