"""
utils/computos.py

Este módulo contiene funciones de utilidad para realizar cálculos de ingeniería
relacionados con las conexiones y los perfiles estructurales, como el cálculo
de cómputos métricos (pesos, áreas, etc.).

Estas funciones están diseñadas para ser reutilizables y desacopladas del resto
de la lógica de la aplicación.
"""

import json
import os
import re
from flask import current_app

# Variable global para almacenar los datos de los perfiles y evitar leer el archivo
# repetidamente en la misma solicitud. Es una optimización de rendimiento.
_perfiles_data = None

def _convert_fraction_to_float(frac_str):
    """
    Convierte una cadena que representa una fracción o un número mixto a un float.
    Ejemplos: "1/2" -> 0.5, "1 1/2" -> 1.5, "2" -> 2.0
    """
    if not frac_str:
        return 0.0

    # Normalizar la cadena para manejar espacios inconsistentes, especialmente alrededor de las fracciones.
    # Elimina espacios al principio/final y colapsa espacios alrededor de la barra de división.
    # Ejemplo: " 1 1 / 2 " -> "1 1/2"
    normalized_str = re.sub(r'\s*/\s*', '/', frac_str.strip())

    try:
        # Si es un número simple (entero o decimal), lo convierte directamente.
        if ' ' not in normalized_str and '/' not in normalized_str:
            return float(normalized_str)

        # Si es una fracción mixta (ej. "1 1/2")
        if ' ' in normalized_str:
            parts = normalized_str.split(' ')
            # Puede haber espacios extra, filtrar partes vacías
            parts = [p for p in parts if p]
            whole_part = float(parts[0])
            frac_part_str = parts[1]
        else: # Si es una fracción simple (ej. "1/2")
            whole_part = 0
            frac_part_str = normalized_str

        # Convertir la parte fraccionaria
        if '/' in frac_part_str:
            num, den = frac_part_str.split('/')
            frac_part = float(num) / float(den)
        else: # No debería ocurrir si hay espacios, pero por si acaso.
            frac_part = float(frac_part_str)

        return whole_part + frac_part
    except (ValueError, ZeroDivisionError):
        # Si la conversión falla, devuelve 0.0 y deja que el logger principal lo maneje.
        raise ValueError(f"No se pudo convertir la fracción '{frac_str}' a un número.")


def _calculate_plate_weight(profile_name, longitud_mm):
    """
    Calcula el peso de perfiles de platina (PL) basado en sus dimensiones.
    Formato esperado: PL<espesor>X<ancho> (ej: PL1/2X10, PL1 1/2 X 12)
    Las dimensiones se asumen en pulgadas.
    """
    # Regex mejorada para capturar espesor y ancho, permitiendo espacios y fracciones.
    # Grupo 1: Espesor (puede ser número, fracción, o mixto)
    # Grupo 2: Ancho (puede ser número, fracción, o mixto)
    match_PL = re.match(r'^PL\s*([0-9\s/.]+)\s*[X*]\s*([0-9\s/.]+)', profile_name, re.IGNORECASE)
    if not match_PL:
        return None # No es un perfil de platina válido

    try:
        thickness_str = match_PL.group(1).strip()
        width_str = match_PL.group(2).strip()

        thickness_in = _convert_fraction_to_float(thickness_str)
        width_in = _convert_fraction_to_float(width_str)

        # Fórmula estándar para calcular peso de platinas en lb/ft:
        # Peso (lb/ft) = Ancho (in) * Espesor (in) * 3.4
        peso_lb_ft = width_in * thickness_in * 3.4

        # --- Conversión de unidades ---
        # 1 ft = 304.8 mm
        # 1 lb = 0.453592 kg

        longitud_ft = float(longitud_mm) / 304.8
        peso_total_lb = longitud_ft * peso_lb_ft
        peso_total_kg = peso_total_lb * 0.453592

        return round(peso_total_kg, 2)

    except (ValueError, TypeError, IndexError) as e:
        current_app.logger.warning(f"No se pudo parsear o calcular el peso para el perfil de platina '{profile_name}': {e}")
        return None


def _cargar_propiedades_perfiles():
    """
    Función auxiliar interna para cargar el archivo JSON con las propiedades de los perfiles.
    Utiliza una caché simple en memoria para evitar leer el archivo del disco en cada llamada.
    """
    global _perfiles_data
    if _perfiles_data is not None:
        return _perfiles_data

    json_path = os.path.join(current_app.root_path, 'perfiles_propiedades.json')
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            _perfiles_data = json.load(f)
            normalized_data = {}
            for key, value in _perfiles_data.items():
                normalized_key = re.sub(r'[ -]', '', key).upper()
                normalized_data[normalized_key] = value
            _perfiles_data = normalized_data
            return _perfiles_data
    except FileNotFoundError:
        current_app.logger.error(f"Error crítico: No se encontró el archivo de propiedades de perfiles en '{json_path}'.")
        _perfiles_data = {}
        return {}
    except json.JSONDecodeError:
        current_app.logger.error(f"Error crítico: El archivo 'perfiles_propiedades.json' está corrupto o mal formado.")
        _perfiles_data = {}
        return {}


def calcular_peso_perfil(nombre_perfil, longitud_mm):
    """
    Calcula el peso de un perfil de acero específico basado en su longitud.
    Maneja perfiles del JSON y perfiles de platina (PL) calculados dinámicamente.
    """
    if not nombre_perfil or longitud_mm is None:
        return 0.0

    propiedades = _cargar_propiedades_perfiles()
    normalized_nombre_perfil = re.sub(r'[ -]', '', nombre_perfil).upper()

    # 1. Búsqueda en el JSON de perfiles
    perfil_info = propiedades.get(normalized_nombre_perfil)
    if perfil_info:
        try:
            peso_por_metro = float(perfil_info.get('Peso_kg_m', 0))
            longitud_metros = float(longitud_mm) / 1000.0
            peso_total_kg = peso_por_metro * longitud_metros
            return round(peso_total_kg, 2)
        except (ValueError, TypeError) as e:
            current_app.logger.error(f"Error al calcular el peso para el perfil JSON '{nombre_perfil}': {e}.")
            return 0.0

    # 2. Si no se encuentra, intentar calcular como perfil de platina (PL)
    if normalized_nombre_perfil.startswith('PL'):
        peso_calculado = _calculate_plate_weight(nombre_perfil, longitud_mm)
        if peso_calculado is not None:
            return peso_calculado

    # Si no es un perfil del JSON ni un perfil PL calculable, devolver 0.0
    current_app.logger.warning(f"No se encontraron propiedades para el perfil '{nombre_perfil}' y no es un tipo calculable (ej. PL).")
    return 0.0