# 🏥 Sistema de Gestión de Residencias - Backend

Backend limpio y profesional para el sistema de gestión de residencias. Completamente reorganizado y optimizado para producción.

## ✨ Características

- **Arquitectura limpia**: Modelos consolidados, código organizado
- **Base de datos PostgreSQL**: Con enums nativos y índices optimizados  
- **Autenticación JWT**: Sistema seguro de roles y permisos
- **API REST**: Endpoints bien estructurados con FastAPI
- **Soft Delete**: Eliminación lógica para auditoría
- **Encriptación**: Datos sensibles protegidos
- **Logging**: Sistema completo de auditoría

## 🚀 Inicio Rápido

### 1. Configuración del Entorno

```bash
# Crear entorno virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
# o
venv\Scripts\activate     # Windows

# Instalar dependencias
pip install -r requirements.txt
```

### 2. Configuración de Base de Datos

Crear archivo `.env` con:

```env
DATABASE_URL=postgresql+asyncpg://usuario:contraseña@localhost:5432/residences
SECRET_KEY=tu_clave_secreta_muy_larga_y_segura
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

### 3. Inicializar Base de Datos

```bash
# Crear todas las tablas desde cero
python init_database.py

# Poblar con datos de prueba
python seeds.py                # Datos de desarrollo
python seeds.py --minimal      # Solo datos mínimos
python seeds.py --full         # Datos completos con volumen
python seeds.py --clear        # Limpiar antes de crear
```

### 4. Ejecutar Servidor

```bash
uvicorn main:app --reload
```

La API estará disponible en: `http://localhost:8000`
Documentación Swagger: `http://localhost:8000/docs`

## 🏗️ Estructura del Proyecto

```
back-residence/
├── app/
│   ├── models.py           # Todos los modelos consolidados
│   ├── config.py           # Configuración de la aplicación
│   ├── db.py               # Configuración de base de datos
│   ├── security.py         # Autenticación y seguridad
│   ├── deps.py             # Dependencias de FastAPI
│   ├── exceptions.py       # Excepciones personalizadas
│   ├── middlewares.py      # Middlewares personalizados
│   ├── routers/            # Endpoints de la API
│   ├── schemas/            # Esquemas Pydantic
│   └── services/           # Lógica de negocio
├── init_database.py        # Script de inicialización de BD
├── seeds.py               # Script de datos de prueba
├── main.py                # Punto de entrada de la aplicación
└── requirements.txt       # Dependencias Python
```

## 📊 Modelos de Datos

### Entidades Principales

- **User**: Usuarios del sistema (superadmin, manager, professional)
- **Residence**: Residencias donde viven los residentes
- **Floor/Room/Bed**: Estructura jerárquica de ubicaciones
- **Resident**: Personas que viven en las residencias
- **Device**: Dispositivos médicos para mediciones
- **Measurement**: Mediciones médicas de los residentes
- **Task**: Sistema de tareas y categorías
- **Tag**: Etiquetas para categorizar residentes
- **EventLog**: Registro de auditoría del sistema

### Características de los Modelos

- **UUIDs**: Identificadores únicos seguros
- **Timestamps**: Auditoría completa (created_at, updated_at)
- **Soft Delete**: Eliminación lógica con deleted_at
- **Encriptación**: Datos sensibles encriptados
- **Relaciones**: Foreign keys con integridad referencial
- **Enums**: Tipos nativos de PostgreSQL

## 🔐 Sistema de Autenticación

### Roles de Usuario

- **superadmin**: Acceso completo a todo el sistema
- **manager**: Gestión de residencias asignadas
- **professional**: Acceso operativo a residencias asignadas

### Endpoints de Autenticación

```bash
POST /auth/login          # Iniciar sesión
POST /auth/refresh        # Renovar token
POST /auth/logout         # Cerrar sesión
```

### Credenciales por Defecto

```
Superadmin: admin / admin123
Gestores: manager1, manager2, ... / manager123  
Profesionales: prof1, prof2, ... / prof123
```

## 📡 API Endpoints

### Principales Grupos

- `/auth/*` - Autenticación y autorización
- `/residences/*` - Gestión de residencias
- `/residents/*` - Gestión de residentes  
- `/structure/*` - Pisos, habitaciones, camas
- `/devices/*` - Dispositivos médicos
- `/measurements/*` - Mediciones médicas
- `/tasks/*` - Sistema de tareas
- `/tags/*` - Etiquetas de residentes
- `/dashboard/*` - Estadísticas y reportes

## 🛠️ Comandos Útiles

### Base de Datos

```bash
# Reinicializar completamente
python init_database.py

# Poblar con datos específicos
python seeds.py --minimal           # Datos mínimos
python seeds.py                     # Datos de desarrollo  
python seeds.py --full              # Datos completos
python seeds.py --clear --full      # Limpiar y crear datos completos
```

### Desarrollo

```bash
# Servidor con recarga automática
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Verificar sintaxis
python -m py_compile app/models.py

# Verificar importaciones
python -c "from app.models import *; print('✅ Modelos importados correctamente')"
```

## 🔧 Configuración de Producción

### Variables de Entorno

```env
# Base de datos
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db

# Seguridad
SECRET_KEY=clave_super_secreta_de_al_menos_32_caracteres
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Aplicación
DEBUG=false
ENVIRONMENT=production
```

### Optimizaciones

- Índices de base de datos automáticos
- Pool de conexiones configurado
- Middleware de compresión
- Logging estructurado
- Validación de datos con Pydantic

## 📈 Rendimiento

### Índices Optimizados

El script `init_database.py` crea automáticamente índices optimizados para:

- Búsquedas por usuario y rol
- Filtros por residencia
- Consultas de residentes por estado
- Mediciones por fecha y tipo
- Tareas por residente y estado
- Logs de eventos por fecha y actor

### Consultas Eficientes

- Uso de `select_related` y `prefetch_related`
- Paginación en endpoints de listado
- Filtros optimizados por permisos de usuario
- Soft delete para mantener historial

## 🧪 Testing

```bash
# Crear datos de prueba
python seeds.py --minimal

# Verificar API
curl -X POST "http://localhost:8000/auth/login" \
     -H "Content-Type: application/json" \
     -d '{"alias":"admin","password":"admin123"}'
```

## 📝 Notas de Migración

### ✅ Limpieza Realizada

- ❌ Eliminados todos los scripts de fix temporales
- ❌ Eliminados archivos de investigación y debugging  
- ❌ Eliminados modelos duplicados en `src/`
- ❌ Eliminados logs y archivos de cache
- ❌ Eliminados entornos virtuales duplicados
- ✅ Consolidados todos los modelos en `app/models.py`
- ✅ Creado script de inicialización limpio
- ✅ Creado script de seeds unificado
- ✅ Actualizada estructura de importaciones

### 🚀 Mejoras Implementadas

- **Modelos consolidados**: Un solo archivo por entidad
- **Scripts profesionales**: Inicialización y seeds limpios
- **Documentación completa**: README y comentarios actualizados
- **Índices optimizados**: Rendimiento mejorado
- **Estructura limpia**: Código organizado y mantenible

## 🤝 Contribución

1. El código está completamente limpio y reorganizado
2. Todos los modelos están consolidados y documentados
3. Los scripts de inicialización son profesionales
4. La estructura es escalable y mantenible
5. No hay archivos basura ni código temporal

---

**¡Backend completamente limpio y listo para producción!** 🎉
