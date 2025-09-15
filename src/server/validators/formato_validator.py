import re
import pytesseract
from difflib import SequenceMatcher
from PIL import Image

# --- Normalizador de texto ---
def normalize_text(s: str) -> str:
    if not s:
        return ""
    return (
        s.lower()
        .strip()
        .replace("\n", " ")
        .encode("ascii", "ignore")
        .decode("utf-8")
    )

# --- Buscar coincidencia aproximada (fuzzy) ---
def fuzzy_find(texto_plano: str, termino: str, threshold: float = 0.7):
    palabras = texto_plano.split(" ")
    termino_len = len(termino.split(" "))
    for i in range(len(palabras)):
        ventana = " ".join(palabras[i : i + termino_len + 2])
        score = SequenceMatcher(None, ventana, termino).ratio()
        if score >= threshold:
            return {"match": ventana, "score": score}
    return None

# --- Validador principal ---
def validar_formato_transportador(
    file_path: str,
    codigo_transportador_input: str,
    nombre_transportador_input: str,
    cedula_conductor_input: str,
    nombre_conductor_input: str,
):
    try:
        # 1) OCR
        texto = pytesseract.image_to_string(Image.open(file_path), lang="spa")
        texto_plano = normalize_text(texto)

        # --- 1) Validar código transportador ---
        codigos_raw = re.findall(r".{0,5}\d{5,10}.{0,5}", texto) or []
        codigos = [re.sub(r"\D", "", c) for c in codigos_raw]
        codigo_encontrado = (
            next((c for c in codigos if c == codigo_transportador_input), None)
        )

        # --- 2) Validar transportador (razón social) ---
        transportador_encontrado = False
        similitud_transportador = 0
        if nombre_transportador_input:
            nombre_norm = normalize_text(nombre_transportador_input)
            encontrado = fuzzy_find(texto_plano, nombre_norm, 0.65)
            if encontrado:
                transportador_encontrado = True
                similitud_transportador = encontrado["score"]

        # --- 3) Validar cédula del conductor ---
        cedulas_raw = re.findall(r"\d[\d'.-]{6,15}\d", texto) or []
        cedulas = [re.sub(r"\D", "", c) for c in cedulas_raw]
        cedula_encontrada = cedula_conductor_input in cedulas

        # --- 4) Validar nombre del conductor ---
        conductor_encontrado = False
        similitud_conductor = 0
        if nombre_conductor_input:
            nombre_conductor_norm = normalize_text(nombre_conductor_input)
            encontrado = fuzzy_find(texto_plano, nombre_conductor_norm, 0.65)
            if encontrado:
                conductor_encontrado = True
                similitud_conductor = encontrado["score"]

        return {
            "codigoTransportador": {
                "esperado": codigo_transportador_input,
                "encontrado": codigo_encontrado,
                "coincide": bool(codigo_encontrado),
            },
            "transportador": {
                "esperado": nombre_transportador_input,
                "similitud": similitud_transportador,
                "coincide": transportador_encontrado,
            },
            "conductor": {
                "cedula": {
                    "esperado": cedula_conductor_input,
                    "encontrado": cedulas,
                    "coincide": cedula_encontrada,
                },
                "nombre": {
                    "esperado": nombre_conductor_input,
                    "similitud": similitud_conductor,
                    "coincide": conductor_encontrado,
                },
            },
            "textoOCR": texto,
        }

    except Exception as e:
        return {"error": str(e), "textoOCR": ""}
