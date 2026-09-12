# PythIA - Aplicación final

Autora: Lydia Blanco Ruiz.

En esta carpeta se encuentra la versión final de la aplicación. Está preparada para ejecutarse desde cualquier dispositivo sin necesidad de gestionar sus dependencias, ya que se despliega en un contenedor Docker con Gunicorn y utiliza Nginx como proxy inverso.

## Estructura general del directorio

- Pythia/
  - app/
    - main/
      - code/
        - controllers/
          - admin/
          - auth/
          - main/
          - rag/
        - inetrnacionalizacion/
        - model/
        - services/
          - markdown/
          - rag/
          - documentos.py
          - async_tasks.py
          - markdown_conversion_state.py
          - vector_update_state.py
        - __init__.py
        - countries.py
        - decorators.py
        - extensions.py
        - forms.py
        - run.py
      - resources/
        - static/
        - templates/
    - test/
      - integration/
      - unit/
      - support.py
      - run_tests.sh
  - migrations/
  - docker/
    - nginx/
      - nginx.conf.template
    - Dockerfile
    - Dockerfile.dockerignore
    - entrypoint.sh
    - requirements_docker.txt
  - docker-compose.yml

## Contenido de los archivos y directorios

- **app/main/code**: contiene el código Python real de la aplicación Flask. Concretamente, los controladores, modelos, formularios, servicios, RAG y el punto de entrada `run.py`.
- **app/main/code/controllers**: contiene los controladores y blueprints de la aplicación.
- **app/main/code/services**: contiene la lógica de servicio de la aplicación, incluyendo RAG, conversión a Markdown, tareas asíncronas y gestión de documentos.
- **app/main/code/model**: contiene los modelos y entidades de dominio de la aplicación.
- **app/test**: contiene los tests unitarios y de integración de la aplicación, además de utilidades compartidas y el script `run_tests.sh`, que sirve para ejecutar los **tests**.
- **migrations**: contiene el historial de versiones de la base de datos, gestionado con Flask-Migrate/Alembic. Estas migraciones sirven para aplicar de forma automática los cambios de la base de datos en cualquier entorno.
- **docker/nginx**: contiene la configuración del servidor Nginx. Nginx actúa como proxy inverso delante de la aplicación Flask.
- **app/main/resources/static**: almacena los archivos estáticos: CSS, JavaScript e imágenes.
- **app/main/resources/templates**: contiene las plantillas HTML que Flask renderiza con Jinja2.
- **docker-compose.yml**: define la arquitectura de la aplicación en contenedores Docker e indica cómo se relacionan entre sí. Levanta la base de datos SQL (`db`) con PostgreSQL y un volumen persistente, la base de datos vectorial (`qdrant`) y un LLM local (`Ollama`). Además, el servicio de Ollama descarga y verifica automáticamente los modelos configurados en `RAG_LLM_MODELS` y el modelo OCR antes de que arranque la web. El servicio principal es `web`, que construye la app Flask, espera a que los servicios estén listos y configura las variables de entorno: URL de Ollama, Qdrant y directorio de documentos. Se ejecuta con Gunicorn y Nginx. También define un servicio para los tests, que utilizan SQLite en memoria. Por último, define volúmenes persistentes para Postgres, Qdrant, Ollama, la caché de Hugging Face y los datos de la aplicación.
- **docker/Dockerfile**: define cómo se construye la imagen Docker de la aplicación. Parte de la imagen `mcr.microsoft.com/playwright/python:v1.57.0-jammy`, que ya incluye Python y Playwright. Establece `/app` como directorio de trabajo e instala las dependencias del sistema necesarias para compilar paquetes Python y conectarse a PostgreSQL. Las dependencias de Python se instalan desde `docker/requirements_docker.txt`, que se copia antes para aprovechar la caché de Docker. Después, copia el código del proyecto dentro del contenedor, expone el puerto `5000` (donde corre Gunicorn) y establece el script `docker/entrypoint.sh` como inicio del contenedor.
- **docker/Dockerfile.dockerignore**: contiene los archivos excluidos del contexto de build asociado al Dockerfile.
- **docker/entrypoint.sh**: se ejecuta cuando arranca el contenedor de la aplicación (`web`). Se encarga de preparar el entorno, construir la variable `DATABASE_URL` y esperar a que PostgreSQL y Qdrant estén disponibles. Una vez que las bases de datos están listas, aplica las migraciones. Por último, inicia el servidor en producción usando Gunicorn.
- **docker/requirements_docker.txt**: lista las dependencias necesarias para ejecutar la aplicación dentro del contenedor Docker. Al construir la imagen, este archivo permite instalar automáticamente todas las librerías necesarias para su ejecución.
- **app/main/code/run.py**: sirve como punto de entrada a la aplicación Flask. Importa `create_app()`, crea la instancia de la aplicación y la expone como variable `app`.

## Ejecución de los archivos

En este apartado se indican los pasos para ejecutar la aplicación web.

Para acceder a la página web ya levantada en el servidor, solo hay que acceder al dominio pythia.es:

[PythIA](https://pythia.es)

Si se desea, también es accesible (si se está conectado a Eduroam) desde la IP del servidor:

[PythIA (10.168.168.124:7000)](http://10.168.168.124:7000/)

Si se desea desplegar en local, se puede levantar usando los siguientes comandos.

- Este primer comando permite levantar la aplicación reconstruyendo el código (ideal para la primera ejecución). Va a construir las imágenes y levantar los contenedores:

  ```bash
  docker compose up --build
  ```

- Si solo se desea reconstruir las imágenes sin levantar los contenedores, se puede usar el comando Compose sin el `up`:

  ```bash
  docker compose build
  ```

- Para que reconstruya el código sin usar la caché almacenada por Docker (recomendado si hay fallos de dependencias):

  ```bash
  docker compose build --no-cache
  ```

- Para levantar la aplicación sin reconstruir el código, utilizando las imágenes construidas previamente:

  ```bash
  docker compose up
  ```

- Para ejecutar los tests:

  ```bash
  docker compose --profile test up test
  ```

Para parar los contenedores se pueden usar dos comandos.

- El primero permite detener los contenedores manteniendo los volúmenes y datos:

  ```bash
  docker compose down
  ```

- Si además se desea eliminar los volúmenes y los datos, incluyendo bases de datos y archivos guardados:

  ```bash
  docker compose down --volumes
  ```

Si se desea borrar la caché de los builds manteniendo los contenedores y las imágenes activas, se usa:

```bash
docker builder prune -af
```

Si se desea realizar una limpieza completa de Docker, incluyendo los contenedores parados, las imágenes no usadas, la caché y los volúmenes, se puede usar este comando:

```bash
docker system prune -af --volumes
```

Para ver los logs de la aplicación se puede usar el comando:

```bash
docker compose logs -f
```

Para reiniciar servicios se puede usar el comando:

```bash
docker compose restart
```

Nota: para que funcione el despliegue en local, debe estar instalado Docker en el sistema.

Para instalar Docker en Ubuntu:

1. Instalar dependencias:

   ```bash
   sudo apt install ca-certificates curl gnupg lsb-release -y
   ```

2. Instalar Docker:

   ```bash
   sudo apt install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin -y
   ```

Se puede confirmar la instalación consultando la versión de Docker instalada en el sistema. Si devuelve una versión, es que se ha instalado correctamente.

```bash
docker --version
```

Para instalar Docker en Windows se puede descargar directamente la aplicación de escritorio desde la página oficial de [Docker](https://www.docker.com/products/docker-desktop/).

De igual forma que en Ubuntu, se puede confirmar la instalación ejecutando el comando:

```powershell
docker --version
```
