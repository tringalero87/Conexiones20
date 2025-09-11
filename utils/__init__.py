"""
utils/__init__.py

Este archivo, aunque esté mayormente vacío, es fundamental. Su presencia
convierte al directorio 'utils' en un "paquete" de Python.

Esto permite que otros archivos de la aplicación puedan importar módulos
que se encuentren dentro de esta carpeta de una manera organizada y estructurada.

Por ejemplo, gracias a este archivo, podemos hacer:
from utils.computos import calcular_peso

Sin este archivo, Python no reconocería a 'utils' como una fuente de módulos
y las importaciones fallarían. No se necesita añadir más código aquí a menos
que se quiera ejecutar alguna lógica de inicialización específica para el paquete,
lo cual no es necesario para este proyecto.
"""