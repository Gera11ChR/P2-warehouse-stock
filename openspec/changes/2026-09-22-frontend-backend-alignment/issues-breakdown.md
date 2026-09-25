---

# 1. El concepto de "ID LISTA" se volvió innecesario

Lo primero que detectaste es que el sistema actualmente conserva un identificador llamado **ID LISTA**, pero en la práctica ya existen otros identificadores más útiles dentro del dominio. 

Tu observación no es simplemente:

> "No me gusta el ID LISTA"

Lo que realmente estás diciendo es:

> "Ya tenemos identificadores reales para trabajar. Mantener otro identificador fijo solo agrega complejidad."

Actualmente el sistema fue diseñado bajo la idea de:

```text
ID LISTA
=
Identificador permanente
=
No renumerable
```

Pero durante las pruebas descubriste que el operador realmente trabaja con:

```text
Descripción
SKU
Categoría
Inventario
```

y no con un número interno fijo.

Por eso propones que:

```text
ID LISTA
↓
Número de listado visual
```

simplemente para ordenar registros.

Lo que buscas es:

```text
1
2
3
4
5
...
```

como una numeración dinámica de tabla.

No buscas:

```text
ID 53
ID 54
ID 55
```

persistidos para siempre.

Por eso solicitas eliminar completamente la relevancia funcional del ID LISTA. 

---

# 2. Eliminar un material no lo elimina realmente del inventario

Este es probablemente el problema más grave encontrado.

Tu flujo fue:

```text
Crear material
↓
Aparece correctamente
↓
Eliminar material
↓
Sigue apareciendo
```



Lo que observaste es que el sistema aparentemente realiza una especie de:

```text
Soft Delete
```

o una desactivación.

Pero la interfaz sigue mostrando el material.

El resultado práctico es muy malo porque genera un estado inconsistente:

```text
Material visible
+
Material no editable
+
Material no utilizable
```

Lo cual provoca que el usuario vea algo que ya no puede gestionar.

Desde la perspectiva del operador esto se percibe como:

```text
"Está ahí pero no sirve."
```

Por eso escribiste:

> "Es mejor que desaparezca." 

Lo que buscas no es mantener un historial visual.

Quieres:

```text
Eliminar
↓
Desaparece
```

Porque para la operación diaria ese historial no aporta valor.

---

# 3. El inventario general quedó demasiado rígido

Aquí encontraste un conflicto entre diseño y operación real.

Actualmente:

```text
Descripción
✓ editable

Categoría
✓ editable

SKU
✗ bloqueado

Stock Actual
✗ bloqueado
```



Lo que descubriste durante el uso es que la empresa necesita flexibilidad.

Tu necesidad real es:

```text
Modificar descripción
Modificar categoría
Modificar SKU
Modificar stock
```

desde el inventario general.

No quieres que esos campos estén protegidos.

Porque en la operación cotidiana:

* pueden corregirse códigos;
* pueden existir errores de captura;
* pueden existir ajustes administrativos.

Por eso percibes que el sistema actual es demasiado restrictivo para la realidad de la empresa. 

---

# 4. La numeración comienza en 10 y no en 1

Aquí detectaste una consecuencia directa del modelo persistente.

El sistema está mostrando algo parecido a:

```text
10
11
12
13
14
...
```

en lugar de:

```text
1
2
3
4
5
...
```



Eso normalmente ocurre porque:

```text
ID real de base de datos
=
contador acumulado
```

y anteriormente existieron registros eliminados.

Pero como ya decidiste que:

```text
ID LISTA
no aporta valor
```

entonces tampoco tiene sentido mostrar esos saltos.

Lo que realmente quieres es:

```text
Número de fila visual
```

y no:

```text
ID histórico de la base de datos
```

---

# 5. El modelo "Sparse" de equipos no coincide con la operación real

Este es probablemente el hallazgo arquitectónico más importante de todo el PDF.

Originalmente se había construido la lógica bajo la idea:

```text
Catálogo Maestro
↓
53 materiales
↓
Todos los equipos ven esos 53 materiales
```

Modelo sparse.

Pero al probar la aplicación descubriste que la empresa trabaja diferente. 

Tu razonamiento fue:

```text
Hay pocos equipos
(aprox. 5)
```

y además:

```text
Ningún equipo utiliza todos los materiales
```

Entonces te preguntaste:

```text
¿Por qué obligar a cada equipo a cargar un catálogo completo?
```

La respuesta operativa fue:

> No tiene sentido.

Por eso cambiaste la visión del sistema.

Antes:

```text
Equipo
↓
Vista derivada del inventario general
```

Ahora:

```text
Equipo
↓
Inventario propio
```



Ese cambio es enorme.

Porque modifica completamente el modelo mental del sistema.

---

# 6. Fibra Óptica también debe tener inventarios independientes

Aquí detectaste exactamente el mismo problema que en Equipos.

La implementación actual intentaba tratar:

```text
FO Paquete
FO En Uso
```

como casos especiales ligados a:

```text
Carretes
Metros
```



Pero durante la prueba encontraste que eso agrega complejidad innecesaria.

Tu nueva visión es:

```text
FO Paquete
=
Inventario propio

FO En Uso
=
Inventario propio
```

y la unidad de medida resolverá las diferencias.

Por ejemplo:

```text
PZ
M
ROLLO
CARRETE
```

se controlan mediante:

```text
UM
```

sin necesidad de lógica especial.

---

# 7. Todos los equipos deben nacer con inventario propio

Este punto complementa el anterior.

Tu conclusión fue:

```text
Crear Equipo
↓
Crear Inventario del Equipo
```

automáticamente.



Porque actualmente existe una dependencia incómoda:

```text
Equipo
↓
esperar movimientos
↓
inventario aparece
```

Tú quieres:

```text
Equipo creado
=
Inventario listo
```

desde el primer momento.

---

# 8. La descripción es mucho más útil que el ID LISTA

Este problema es puramente de usabilidad.

Descubriste que el administrador nunca piensa:

```text
Material 48
```

Piensa:

```text
Conector SC/APC
Cable Drop
Herraje X
```

Por eso propones:

```text
Quitar ID LISTA
↓
Mostrar Descripción
```

como referencia principal.



Es una mejora enfocada en productividad operativa.

---

# 9. El buscador masivo quedó incompleto

El diseño original contemplaba:

```text
Desde SKU
Hasta SKU
```

Pero al probarlo detectaste que también hace falta:

```text
Desde descripción
Hasta descripción
```



porque muchas veces el operador recuerda:

```text
el nombre
```

y no:

```text
el SKU
```

---

# 10. Las categorías no se están guardando

Este es el otro problema crítico.

Durante la prueba observaste:

```text
Crear categoría
↓
Guardar material
↓
Editar material
↓
Categoría desaparece
```



La consecuencia es muy grave.

Porque entonces:

```text
Filtros por categoría
=
vacíos
```

aunque aparentemente existan categorías.

Tu diagnóstico es correcto:

Si la categoría no se persiste:

```text
No existe clasificación real.
```

Y si no existe clasificación real:

```text
Buscar por categoría
=
imposible
```



---

# Resumen global

Después de leer todo el PDF, los hallazgos pueden resumirse en tres grandes grupos:

### A. Problemas de Persistencia

El sistema no está guardando o eliminando correctamente ciertos datos:

```text
Categorías no persisten.
Materiales eliminados siguen apareciendo.
```

 

---

### B. Problemas de Modelo de Dominio

Las decisiones arquitectónicas originales no coinciden completamente con la operación real:

```text
ID LISTA no aporta valor.
Modelo sparse de equipos no resulta útil.
FO necesita inventarios propios.
```

 

---

### C. Problemas de Usabilidad Operativa

La aplicación funciona, pero no de la forma más cómoda para quien la usa diariamente:

```text
No editar SKU.
No editar Stock.
No buscar por descripción.
Numeración poco intuitiva.
Descripción más útil que ID LISTA.
```