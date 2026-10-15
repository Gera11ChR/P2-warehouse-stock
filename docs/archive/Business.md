# DMS-TELECOM — Valoración económica y posición comercial

**Fecha:** 2026-10-05
**Alcance:** valoración re-anclada a costos de producción con IA (2026) + segmentación de precio por tipo de comprador.
**Naturaleza:** estimación razonada, no una tasación formal ni una oferta contractual.
**Relación con otros documentos:** re-ancla y sustituye los rangos económicos de [`valoracion-economica.md`](valoracion-economica.md) (2026-09-30), que queda como registro del modelo histórico. `README.md` §11 no se actualiza por decisión expresa (2026-10-05).

---

## 1. Por qué una re-anclación

El modelo anterior (`valoracion-economica.md`) dimensionaba el esfuerzo con criterios convencionales pre-IA (1,600–2,250 h de agencia a tarifas de $45–$110 USD/h) y bandas de precios de lista de agencias (Rorix, Stfalcon, YuSMP), que son cotizaciones de mercado tradicional, no costos reales de producción con IA.

Los hechos observados en este repositorio contradicen esas bases:

| Dato observado | Valor |
| --- | --- |
| Ventana de entrega | 29 días calendario (2026-09-02 → 2026-09-30) |
| Equipo de producción | 1 desarrollador junior + flota de agentes IA |
| Desembolso en herramienta IA | ≈ $3,000 MXN (≈ $170 USD) |
| Banda publicada AI-first MVP (Groovy Web, 2026) | $15,000 – $50,000 USD (4–8 semanas, 1–2 personas) |

Principio rector de esta revisión: **el costo no es el valor**. El costo de producción colapsó con la IA; el valor para un comprador depende de *su* alternativa más barata. Cada enfoque se ancla a su ancla real.

## 2. Resumen consolidado

| Enfoque | Interpretación | Rango (USD) | Rango (MXN, a 18) | Confianza |
| --- | --- | --- | --- | --- |
| **A — Costo de producción** | Lo que costó realmente, con IA | **$1,000 – $4,500** | $18,000 – $81,000 | Alta (observado) |
| **B — Reemplazo / mercado** | Lo que cuesta encargar hoy el mismo alcance — *titular* | **$15,000 – $50,000** | **$270,000 – $900,000** | Media |
| **C — Valor en uso (5 años)** | Beneficio vs. licenciar un WMS SaaS | **$30,000 – $150,000** | $540,000 – $2,700,000 | Media-baja |
| **D — Valor producto (3 años)** | Si se empaqueta y licencia | **$30,000 – $70,000** | $540,000 – $1,260,000 | Baja (condicionada) |

> **Cifra titular para uso externo: USD $15,000 – $50,000 (≈ $270,000 – $900,000 MXN).**
> La banda anterior $75,000–$200,000 se conserva únicamente como *contrafactual de agencia tradicional (precios de lista 2026, en declive)*: lo que todavía cobra una agencia full-service, no lo que cuesta producir con IA.

## 3. Detalle por enfoque

### 3.1 Enfoque A — Costo de producción: $1,000 – $4,500

| Línea | Bajo | Alto | Base |
| --- | --- | --- | --- |
| Caja real: 1 mes de salario mínimo + herramienta IA + infra mínima | $700 | $1,500 | Salario mínimo general 2026 (≈ $9,000–$10,000 MXN/mes) + $3,000 MXN tooling + infra local |
| Valor junior de mercado (1 mes, AI-leveraged) | $1,500 | $4,500 | Sueldo publicado de desarrollador junior en México ≈ $12,800–$15,300 MXN/mes, ajustado por entrega AI-acelerada |

Esfuerzo observado: **160–300 h** (1 dev-mes, 29 días). El dimensionamiento convencional de 1,600–2,250 h del modelo anterior se conserva solo como cross-check de mercado (lo que dimensionaría una agencia tradicional).

### 3.2 Enfoque B — Reemplazo / mercado: $15,000 – $50,000 (titular)

Anclas:

1. **Banda AI-first publicada**: MVP de alcance comparable en 4–8 semanas con 1–2 personas: **$15k–$50k** (Groovy Web, 2026).
2. **Cross-check por horas observadas** (matriz §4): $4k–$22.5k → piso del rango.
3. **Contrafactual de agencia legada**: $75k–$200k (Rorix/Stfalcon) → se descarta como ancla principal; son precios de lista que aún cotizan equipos tradicionales y están en declive.

Ajustes (heredados del modelo original): prima de calidad +5–15% (644 pruebas, ledger inmutable, gobernanza) y descuento −20–35% por integraciones ausentes (sin ERP, carrier, hardware, móvil, multi-tenant). El resultado ajustado converge en **$15k–$50k**.

### 3.3 Enfoque C — Valor en uso (5 años): $30,000 – $150,000

La ancla no cambió con la IA: las suscripciones SaaS WMS **subieron** 30–50% desde 2023 ($18k–$120k/año evitados). El ajuste es de realismo de comprador:

| Perfil del operador | Valor en uso (5 años) |
| --- | --- |
| Operador que desplaza una suscripción WMS real (10–20 usuarios) | $50,000 – $150,000 |
| **Operador pequeño con control manual funcional (≈30 personas, trazabilidad adecuada)** | **≈ $0 – $10,000** |

El segundo renglón es el contra-caso honesto: si la alternativa real es seguir con hojas de cálculo, el valor en uso colapsa hacia cero y el precio debe venir de otra ancla (comodidad, continuidad, prevención de pérdidas).

### 3.4 Enfoque D — Valor producto (3 años): $30,000 – $70,000

| Componente | Precio |
| --- | --- |
| Licencia perpetua, una sede | $20,000 – $40,000 |
| Soporte y actualizaciones | 18% de la licencia / año × 3 |

Sigue **condicionado** a cerrar la deuda de autenticación (sin IdP externo/OAuth2 no es vendible a terceros).

## 4. Sensibilidad — Enfoque B (tarifa × horas observadas)

| | 160 h | 230 h | 300 h |
| --- | --- | --- | --- |
| **$25/h** (freelance junior AI) | $4,000 | $5,750 | $7,500 |
| **$45/h** (freelance senior AI) | $7,200 | $10,350 | $13,500 |
| **$75/h** (estudio AI-first) | $12,000 | $17,250 | $22,500 |

Lectura: la matriz por horas es el **piso** ($4k–$22.5k); el rango titular $15k–$50k está dominado por la banda de mercado AI-first, porque un comprador paga precio de mercado, no horas del vendedor.

Palancas que mueven más el número (en orden):
1. Alcance de integraciones (ERP/hardware/móvil): puede duplicar o reducir a la mitad.
2. Modelo de entrega y tarifa (freelance vs. agencia): ~4× de spread.
3. Si el comprador valora la evidencia de QA/gobernanza: la diferencia entre "código" y "sistema verificado".

## 5. Precio por tipo de comprador

| Perfil de comprador | Qué pagaría | Por qué |
| --- | --- | --- |
| Operador pequeño, control manual funciona | **$0 – $10,000 USD** o piloto/suscripción baja | Su alternativa más barata es gratis; el valor es comodidad y continuidad |
| Operador que desplaza un SaaS WMS | Banda C ($30k–$150k a 5 años) | Ancla = suscripción evitada |
| Comprador externo que encarga el alcance | Banda B ($15k–$50k) | Costo de replicación 2026 con IA |
| Producto empaquetado multi-cliente | Banda D ($30k–$70k) | Licencia + soporte; condicionado a auth |

> **El precio para un comprador concreto = su alternativa más barata, no esta tabla.**

### 5.1 Ejemplo trabajado — operador pequeño actual

Estructura de referencia para el comprador actual (empresa ≈30 personas, trazabilidad manual funcional, sin SaaS previo):

| Concepto | Monto (MXN) |
| --- | --- |
| Apertura de negociación | $69,800 |
| Zona objetivo de cierre | $49,800 – $59,800 |
| Piso (solo con condiciones favorables: pago anticipado, sin personalizaciones futuras) | ≈ $40,000 – $44,800 |
| Soporte y mantenimiento posterior | $8,000 – $15,000 / año (opcional, limitado y definido) |
| Cesión de código fuente / derechos amplios | $120,000 – $180,000+ (negociación independiente) |

- Licencia perpetua de uso, una empresa/sede; **el código y la propiedad intelectual permanecen con el autor**.
- Personalizaciones futuras siempre por separado.
- La cesión del código NO se cotiza al mismo precio de la licencia.

> Esta zona se ubica dentro de la banda "operador pequeño" (§5) y muy por debajo del ancla externa ($270k–$900k MXN): precio amigable justificado por la segmentación, no por el costo de producción.

## 6. Supuestos y riesgos

1. Alcance tal como se entregó: una sede, un tenant, 43 endpoints, sin ERP/carrier/hardware/móvil.
2. El modelo productivo real es **1 desarrollador junior + agentes IA**; las bandas de agencia son contrafactual.
3. Salarios: salario mínimo general 2026 y sueldos junior publicados en México (≈ $12,800–$15,300 MXN/mes).
4. Tipo de cambio ilustrativo: 18 MXN/USD.
5. Las bandas AI-first ($15k–$50k) son publicadas por terceros en 2026; pueden variar ±30%.
6. El valor en uso supone que el comprador desplaza una alternativa pagada; si seguiría con hojas de cálculo, colapsa (renglón de operador pequeño, §3.3).
7. El valor producto (§3.4) está condicionado a cerrar la autenticación externa.
8. **Riesgo de titularidad (revisar antes de licenciar):** para programas de cómputo creados por empleados en ejercicio de sus funciones, la LFDA presume la titularidad patrimonial del empleador salvo pacto en contrario. Antes de firmar licencia o cesión, verificar contrato laboral y condiciones de creación del proyecto.

## 7. Control de cambios

- Este documento es la fuente de verdad de las cifras re-ancladas a IA a partir de 2026-10-05.
- Los rangos de `valoracion-economica.md` (2026-09-30) quedan como modelo histórico/legado; cualquier uso externo debe citar este documento.
- Revalidar al menos anualmente: las bandas AI-first son el insumo más volátil.
