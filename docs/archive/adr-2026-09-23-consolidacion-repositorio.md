# ADR — Consolidación de repositorios en la raíz `P2`

**Fecha:** 2026-09-23
**Estado:** Registro histórico (no normativo — no modifica `docs/constitution.md` ni crea reglas)

## Repositorios involucrados

| Repositorio | Raíz Git | Rama tras la migración | HEAD |
|---|---|---|---|
| Padre | `~/P2` | `refactor/monorepo-consolidation` | `bcbb9d3` |
| Hijo | `~/P2/P2-warehouse-stock` | `main` (conservado) | `bcbb9d3` |
| Padre (respaldo) | `~/P2` | `main`, `backup/pre-final-merge` | `2ba44b4` (clavadas) |
| Hijo (respaldo) | `~/P2/P2-warehouse-stock` | `backup/pre-merge` | `597460d` |

## Estrategia seleccionada

`git fetch` local del hijo + `git merge --ff-only` sobre `refactor/monorepo-consolidation`.

## Alternativas consideradas

1. **`git merge --allow-unrelated-histories`** — descartada: los historiales **no** son independientes (`2ba44b4` del padre es el commit raíz del hijo). Habría creado un merge-commit artificial sin aportar trazabilidad.
2. **`git subtree`** — descartada: exige prefijos de ruta y reescribe/duplica el historial, rompiendo `git log --follow` y `git blame`; el layout del hijo ya coincide con la estructura final, por lo que no hay rutas que remapear.

## Motivo técnico

- `HEAD_padre (2ba44b4) == commit raíz del hijo`: el DAG del hijo es una extensión lineal estricta del padre.
- Un fast-forward cierra el DAG sin reescritura: todos los SHAs del hijo permanecen idénticos en el padre.
- El árbol del hijo ya tenía la forma de la estructura final (`backend/`, `frontend/`, `openspec/`, `docs/`, `.opencode/`): cero movimientos de rutas.
- El WIP sin commitear de cada repo se preservó: en el hijo mediante commits propios (`da13548`, `bcbb9d3`), en el padre mediante stash retenido + reubicación del borrador OpenSpec en `openspec/changes/2026-09-22-frontend-backend-alignment/`.

## Impacto

- **Historial:** DAG lineal único `2ba44b4 → … → 597460d → da13548 → bcbb9d3`. Ambos historiales permanecen accesibles; el estado anterior del padre queda clavado en `main` y `backup/pre-final-merge`.
- **Estructura:** `backend/`, `frontend/`, `openspec/`, `docs/`, `.opencode/` en la raíz `~/P2`; el directorio original del hijo se aísla en `~/P2-warehouse-stock-PRE-MERGE` (no destructivo).
- **SDD:** `docs/constitution.md` intacto (idéntico byte a byte en ambos repos); gobernanza `openspec/` preservada; 11 agentes de la versión del hijo consolidados en `.opencode/agents/`.

## Riesgos conocidos

- `backend/.env` (ignorado por git) se copió manualmente; no se versiona.
- El entorno virtual del backend del padre (Python 3.12) debe recrearse contra `backend/pyproject.toml` (>=3.12).
- La rama `origin/main` local del padre estaba obsoleta (`2ba44b4`); el remoto real quedó en `597460d` (hijo) y no se forzó ningún push.

## Validaciones realizadas

Ver historial de la migración: `git log --graph --oneline --decorate --all`,
`git log --follow -- backend/app/api/v1/auditoria.py`, suite `pytest` del backend,
`npm run build/test/lint` del frontend, y verificación de integridad de `openspec/` y `docs/constitution.md`.
