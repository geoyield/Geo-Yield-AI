# PROYECTO JUPYTER GEOYELD

---

## Descripción del repositorio

Estructrua incial básica del repositorio. Susceptible de evolucionar con el proyecto.
Descripción de archivos y directorios:

- `docs`: datos relevantes, como la descirpción de los datos de entrada, la estructura del repo - de hecho este documento debería estar ahí - o cual es la finalidad del proyecto, por ejemplo

- `notebooks`: contiene los jupyter notebooks de experimentación con los datos
  
- `src`: contiene el código para la construcción del modoelo:
  - `data_loader.py`: carga datos y los pre-porcesa (adecúa) los datos para poder ser usados. Los datos de entrada están en `data`
  - `model.py`: crea y entrena el modelo con los datos de entremiento
  - `evaluate.py`: evalúa el modelo con los datos de test
  - `main.py`: implementa la pipeline, haciendo uso de los componentes implementados en los archivos de arriba. La última cosa que hace es crear los componentes del model serializándolos en pikel y dejándolos en el directorio `models`
  
- `unit_tests`: implementa tests unitarios de las funciones definidas en `src`. Asegura que las funciones hacen lo que se espera de ellas. Los test se ejecutan con el comando *pytest*
- `model tests`: implementa tests en el modelo en `moodels`, verificando que cumple con un mínimo de *accuracy*,por ejemplo. Los test se ejecutan con el comando *pytest*
  
- `deplolyment`: contiene la aplicación a desplegar, que no incluye nada de lo que está fuera de este directorio. Lo que está fuera es para construir el modelo. La aplicación usa el modelo construdio. Su contenido:
  - `main.py`: es el punto de entrada a la aplicación. A llamar por el *CMD* del archivo imágen de docker. Levanta el web server (uvicorn en este caso) y llama a la aplicación
  - `schema`: contiene los 'interfaces' que definen los formatos de la entrada y salida
  - `app`: contiene la aplicación en sí. Descarga una versión del modelo (en este caso guardado como una release en Github), que viene indicada en una variable de entorno de github (*"MODEL_VERSION*) que se inicializa en el momento de hacer el deployment (en este caso usando la gitub actiuon defilida en `.github/workflows/deployment-yml`), crea el modelo, contiene los endpoint. Al salir limpia de archivos temporales. Importa *metrics* para actualizarlas, definidas en el directrio `metrics`. Va generando el log en el directrio `log`. También exite el directrio `env`, que contiene el archivo `.env`, pensado para contener variables de entorno.`metrics`, `log` y `env` están pensados para ser asignados a un volumen en el host cuando se cree el container, para darles persistencia
  - `requirements.txt`: contiene las dependencias de la aplicación
  
- **CI:** Basado en lo visto en el ejercicio de evaluación de devops
  - `.github\workflows\integrate.yml`: actualiza dependencias, instala el código del repositorio en github, ejecuta los test unitarios y muestra su resultado. El disparador es una pull request a main
  - `.github\workflows\build.yml`: actualiza dependencias, descarga los datos de entrenamientoy test, crea versión del modelo y la guarda, en este caso como una *release* en github. El disparador es un push a main
                                  
- **CD:**
  - **Con github + *Render*:** `deployment.yml`: Contiene uan forma de hacer el deplyment en *Render* desde el repositorio de github. La configuración de *Render* viene en `*Render*.yml`. El disparador es manual. Al ejectuarse pregunta por ls versión de la api y del modelo a desplegar, por defecto las más recientes (latest). Asume que al subir una versión de la api al repositorio se crea un tag y se hace un push del mismo (los tag se deben crear en orden ascendente, *git push --tags*). Hace un git chekcout al tag especificado y carga en la variable de entorno *"MODEL_VERSION* la versión del modelo
  - **Con docker + *Render*:** *Render* permite desplegar desde una imágen docker en el repositorio. entro del directorio `deployment` se incluyen un dockerfile para la api, otro para la base de datos y un dockercompose que los conecta en un bridge (de momento aun no creados explíctamente, a modo de muestra hay lo usado en la evaluación del módulo de contenedores):
    - `Dockerfile_api`: imagen para un container con la api. Debe estar alineado en version de python con la usada en el desarrollo en local y la del CI en github. Lo llama docker-compose para crear el container en *Render*
    - `Dockerfile_db`: imagen para la base de datos. Lo llama docker-compose para crear el container en *Render*. Tmaibén debe llamarse en local para crear la base de datos y exponerla en un puerto, para poder hacer el debug. Si el modelo incluye una base de datos, entonces deberá incluirse en `integrate.yml`, la acción deberá crear el container en github actions (https://docs.github.com/en/actions/tutorials/use-containerized-services/create-a-docker-container-action)
    - `docker-compose.yml`: llama a los dockerfile, crea los volumenes `metrics`, `log`, `env` y el propio de la base de datos para dar persistencia, une el container de la api con la base de datos por un bridge, gestiona la dependencia de la api de la base de datos en la incialización        
  
- Otros:
  - `.venv`: es el entorno virtual
  - `.gitignore`
  - `requirements.txt`: contiene las dependencias del directrio entero
