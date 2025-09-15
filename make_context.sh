#!/usr/bin/env bash
set -euo pipefail

OUT_DIR="context"
mkdir -p "$OUT_DIR"

# 1. Exportar estructura de BD en Markdown (sin datos)
echo "# Database Structure" > "$OUT_DIR/STRUCTURE.md"
echo '```sql' >> "$OUT_DIR/STRUCTURE.md"

pg_dump --schema-only --no-owner --no-privileges \
  -h localhost -p 5432 -U postgres -d residences \
  >> "$OUT_DIR/STRUCTURE.md"

echo '```' >> "$OUT_DIR/STRUCTURE.md"

# 2. Añadir reglas de roles (texto fijo)
cat >> "$OUT_DIR/STRUCTURE.md" <<'EOF'

# Roles y permisos

- **Superadmin**: puede hacer todo, crear residencias, gestores, profesionales, dispositivos, etc.
- **Gestor**: asignado a n residencias, puede crear otros gestores dentro de esas residencias, crear categorías/tareas, dar de alta residentes, asignar camas.
- **Profesional**: asignado a una o varias residencias, puede tomar mediciones y aplicar tareas. Solo puede borrar/editar sus propias mediciones/tareas.
- **Residente**: tiene estado (`active | discharged | deceased`), solo puede ocupar una cama activa, con histórico de cambios.

# Políticas importantes
- Login con `alias` + `password` (alias cifrado + hash).
- Selección de residencia obligatoria para gestor/profesional si tienen varias.
- Dispositivos: vinculados a residencia, MAC única global. 
- Tags: solo los crean/gestionan gestores o superadmin, globales en el sistema.
EOF

# 3. Concatenar todo el código Python en un TXT único
echo "# Backend Code Dump" > "$OUT_DIR/BACKEND_CODE.txt"
find app -type f -name "*.py" -print0 | xargs -0 cat >> "$OUT_DIR/BACKEND_CODE.txt"
cat main.py >> "$OUT_DIR/BACKEND_CODE.txt" || true
cat requirements.txt >> "$OUT_DIR/BACKEND_CODE.txt" || true
cat pyproject.toml >> "$OUT_DIR/BACKEND_CODE.txt" || true
