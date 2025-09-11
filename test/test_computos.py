# test/test_computos.py
import pytest
from utils.computos import calcular_peso_perfil

# La fixture 'app' es necesaria porque calcular_peso_perfil utiliza 'current_app' indirectamente.
def test_calculo_perfil_existente(app):
    """
    Prueba un cálculo de peso simple con un perfil que existe en perfiles_propiedades.json.
    """
    with app.app_context():
        # Perfil IPE 300 tiene un peso de 42.2 kg/m.
        # Longitud de prueba: 1000 mm (1 metro).
        # Peso total esperado en kg = 42.2 kg/m * 1 m = 42.2 kg.
        assert calcular_peso_perfil("IPE 300", 1000) == 42.2

def test_calculo_perfil_inexistente(app):
    """
    Prueba que un perfil que no existe (y no es un perfil calculable como PL) devuelve 0.
    """
    with app.app_context():
        assert calcular_peso_perfil("PERFIL-INEXISTENTE", 1000) == 0.0

def test_calculo_platina_fraccion_simple(app):
    """
    Prueba el cálculo de peso para un perfil de platina (PL) con una fracción simple.
    Esta prueba fallará hasta que se re-implemente la lógica de cálculo para platinas.
    """
    with app.app_context():
        # Perfil: PL1/2X10
        # Espesor = 0.5 in, Ancho = 10 in
        # La lógica anterior usaba una fórmula de lb/ft y convertía a kg.
        # Peso (lb/ft) = Ancho (in) * Espesor (in) * 3.4 = 10 * 0.5 * 3.4 = 17 lb/ft
        # Longitud: 304.8 mm (1 ft)
        # Peso en lb = 17 lb/ft * 1 ft = 17 lb
        # Peso en kg = 17 lb * 0.453592 kg/lb = 7.711... kg
        # La función original que vi usaba la conversión de lb/ft a kg.
        # Por consistencia, si re-implemento esa lógica, el valor debería ser este.
        # Si la nueva implementación es diferente, ajustaré este valor.
        # Por ahora, el objetivo es que no devuelva 0.0.
        # El valor esperado es 7.71
        assert calcular_peso_perfil("PL1/2X10", 304.8) == 7.71

def test_calculo_platina_fraccion_mixta(app):
    """
    Prueba el cálculo de peso para un perfil de platina (PL)
    con una fracción mixta en el espesor.
    Esta prueba está diseñada para fallar antes de la corrección.
    """
    with app.app_context():
        # Perfil: PL1 1/2X10
        # Espesor = 1.5 in, Ancho = 10 in
        # Peso (lb/ft) = 1.5 * 10 * 3.4 = 51 lb/ft
        # Longitud: 304.8 mm (1 ft)
        # Peso esperado (kg) = 51 lb * 0.453592 kg/lb = 23.133...
        # El valor esperado es 23.13
        assert calcular_peso_perfil("PL1 1/2X10", 304.8) == 23.13

def test_calculo_platina_con_espacios_en_fraccion(app):
    """
    Prueba el cálculo de peso para un perfil de platina (PL) con espacios
    adicionales alrededor de la fracción. Esta prueba está diseñada para
    fallar antes de la corrección en _convert_fraction_to_float.
    """
    with app.app_context():
        # Perfil: PL1/2X10, pero con espacios extra.
        # El peso esperado es el mismo que en test_calculo_platina_fraccion_simple
        # 7.71 kg para una longitud de 304.8 mm (1 ft).
        assert calcular_peso_perfil("PL 1 / 2 X 10", 304.8) == 7.71

def test_calculo_platina_decimal_thickness(app):
    """
    Prueba el cálculo de peso para un perfil de platina (PL) con espesor decimal.
    Esta prueba debe fallar antes de la corrección del regex.
    """
    with app.app_context():
        # Perfil: PL0.5X10
        # Espesor = 0.5 in, Ancho = 10 in
        # Peso (lb/ft) = 0.5 * 10 * 3.4 = 17 lb/ft
        # Longitud: 304.8 mm (1 ft)
        # Peso esperado (kg) = 17 lb * 0.453592 kg/lb = 7.711... kg
        # El valor esperado es 7.71
        assert calcular_peso_perfil("PL0.5X10", 304.8) == 7.71
