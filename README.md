# AJPLAY Catalog Engine

Preparación y distribución de catálogos VOD para AJPLAY.

## Arquitectura prevista

- GitHub Actions: extrae y valida el catálogo cuando hay cambios de asignaciones o se solicita manualmente.
- Cloudflare R2: almacena los JSON privados por usuario.
- Cloudflare Worker: autentica las solicitudes y entrega el catálogo.
- AJPLAY Android: descarga y cachea el catálogo; realiza la búsqueda local.
- Consulta individual al proveedor: solo al abrir una película para obtener detalles y fuentes.

## Reglas de integridad del catálogo

- No normalizar ni renombrar títulos.
- No normalizar años.
- No deduplicar, fusionar ni eliminar registros repetidos.
- Conservar los datos originales del proveedor.
- No publicar credenciales IPTV ni catálogos privados.
- Publicar de forma atómica: conservar el catálogo anterior si falla la extracción o validación.

## Estado de configuración

El Worker de prueba se despliega por separado en Cloudflare.
Para habilitar la publicación de catálogos, activar R2 en el Dashboard de Cloudflare y crear el bucket privado correspondiente.

## Secrets necesarios para GitHub Actions

Se configurarán cuando R2 esté habilitado:
- CLOUDFLARE_ACCOUNT_ID
- CLOUDFLARE_API_TOKEN (permisos mínimos para escribir en el bucket R2 seleccionado)

No añadir credenciales IPTV, tokens ni claves privadas al repositorio.
