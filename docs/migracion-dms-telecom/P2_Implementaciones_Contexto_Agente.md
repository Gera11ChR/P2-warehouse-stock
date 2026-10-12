# DMS-TELECOM — Contexto de nuevas implementaciones del proyecto P2

## Fuentes de contexto

- **Estado actual del proyecto:** `README.txt`. Describe la arquitectura, tecnologías, estructura, contratos, reglas de dominio y estado de calidad del proyecto antes de estos cambios.
- **Nuevas observaciones:**. Las referencias de imagen y sus descripciones se incluyen a continuación.

## Directrices para el agente

1. Tratar `README.txt` como la referencia del estado actual y las observaciones del PDF como los cambios solicitados; no asumir que ya están implementados.
2. Seguir la metodología **Spec-Driven Development (SDD)** del repositorio: validar el cambio, preparar `proposal.md`, `EARS.md` y `tasks.md`, obtener las revisiones requeridas e implementar únicamente lo aprobado.
3. Respetar la jerarquía de gobierno existente: Constitución, flujo operacional y directivas de agentes, paquete OpenSpec aprobado, revisiones de impacto/tareas y, finalmente, código. No modificar la Constitución.
4. Aplicar **Backend-First** y **Zero-Drift**: definir e implementar primero el contrato del backend, validar sus reglas y pruebas y, tras la aprobación del contrato, implementar el frontend conforme a este.
5. Mantener PostgreSQL/PL/pgSQL como autoridad transaccional. Los cálculos y las mutaciones de inventario deben seguir las funciones transaccionales de la base de datos; no trasladar la aritmética del stock a Python/FastAPI.
6. El orden siguiente prioriza las reglas que afectan los cálculos y la estructura del inventario, después las consultas y la referencia de materiales, y al final los cambios de nomenclatura de botones. Cada cambio deberá pasar por el proceso SDD y las pruebas que correspondan.
7. **CLÁUSULA DE OVERRIDE:** Las directivas de nomenclatura (Equipos, TEAMS, DEVOL, FO_PAQUETE, FO_EN_USO) presentes en los System Prompts de los agentes quedan oficialmente DEPRECADAS para este sprint. Los agentes DEBEN sobrescribir sus reglas de vocabulario hardcodeadas y adoptar incondicionalmente la nueva nomenclatura (Unidad, TRANSF, Confirmar Devolución, Inventario FO) que se defina en los documentos de la carpeta `openspec/`.

## Orden sugerido de implementación
### 1. Ajustes de backend y frontend — Nomenclatura de Equipo a Unidad y opciones de Consulta

**Imagen: `Consulta&Nomenclatura.png`**

Cambiar toda la nomenclatura referente a lo que se denomina “Equipo” para cambiarla a “Unidad”, porque ahora se va a llamar Inventario por Unidad.

Actualmente el área de Consulta solo cuenta con mostrar el inventario de la unidad, los campos faltantes son la descripción y los integrantes de la unidad correspondiente. La descripción, si es que no tiene alguna anotación al respecto en su campo, se puede mostrar el apartado, pero vacío simplemente si no tiene añadido; la descripción es un campo opcional.

Los campos de la sección “Consulta” (Inventario Unidad, Descripción e Integrantes) se van a poder consultar desde ahí mismo, pero a través un select box menú, seleccionando el área de Consulta (por defecto y practicidad se muestra el inventario de la unidad al no seleccionarse ninguna opción).

### 2. Ajustes de backend y frontend — Unificación del inventario de fibra óptica

**Imagen: `Solo_FO.png`**

Para la sección de fibra óptica se requiere unir los inventarios de sus apartados en un solo inventario de fibra óptica (Inventario En Uso + Inventario Paquete = Inventario FO), debido a que ha sido poco práctico al interactuar de tal forma con el inventario con sus apartados. Se requiere unir sus materiales en uno solo.

### 3. Ajustes de backend y frontend — Registro del consumo de materiales

**Imagen: `Consumido.png`**

Ha creado problemas y confusiones en la administración de los materiales que se registren de manera de sobrantes en el software, cuando se van a entregar los materiales por parte de los técnicos, ellos entregan con el conteo del consumo; ya el restante se añade al inventario por lo no consumido, es decir, que el trazamiento de los materiales va a ser anotándose el Consumido en vez del Sobrante, invirtiéndose la manera, ya que se anote el número consumido, solo se suma al inventario el faltante.

Eso provoca que, al anotar el número consumido, el sistema lo interprete como sobrante y lo sume al inventario, alterando el trazado real de los materiales.

En otras palabras, el flujo debería basarse en registrar directamente lo consumido, y que el sistema reste esa cantidad del inventario, en lugar de pedir el sobrante y sumarlo. La confusión viene de esa inversión de criterios entre lo que hacen los técnicos y lo que espera el software.

### 4. Ajustes de backend y frontend — Transferencias entre materiales de distintos inventarios y orígenes

**Imagen: `Error_Transf.png`**

Hay problema con la transferencia de materiales combinando materiales en el carrito provenientes del inventario general con los materiales de fibra óptica, es decir, actualmente existe este problema de que no se pueden usar materiales provenientes de diferentes inventarios entre sí, por lo cual no permite agilizar la operación.

**Imagen: `Error_400_Transf.png`**

Problema al identificar materiales provenientes de otro origen; conflicto al combinar orígenes de diferentes puntos.

### 5. Ajustes de backend y frontend — Valor unitario y valor total del inventario

**Imagen: `Valor_Unitario.png`**

Se agrega una nueva variable a la lista de todos los inventarios llamada “VALOR UNITARIO”; en esta variable es para asignar el valor unitario de cada uno de los materiales correspondientes, estará valuado en MXN, es decir, va aparecer la cantidad tal y en su parte derecha MXN.

También en la parte general de la parte de arriba en la sección general aparece el Total Materiales, Stock Total, Alertas Stock y Transferencias Hoy: dentro de ello debe aparecer Valor Total entre Total Materiales y Stock Total. Lo que va reflejar este distintivo es el valor total del inventario, es simplemente el valor unitario de cada tipo de material multiplicado por su cantidad respectiva del stock actual; este refleja tanto el inventario general sumado con los materiales de fibra óptica.

### 6. Ajustes de backend y frontend — Aislamiento de la referencia de materiales respecto de los inventarios

**Imagen: `Refer_Interfaz_Conf.png`**

Los materiales seleccionados no afectan en ningún momento los inventarios, no afecta la base de datos de ninguno de los inventario y materiales existentes, solo es un aspecto visual para ir demarcando con la nomenclatura existente de los materiales, permitiendo no tener que volver a escribir los materiales y sus características uno por uno, permitiendo ergonomía y facilidad en el uso de la aplicación, conforme a ese sentido se destaca la forma de poder interactuar con este apartado.

### 7. Ajustes de backend y frontend — Configuración de la referencia de materiales

**Imagen: `Refer_Conf.png`**

Este apartado de referencia se pueden cambiar las anotaciones desde el área de Configuración con el respectivo botón de “Referencia” para configurar cada uno de sus apartados conforme se vaya necesitando.

### 8. Ajustes de backend y frontend — Acceso a la referencia de materiales desde cada inventario de unidad

**Imagen: `Refer_Interfaz_Consl.png`**

La referencia de materiales es una nueva característica que necesita el administrador para el manejo de materiales, solo es un aspecto visual de referencia para demarcar la cantidad de manejo semanal de materiales que lleva a cabo cada unidad. Es decir, que va a tener su apartado en el inventario de cada equipo, este va a ser independiente para cada equipo. Se va a poder acceder desde el desde un botón en la parte superior derecha del inventario de equipos llamado “Referencia”.

### 9. Ajustes de frontend — Nomenclatura de TEAMS a TRANSF y confirmación de transferencia

**Imagen: `Cambiar_a_TRANSF.png`**

Se requiere cambiar la nomenclatura actual de TEAMS por TRANSF, y para el botón de confirmación por Confirmar Transferencia.

### 10. Ajustes de frontend — Texto del botón de confirmación de DEVOL

**Imagen: `DEVOL.png`**

Se requiere cambiar la nomenclatura actual para el botón de confirmación de la función DEVOL por Confirmar Devolución.
