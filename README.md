# Simple ML Training Project

---

## Integrantes del Grupo 5

- Guillermo Parés
- Sheila Pena
- Claudi Berenguer
- Carlos Fernández

## Enlaces
proyecto en render: https://pontia-mlops-tutorial-grupo5.onrender.com/
proyecto blueprint: https://pontia-mlops-tutorial-grupo5-render.onrender.com/
repositorio github: https://github.com/carlos-fernandez-ruiz/pontia-mlops-tutorial-grupo5/
---

## Trabajo realizado

### 1. Configuración inicial del repositorio

- Creación del repositorio en GitHub para el grupo 5.
- Copia del contenido del repositorio base visto en clase.
- Actualización del `.gitignore`.
- Generación de `requirements.txt` con las librerías necesarias para el proyecto.
- Initial commit con la estructura base revisada del proyecto.

### 2. Pipeline de integración continua (CI)

Se ha creado la carpeta `.github/workflows/` con el fichero `integration.yml`, que define el pipeline de integración continua en GitHub Actions. Los cambios respecto al pipeline original visto en clase son:

- **Versión de Python**: se fija a `3.10` para garantizar compatibilidad.
- **Instalación de dependencias**: se cambia el comando de instalación para usar `pip install -r requirements.txt`.
- **Tolerancia a fallos en tests**: el pipeline se completa aunque los tests fallen, pero notifica el error al final del job.
- **Comentario de resultados en PR**: se corrige el campo `issue_number` usando `context.payload.pull_request.number` para que el comentario con los resultados y la cobertura se publique correctamente en el PR (evitando el fallo que se producía en clase al no identificar el número de PR).

### 3. Validación del pipeline y revisión de PR

- Se abrió una PR con los cambios del `integration.yml` y Sheila actuó como reviewer, aprobándola con el comentario *"looks good to me"*.
- Se validó que el pipeline se ejecuta correctamente de extremo a extremo.

### 4. Despliegue en Render

- Se creó el web service en Render siguiendo el mismo proceso que en clase.
- Al ejecutarlo, se produjo un error relacionado con la carpeta `deployment`, que todavía no existe en el repositorio. Queda pendiente de resolver.

### 5. Ruleset para la rama main

- Se configuró una ruleset en GitHub para proteger la rama `main` con los requisitos indicados en el enunciado.

### 6. Validación del flujo completo con "cambio chorra"

- Se añadió el secreto `RENDER_DEPLOY_HOOK` en GitHub para permitir el despliegue automático desde el pipeline.
- Se realizó un cambio en el `README.md` para verificar que:
  - El pipeline se ejecuta al abrir una PR.
  - La ruleset bloquea el merge hasta que se cumplan los requisitos.
  - Sheila revisó y aprobó la PR, validando el flujo completo.

### 7. Pipeline de build (`build.yml`)

- Se ha configurado el fichero `build.yml` en `.github/workflows/` usando como base el fichero proporcionado por el profesor en Google Drive (carpeta de evaluación).
- Se han aplicado las modificaciones vistas en clase:
  - Descarga del dataset necesario para el entrenamiento.
  - Actualización y publicación del modelo entrenado en la sección de **Releases** de GitHub.
- Se creó una PR con estos cambios. Tras algunos fallos iniciales en el pipeline por equivocación nuestra en el código, Sheila revisó y aprobó la PR, integrando el workflow de build en `main`.


### 8. Pipeline de deploy (`deploy.yml`)

- Se ha clonado el repositorio del grupo a local para seguir con el ejercicio
- Se ha configurado el fichero `deploy.yml` en `.github/workflows/` usando como base el fichero proporcionado por el profesor.
- Se copia el directorio `deployment`, con el endpoint y sus dependencias el directorio `app`, tal cual de la documentación del ejecrcicio.
- Se usa proyecto `Render` preexistente asociado a este repositorio
- `deploy.yml` llama a `Render` con el webhook contenido en 'secret' *RENDER_DEPLOY_HOOK* de este repositorio
- Se crea rama `deploy` en local, se hace un commit de los cambios sobre ella y se hace un push a este repositorio
- `Render`tiene actiavado por defecto *auto-deploy*,  con lo que con cada nuevo commit a la rama conectada - main en este caso -, si pasa los test, el servicio se despliega de nuevo.  `deploy` se llama vía *workflow dispatch* y llama a `Render`, por lo que no se desa *auto-deploy*. Se desactiva. Documentación: [Render auto-deploy](https://render.com/docs/deploys)

### 9. Rollback 

- En el contexto de devops un rollback es: 'En el contexto de DevOps, un rollback (o reversión) es el proceso de restaurar una aplicación, servicio o infraestructura a un estado estable anterior inmediatamente después de que una nueva implementación (deploy) o cambio haya causado problemas, errores o fallas inesperadas'
- En `Render`, en la pestaña *Events*, se puede ver el listado de deploys y hacer rollabk a uno de ellos
- Otra opción que se ha planteado es modificar el `deploy.yml` para que permita seleccionar versión de la API y modelo a desplegar en `Render`. Para ello:
  - Se asume que a los commit que són para deploy se les asigna un tag. Los tags van siempre en orden creciente
  - Cuando se hace el push, además de la rama también se debe hacer un push de los tag (git push --tags), dado que por defecto se quedan en local
  - Se introducen 2 inputs, *api_verion* y *model_version* ambos con default a *latest*. En el primero se puede integar el tag que se corresponde a la versión de la API que se desea y en el segundo el tag de la release del modelo
  - En `deploy`se hace un *git checkout* al tag especificado. Si se ha dejado en *latest*, lo hace al tag más alto (más reciente)
  - Se ha creado una variable de entorno en el repositorio llamada *MODEL_RELEASE* que se rellena con lo entrado en *model_version* Esta variable de entorno es usada por *app/main.py* para cargar el modelo deseado. Si se ha dejado en *latest*, se carga el más reciente


## Pendiente

#### Por parte de todos

- **Simulación de Rollback**: informarse sobre en qué consiste y cómo implementarla en el contexto del proyecto.
- **Revisión del entregable**: verificar conjuntamente que se cumplen todos los requisitos del enunciado antes de la entrega.
