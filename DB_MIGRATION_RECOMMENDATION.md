# Recomendación de Migración de Base de Datos

## Resumen

Este documento describe los cambios realizados para preparar la aplicación para una migración de base de datos de SQLite a PostgreSQL, y explica por qué esta migración es crucial para el rendimiento y la escalabilidad de la aplicación.

## Problema

La aplicación utiliza actualmente SQLite como su base de datos. Si bien SQLite es una excelente opción para el desarrollo y para aplicaciones con un solo usuario, tiene limitaciones significativas en un entorno de múltiples usuarios.

La principal limitación es que **SQLite solo permite una operación de escritura a la vez**. Esto significa que si varios usuarios intentan realizar acciones que modifican la base de datos simultáneamente (como crear una conexión, agregar un comentario o cambiar un estado), se bloquearán entre sí y tendrán que esperar su turno. Con 10 usuarios simultáneos, esto provocará retrasos notables y una mala experiencia de usuario.

## Solución: Migración a PostgreSQL

Para resolver este problema, se recomienda encarecidamente migrar la base de datos a PostgreSQL. PostgreSQL es un sistema de base de datos de nivel de producción, de código abierto y de alto rendimiento que está diseñado para manejar un alto volumen de usuarios y transacciones simultáneas.

### Cambios Realizados

Para facilitar esta migración, he realizado los siguientes cambios preparatorios en el código:

1.  **`docker-compose.yml` actualizado:**
    *   Se ha añadido un nuevo servicio `db` que ejecuta una imagen oficial de PostgreSQL 13.
    *   La aplicación web (`web`) ahora depende de este servicio de base de datos.
    *   Se ha añadido una variable de entorno `DATABASE_URL` para configurar la conexión a PostgreSQL.

2.  **`db.py` modificado:**
    *   El código de gestión de la base de datos ahora es compatible tanto con SQLite como con PostgreSQL.
    *   Si la variable de entorno `DATABASE_URL` está configurada, la aplicación se conectará a PostgreSQL. De lo contrario, utilizará la base de datos SQLite como antes.
    *   Esto permite seguir utilizando SQLite para un desarrollo local sencillo si se desea.

3.  **`requirements.txt` actualizado:**
    *   Se ha añadido la librería `psycopg2-binary`, que es el adaptador de Python necesario para conectarse a PostgreSQL.

## Próximos Pasos

Para completar la migración, se deben seguir los siguientes pasos:

1.  **Iniciar el entorno con PostgreSQL:** Ejecute `docker-compose up -d` (o `sudo docker compose up -d`). Esto iniciará tanto la aplicación web como el nuevo contenedor de la base de datos PostgreSQL.
2.  **Inicializar la base de datos:** Ejecute el comando `flask init-db` dentro del contenedor de la aplicación para crear todas las tablas en la base de datos PostgreSQL.
3.  **Migrar los datos existentes (Opcional):** Si necesita conservar los datos existentes de su base de datos SQLite, deberá realizar una migración de datos. Existen varias herramientas para esto, como `pgloader`. Este paso es más complejo y requiere una planificación cuidadosa.
4.  **Probar la aplicación:** Pruebe exhaustivamente la aplicación para asegurarse de que todo funciona como se espera con la nueva base de datos.

Al migrar a PostgreSQL, la aplicación estará mucho mejor preparada para manejar la carga de 10 usuarios simultáneos y para escalar a futuro.
