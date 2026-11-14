/* Arnés del oráculo dinámico para los patrones en pila (P1, P2). */
#include <stdio.h>
#include <stddef.h>

#define N 4096
#define SONDA (2 * N)   /* la sonda mide el doble del secreto */
#define UMBRAL 16

volatile unsigned char fuente[N];
volatile int sumidero;
void victima(void);

/* Ocupa la pila que acaba de liberar victima() y busca restos del secreto. */
__attribute__((noinline)) int escanear(void) {
  volatile unsigned char sonda[SONDA];   /* sin inicializar a propósito */
  int racha = 0, mejor = 0;
  for (int i = 0; i < SONDA; i++) {
    if (sonda[i] == 0xa5) { if (++racha > mejor) mejor = racha; }
    else racha = 0;
  }
  return mejor;
}

int main(void) {
  for (int i = 0; i < N; i++) fuente[i] = 0xa5;
  victima();
  int r = escanear();
  printf("%s %d\n", r >= UMBRAL ? "RESIDUO" : "LIMPIO", r);
  return 0;
}
