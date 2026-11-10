# Instrucciones para agentes

## Al iniciar una sesión
1. Leer el archivo más reciente de `agentes-documentacion/<agente>/`.
2. Buscar la última entrada con estado `🔄 En progreso` y retomar desde su campo "Pendiente".
3. Leer `README.md` y `wiki/0.-Plan-del-Challenge-3.md` para el contexto del proyecto.

## Formato de cada entrada
```
## HH:MM — Título de la acción
**Acción:** qué se hizo
**Archivos tocados:** lista con ruta y motivo
**Contexto:** por qué, qué problema resuelve
**Pendiente / Próximo paso:** qué falta si quedó incompleto
**Estado:** ✅ Completado | 🔄 En progreso | ⏸ Pausado | ❌ Fallido
```

## Reglas
- Documentar cada acción inmediatamente después de hacerla.
- Si el contexto se agota a medias, dejar `🔄 En progreso` con "Pendiente" completo.
- Evaluar antes de ejecutar; preguntar ante ambigüedad; confirmar el plan en tareas grandes.
- Verificar (compilación, pruebas) antes de reportar éxito.
