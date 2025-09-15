import re
import pytesseract
from difflib import SequenceMatcher
from datetime import datetime
from rapidfuzz import fuzz, process  # más preciso que difflib

# --- Normalizar texto
def normalize_text(s: str) -> str:
    if not s:
        return ""
    return (
        s.lower()
        .replace("\u00a0", " ")
        .replace("\n", " ")
        .strip()
    )

# --- Similitud de cadenas
def similarity(a: str, b: str) -> float:
    return fuzz.ratio(a, b) / 100.0

# --- Validación ARL
def validar_arl(file_path, nombre_esperado, cedula_esperada):
    # --- OCR inicial
    try:
        texto_arl = pytesseract.image_to_string(file_path, lang="spa")
    except Exception as e:
        raise RuntimeError(f"Error OCR: {e}")

    texto_arl = texto_arl.replace("\u00A0", " ")
    texto_plano = normalize_text(texto_arl)

    # --- Normalizar entradas
    nombre_esperado_norm = normalize_text(nombre_esperado)
    cedula_esperada_clean = re.sub(r"\D", "", cedula_esperada)

    # ---------- 1) Validar nombre
    similitud_arl = 0
    nombre_encontrado_arl = False

    # Sliding window
    palabras = texto_plano.split()
    ventanas = []
    for i in range(len(palabras)):
        for size in range(2, 6):
            if i + size <= len(palabras):
                ventanas.append(" ".join(palabras[i:i+size]))

    if nombre_esperado_norm and ventanas:
        mejor_match, score, _ = process.extractOne(nombre_esperado_norm, ventanas, scorer=fuzz.ratio)
        similitud_arl = score / 100.0
        nombre_encontrado_arl = similitud_arl > 0.55

    # ---------- 2) Validar cédula
    cedula_regex = re.compile(r"(\d{1,3}(?:\.\d{3}){1,2}|\d{7,12})")
    posibles_cedulas = [re.sub(r"\D", "", c) for c in cedula_regex.findall(texto_arl)]
    cedula_encontrada_arl = cedula_esperada_clean in posibles_cedulas

    # ---------- 3) Validar fecha expedición
    fecha_detectada = None
    fecha_valida = False
    diff_dias = None

    re_num = re.compile(r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})")

    match_fecha = re_num.search(texto_plano)
    if match_fecha:
        try:
            fecha = match_fecha.group(1)
            for fmt in ["%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y"]:
                try:
                    fecha_doc = datetime.strptime(fecha, fmt).date()
                    hoy = datetime.now().date()
                    diff_dias = (hoy - fecha_doc).days
                    fecha_valida = 0 <= diff_dias <= 30
                    fecha_detectada = fecha_doc.strftime("%d/%m/%Y")
                    break
                except ValueError:
                    continue
        except Exception:
            pass

    # ---------- 4) Clase de riesgo
    riesgo_encontrado = None
    cumple_riesgo = False
    confianza_riesgo = 0

    riesgo_match = re.search(r"clase.*riesgo.*([1-5])", texto_plano)
    if riesgo_match:
        riesgo_encontrado = int(riesgo_match.group(1))
        cumple_riesgo = riesgo_encontrado >= 4
        confianza_riesgo = 0.8

    # ---------- 5) Palabras clave
    palabras_clave = {
        "afiliado": "afiliado" in texto_plano,
        "vinculado": "vinculado" in texto_plano,
        "habilitado": "habilitado" in texto_plano,
        "activo": "activo" in texto_plano,
        "vigente": "vigente" in texto_plano,
        "registra": "registra" in texto_plano,
    }

    # --- Resultado final
    return {
        "nombreEncontrado": nombre_encontrado_arl,
        "similitudNombre": similitud_arl,
        "cedulaEncontrada": cedula_encontrada_arl,
        "fechaDetectada": fecha_detectada,
        "fechaValida": fecha_valida,
        "diffDias": diff_dias,
        "riesgoEncontrado": riesgo_encontrado,
        "cumpleRiesgo": cumple_riesgo,
        "confianzaRiesgo": confianza_riesgo,
        "palabrasClave": palabras_clave,
        "texto": texto_arl,
    }
