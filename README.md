# PythIA
`Autora: Lydia Blanco Ruiz.`

[![Build](https://github.com/lbr1014/TFG_RAG/actions/workflows/build.yml/badge.svg)](https://github.com/lbr1014/TFG_RAG/actions/workflows/build.yml)
![Python](https://img.shields.io/badge/Python-3.12-blue)
![Flask](https://img.shields.io/badge/Flask-3.x-black?logo=flask)
![Docker](https://img.shields.io/badge/Docker-Enabled-2496ED?logo=docker)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791?logo=postgresql)
![Qdrant](https://img.shields.io/badge/Qdrant-Vector%20DB-red)

[![Security Rating](https://sonarcloud.io/api/project_badges/measure?project=lbr1014_TFG_RAG&metric=security_rating&token=adefdd0a9fe6e7c41ada92a0208e968f13dbf23f)](https://sonarcloud.io/summary/new_code?id=lbr1014_TFG_RAG)
[![Coverage](https://sonarcloud.io/api/project_badges/measure?project=lbr1014_TFG_RAG&metric=coverage&token=adefdd0a9fe6e7c41ada92a0208e968f13dbf23f)](https://sonarcloud.io/summary/new_code?id=lbr1014_TFG_RAG)
[![Quality Gate Status](https://sonarcloud.io/api/project_badges/measure?project=lbr1014_TFG_RAG&metric=alert_status&token=adefdd0a9fe6e7c41ada92a0208e968f13dbf23f)](https://sonarcloud.io/summary/new_code?id=lbr1014_TFG_RAG)
[![Bugs](https://sonarcloud.io/api/project_badges/measure?project=lbr1014_TFG_RAG&metric=bugs&token=adefdd0a9fe6e7c41ada92a0208e968f13dbf23f)](https://sonarcloud.io/summary/new_code?id=lbr1014_TFG_RAG)
[![Code Smells](https://sonarcloud.io/api/project_badges/measure?project=lbr1014_TFG_RAG&metric=code_smells&token=adefdd0a9fe6e7c41ada92a0208e968f13dbf23f)](https://sonarcloud.io/summary/new_code?id=lbr1014_TFG_RAG)
[![Coverage](https://sonarcloud.io/api/project_badges/measure?project=lbr1014_TFG_RAG&metric=coverage&token=adefdd0a9fe6e7c41ada92a0208e968f13dbf23f)](https://sonarcloud.io/summary/new_code?id=lbr1014_TFG_RAG)
[![Duplicated Lines (%)](https://sonarcloud.io/api/project_badges/measure?project=lbr1014_TFG_RAG&metric=duplicated_lines_density&token=adefdd0a9fe6e7c41ada92a0208e968f13dbf23f)](https://sonarcloud.io/summary/new_code?id=lbr1014_TFG_RAG)
[![Maintainability Rating](https://sonarcloud.io/api/project_badges/measure?project=lbr1014_TFG_RAG&metric=sqale_rating&token=adefdd0a9fe6e7c41ada92a0208e968f13dbf23f)](https://sonarcloud.io/summary/new_code?id=lbr1014_TFG_RAG)






<p align="center">
  <img width="300" height="300" alt="PythIA_def" src="https://github.com/user-attachments/assets/6e44a4d9-eb22-4aba-a984-b625981c8ded" />
</p>

**PythIA** es una aplicación que permite realizar consultas sobre las licitaciones del estado, concretamente de la **Junta de Gobierno de la Diputación Provincial de Burgos**. Las respuestas se generan usando un ***LLM***  (*Large Lenguaje Model*) alimentado por un modelo ***RAG*** (*Retrieval-Augmented Generation*) que busca información concreta de los pliegos de la Junta.

En la siguiente imagen se puede observar la arquitectura general del sistema RAG:

<img width="1024" height="744" alt="ArquitecturaRAG" src="https://github.com/user-attachments/assets/e3f1335d-5501-487a-b3dd-ed9efc298ece" />


Se puede **acceder a la aplicación** desde cualquier navegador accediendo a la dirección:
> [https://pythia.es](https://pythia.es/)

## 🚀 Despliegue en local
### 📋 Precondiciones
Para el despliegue en local debe estar instalado en el sistema  <a href="#instalarDocker">*docker*</a> y <a href="#instalarGit">*git*</a>.

#### ⚙️ Instalar ***docker*** <a id="instalarDocker"></a>
Para instalar *docker* en ***Ubuntu*** se debe:
   1) Instalar dependencias:
      ```bash
      sudo apt install ca-certificates curl gnupg lsb-release -y
      ```
   3) Instalar docker:
      ```bash
      sudo apt install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin -y
      ```

Para instalar *docker* en ***Windows*** se puede descargar directamente la aplicación de escritorio de la página oficial de [*docker*](https://www.docker.com/products/docker-desktop/).

NOTA:
> Se puede confirmar la instalación mirando la versión que hay de *docker* instalada en el sistema. Si devuelve una versión, es que se ha instalado correctamente.
>  ```bash
>  docker --version
>  ```

#### ⚙️ Instalar ***git*** <a id="instalarGit"></a>
Para instalar *git* en ***Ubuntu*** se debe ejecutar el siguiente comando:
```bash
sudo apt install git -y
```
Para instalar *git* en ***Windows*** se puede descargar desde la *web* oficial [*git*](https://git-scm.com/)

NOTA:
> Se puede confirmar la instalación mirando la versión que hay de *git* instalada en el sistema. Si devuelve una versión, es que se ha instalado correctamente.
>  ```bash
>  git --version
>  ```
>  También, se puede configurar el usuario y el correo para que los *commits* queden asociados al usuario:
> ```bash
> git config --global user.name "Nombre Usuario"
> git config --global user.email "emailUsuario@ejemplo.com"
> ```

### ⛓️ Clonar el repositorio
Una vez que este el comando *git* se debe clonar el repositorio del proyecto. Para ello se deben seguir los siguientes pasos:
  1) Clonar el repositorio:
     ```bash
      git clone https://github.com/lbr1014/TFG_RAG.git
      ```
  2) Acceder a la carpeta donde se encuentra la aplicación:
     ```bash
     cd app/normativa_UBU
     ```
  3) Crear archivo _secret.env_
     > Este archivo debe tener como mínimo configuradas las siguientes variables:
     ```
     SECRET_KEY =
     FLASK_SESSION_SIGNER =
     POSTGRES_PASSWORD =
     ```
     NOTA:
     > En el apartado <<Documentación técnica de programación>> de la memoria, concretamente en <<Compilación, instalación y ejecución del proyecto>>, se detalla el contenido completo del archivo.

### 🐳 Levantar el proyecto con *Docker*
Una vez clonado el repositorio y teniendo *Docker* instalado, se puede levantar la aplicación utilizando ***Docker Compose***.
  - Este primer comando permite **levantar** la aplicación reconstruyendo el código (ideal para la primera ejecución). Va a construir las imágenes y levantar los contenedores:
    ```bash
    docker compose up --build
    ```
  - Si se desea **reconstruir** las imágenes, pero ejecutando los contenedores en **segundo plano**:
    ```bash
    docker compose up -d --build
    ```
  - Si solo se desea **reconstruir** las imágenes sin levantar los contenedores, se puede usar el comando Compose sin el *up*:
    ```bash
    docker compose build
    ```
  - Para que reconstruya el código **sin** usar la **caché** almacenada por *Docker* (recomendado si hay fallos de dependencias):
    ```bash
    docker compose build --no-cache
    ```
  - Para levantar la aplicación **sin reconstruir** el código, utilizando las imágenes construidas previamente:
    ```bash
    docker compose up
    ```

Para **parar** los contenedores se pueden usar dos comando.
  - El primero permite detener los contenedores **manteniendo** los volúmenes y datos:
    ```bash
    docker compose down
    ```
  - Si además se desea **eliminar** los volúmenes y los datos (incluyendo bases de datos y archivos guardados):
    ```bash
    docker compose down --volumes
    ```

Si se desea **borrar** la caché de los *builds* manteniendo los contenedores y las imágenes activas, se usa:
```bash
docker builder prune -af
```
Si se desea realizar una **limpieza completa** de *Docker*, incluyendo los contenedores parados, las imágenes no usadas, la caché y los volúmenes, se puede usar este comando:
```bash
docker system prune -af --volumes
```
Para ver los ***logs*** de la aplicación se puede usar el comando:
```bash
docker compose logs -f
```
Para **reiniciar** servicios se puede usar el comando:
```bash
docker compose restart
```
NOTA:
> Para comprobar que los contenedores están funcionando, se puede usar este comando:
> ```bash
> docker ps
> ```

### 🗝️ Acceso a la aplicación local
Una vez desplegada la aplicación en local utilizando un contenedor *Docker* levantado en *Gunicorn* y usando *Nginx* como *proxy* inverso, se puede **acceder** a través del **navegador** ***web*** poniendo cualquiera de estas direcciones:
- [http://127.0.0.1:8080/](http://127.0.0.1:8080/)
- [http://localhost:8080/](http://localhost:8080/)
- `http://IP_del_dispositivo:8080`

NOTA:
> Los dos primeros solo son accesibles desde el propio dispositivo donde se ejecuta. En cambio, la opción de la IP es accesible desde cualquier dispositivo conectado a la misma red.

IMPORTANTE:
> Se ha creado un administrador por defecto en la aplicación para permitir el acceso con este rol.
> Sus credenciales para iniciar sesión son:
>
>   - email: `admin@gmail.com`
>   - contraseña: `contraseña`
