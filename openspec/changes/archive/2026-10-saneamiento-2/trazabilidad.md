# Trazabilidad: 2026-10-saneamiento-2

Matriz RF → implementación → prueba (6/6 RF).

| RF | Implementación | Pruebas / verificación |
| :-- | :-- | :-- |
| RF-1 Gobernanza y docs | `.agents.md` (líneas 33 y 670 sin `FO_PAQUETE`/`FO_EN_USO`; fila de tabla §3 conservada), `git rm docs/1 Changes.docx`, `README.md` (head 0028, 28 migraciones, conteos medidos, FO unificado, historial), `backend/db/ddl.sql` + `backend/scripts/generar_ddl.py` | `grep` de residuos = 0; `uv run python scripts/generar_ddl.py --verificar` → «OK: ddl.sql coincide con el esquema 0028»; cifras del README = última corrida de compuertas |
| RF-2 IDs INT4 → 400 | `app/main.py` (`dbapi_error_handler`, predicado exclusivo `orig.sqlstate == '22003'`, mensaje fijo) | `tests/test_robustez_ids.py` (31: 8 rutas GET con `10**12`/`10**30`, POST/PATCH, sin fuga de detalles, sesión sana después, `23505` conserva 409, otros SQLSTATE se relanzan) |
| RF-3 `X-Actor` | `app/security.py` (`ActorHeader`: 1..100, sin controles C0/DEL/C1, al menos un no blanco, con `description`); `openspec.yaml › domain_rules.actor_header` | `tests/test_actor_header.py` (26: 101 chars, vacío, solo espacios, `\t` por HTTP, LF/NUL por dependencia directa, 100 chars y nombres con espacios/acentos válidos, el rechazo no abre sesión, con control positivo de que un actor válido sí la abre) |
| RF-4 Poda | Backend: `api/v1/catalog.py`, `services/catalogo.py` (4 filtros). Frontend: `Sidebar.tsx` (`children`), `utils/formatMxn.ts`, `utils/cantidad.ts`, `services/catalog.ts`, `types.ts` (`ActaItem`) | `test_catalogo.py::test_filtros_eliminados_son_ignorados` (E6); vitest 529; `grep` de los nombres eliminados = 0 en `backend/app` y `frontend/src` |
| RF-5 `EXITO` | Sin cambio de código (ya vigente); guardián | `tests/test_convencion_resultado.py` (8: 18 funciones que insertan en `auditoria_eventos`, `DEFAULT` de la columna NULL, barrido de `backend/app`, `DISTINCT resultado = {'EXITO'}` tras un flujo por API) |
| RF-6 No regresión | — | pytest 519, `sql_tests` 25, mypy 0/88, `tsc -b`, eslint, vitest 529, `vite build` sin advertencias, `openspec validate --specs --strict` 3/3 |

## Congelación Contractual
Diff de OpenAPI contra el baseline previo a T3: solo (a) los 4 query params eliminados de `GET /api/v1/catalogo` y (b) `minLength`/`maxLength`/`pattern`/`description` del header `X-Actor`. `components` sin cambios.

## Desviaciones y correcciones registradas
- El patrón prescrito con `\S` dejaba pasar NUL/DEL/C1; se usa la clase negada `[^\s<controles>]` (T3).
- Corrección al briefing: el commit de `.agents.md` §5 ya existía (`69bca35`); la «nota de §3» nunca se añadió (se retiraron las menciones deprecadas); hay 28 migraciones; `'OK'`/`'EXITO'` ya estaba unificado; `ActaItem` carecía de (no contenía de más) `origen_*`; los filtros eran 4; el rechazo de IDs gigantes es del servidor PostgreSQL.
- `X-Actor` sigue sin autenticar: **desviación conocida de la Constitución §3.1/§3.3, reconocida por el humano** (no es cumplimiento ni una dispensa §8.2).

## Dispensas formales de pruebas (consolidadas)
| Dispensa | Justificación | Evidencia alternativa |
| :-- | :-- | :-- |
| 12(c) stock (verificación interna de `0028`) | Aserción de defensa en profundidad dentro de la transacción; no se puede disparar desde fuera sin corromper el estado | `test_migracion_0028.py::test_RF_001_003_purga_conserva_dominio_vivo_y_ledger_no_legacy` compara stock fila a fila antes/después |
| 12(d) md5 de eventos conservados | Ídem | La misma prueba compara `id` y md5 de los eventos conservados |
| E12 guardia E-1 en otra base | El rol QA no posee `CREATEDB`; no se puede crear otra base | `test_RF_006_guardia_e1_aborta_fuera_de_p2_y_p2_test` (unidad sobre la guardia, con nombre de base y con conexión real) |
| E9 reintento tras fallo | La infraestructura restaura la cabeza con `upgrade head` tras cada aborto, lo que re-ejecuta `0028` con éxito | `test_RF_006_abortos_con_rollback_total` (rollback verificado) + restauración por `esquema_en` |

## Destrucción de respaldos (D-7)
Registrada en `tasks.md` T7 (qué se destruyó, no su contenido). Tras ella la purga de `p2` es irrecuperable; `shred` es de mejor esfuerzo en sistemas de archivos con journaling/CoW.
