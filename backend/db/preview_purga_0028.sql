-- Vista previa de SOLO LECTURA de la purga 0028 (plan §1.3 / tasks T2).
-- Equivalente EXACTO de los predicados de la migración
-- alembic/versions/0028_purga_legacy_fo.py. No crea objetos, no escribe.
--
-- Uso (la sesión queda en solo lectura aunque el script falle):
--   psql "$URL" -v ON_ERROR_STOP=1 -c "BEGIN READ ONLY" -f db/preview_purga_0028.sql
-- (o ejecutarlo con cualquier cliente dentro de una transacción READ ONLY).
-- Salida: filas (seccion, metrica, n). Las métricas "eventos_..." solapan entre
-- criterios; "eventos_a_eliminar_UNION" es el total deduplicado.
-- Contraste con el resultado de la migración: el evento PURGA_LEGACY_FO
-- (detalles.eliminados_por_tabla / eliminados_por_tipo_accion).

WITH
secc AS (
  SELECT almacen_id FROM secciones WHERE tipo IN ('FO_PAQUETE','FO_EN_USO')
),
mov AS (
  SELECT id FROM movimientos_cabecera
   WHERE origen_almacen_id  IN (SELECT almacen_id FROM secc)
      OR destino_almacen_id IN (SELECT almacen_id FROM secc)
  UNION
  SELECT movimiento_id FROM movimientos_detalle
   WHERE origen_almacen_id IN (SELECT almacen_id FROM secc)
),
acta AS (
  SELECT id FROM actas_reportes WHERE movimiento_id IN (SELECT id FROM mov)
),
ev AS (
  SELECT e.id, e.tipo_accion,
         COALESCE(e.almacen_origen_id IN (SELECT almacen_id FROM secc)
               OR e.almacen_destino_id IN (SELECT almacen_id FROM secc), FALSE) AS c_a,
         COALESCE(e.detalles::jsonb @? '$.**.modulo ? (@ == "PAQUETE" || @ == "EN_USO")'
               OR e.detalles::jsonb @? '$.**.origen_modulo ? (@ == "PAQUETE" || @ == "EN_USO")'
               OR e.detalles::jsonb @? '$.**.destino_modulo ? (@ == "PAQUETE" || @ == "EN_USO")', FALSE) AS c_b,
         (e.tipo_accion = 'FO_UNIFICADO') AS c_c,
         COALESCE((e.detalles::jsonb ->> 'movimiento_id') IN (SELECT id::text FROM mov)
               OR (e.detalles::jsonb ->> 'acta_id')       IN (SELECT id::text FROM acta), FALSE) AS c_d
    FROM auditoria_eventos e
),
ev_del AS (SELECT * FROM ev WHERE c_a OR c_b OR c_c OR c_d),
ev_cons AS (
  SELECT e.* FROM auditoria_eventos e
   WHERE e.id NOT IN (SELECT id FROM ev_del)
),
-- 12(d2): barrido diagnóstico no circular sobre las filas que SOBREVIVIRÍAN.
d2 AS (
  SELECT 'auditoria_eventos.detalles' AS fuente, count(*) AS n
    FROM ev_cons
   WHERE detalles::text LIKE '%FO\_PAQUETE%' OR detalles::text LIKE '%FO\_EN\_USO%'
  UNION ALL
  SELECT 'actas_reportes.snapshot', count(*) FROM actas_reportes
   WHERE id NOT IN (SELECT id FROM acta)
     AND (snapshot::text LIKE '%FO\_PAQUETE%' OR snapshot::text LIKE '%FO\_EN\_USO%')
  UNION ALL
  SELECT 'operaciones_idempotencia.resultado', count(*) FROM operaciones_idempotencia
   WHERE NOT (COALESCE(resultado @? '$.modulo ? (@ == "PAQUETE" || @ == "EN_USO")', FALSE)
           OR COALESCE(resultado ->> 'movimiento_id' IN (SELECT id::text FROM mov), FALSE))
     AND (resultado::text LIKE '%FO\_PAQUETE%' OR resultado::text LIKE '%FO\_EN\_USO%')
  UNION ALL
  SELECT 'claves_almacen_id_a_seccion_purgada (detalles supervivientes)', count(*)
    FROM ev_cons e, secc s, (VALUES ('almacen_id'),('origen_almacen_id'),('destino_almacen_id')) k(clave)
   WHERE jsonb_path_exists(e.detalles::jsonb,
           format('$.**.%s ? (@ == $id || @ == $ids)', k.clave)::jsonpath,
           jsonb_build_object('id', s.almacen_id, 'ids', s.almacen_id::text))
)
SELECT 1 AS orden, 'secciones' AS seccion, 'legacy' AS metrica, count(*)::bigint AS n FROM secc
UNION ALL SELECT 2, 'movimientos_cabecera', 'a_eliminar_total', count(*) FROM mov
UNION ALL SELECT 3, 'movimientos_cabecera', 'a_eliminar_' || m.estado, count(*)
          FROM movimientos_cabecera m WHERE m.id IN (SELECT id FROM mov) GROUP BY m.estado
UNION ALL SELECT 4, 'movimientos_cabecera', 'mixtos (con alguna linea no legacy)', count(DISTINCT d.movimiento_id)
          FROM movimientos_detalle d WHERE d.movimiento_id IN (SELECT id FROM mov)
           AND (d.origen_almacen_id IS NULL OR d.origen_almacen_id NOT IN (SELECT almacen_id FROM secc))
UNION ALL SELECT 5, 'movimientos_detalle', 'a_eliminar', count(*)
          FROM movimientos_detalle WHERE movimiento_id IN (SELECT id FROM mov)
UNION ALL SELECT 6, 'actas_reportes', 'a_eliminar', count(*) FROM acta
UNION ALL SELECT 7, 'actor_almacen_scopes', 'a_eliminar', count(*)
          FROM actor_almacen_scopes WHERE almacen_id IN (SELECT almacen_id FROM secc)
UNION ALL SELECT 8, 'operaciones_idempotencia', 'a_eliminar', count(*)
          FROM operaciones_idempotencia
          WHERE COALESCE(resultado @? '$.modulo ? (@ == "PAQUETE" || @ == "EN_USO")', FALSE)
             OR COALESCE(resultado ->> 'movimiento_id' IN (SELECT id::text FROM mov), FALSE)
UNION ALL SELECT 9, 'inventario_equipos', 'ultimo_movimiento_id_a_NULL', count(*)
          FROM inventario_equipos WHERE ultimo_movimiento_id IN (SELECT id FROM mov)
UNION ALL SELECT 10, 'inventario_almacen', 'filas_con_seccion_legacy (debe ser 0: guardia de saldos)', count(*)
          FROM inventario_almacen WHERE almacen_id IN (SELECT almacen_id FROM secc)
UNION ALL SELECT 11, 'auditoria_eventos', 'total_actual', count(*) FROM auditoria_eventos
UNION ALL SELECT 12, 'auditoria_eventos', 'criterio_a_columnas', count(*) FROM ev WHERE c_a
UNION ALL SELECT 13, 'auditoria_eventos', 'criterio_b_json_modulo', count(*) FROM ev WHERE c_b
UNION ALL SELECT 14, 'auditoria_eventos', 'criterio_c_FO_UNIFICADO', count(*) FROM ev WHERE c_c
UNION ALL SELECT 15, 'auditoria_eventos', 'criterio_d_movimiento_acta_id', count(*) FROM ev WHERE c_d
UNION ALL SELECT 16, 'auditoria_eventos', 'eventos_a_eliminar_UNION', count(*) FROM ev_del
UNION ALL SELECT 17, 'auditoria_eventos', 'eventos_conservados', count(*) FROM ev_cons
UNION ALL SELECT 18, 'auditoria_eventos', 'eliminados_tipo_accion=' || tipo_accion, count(*)
          FROM ev_del GROUP BY tipo_accion
UNION ALL SELECT 19, 'auditoria_eventos', 'conservados_MATERIAL_MODIFICADO_con_unidad_PAQUETE_100PZ', count(*)
          FROM ev_cons WHERE tipo_accion = 'MATERIAL_MODIFICADO' AND detalles::text LIKE '%PAQUETE (100 PZ)%'
UNION ALL SELECT 20, 'diagnostico_d2 (debe ser 0)', fuente, n FROM d2
UNION ALL SELECT 21, 'auditoria_eventos', 'conservados_tipo_accion=' || tipo_accion, count(*)
          FROM ev_cons WHERE tipo_accion LIKE 'DESPLIEGUE\_%' OR tipo_accion LIKE 'UM\_%' OR tipo_accion = 'MATERIAL_MODIFICADO' GROUP BY tipo_accion
ORDER BY 1, 3;
