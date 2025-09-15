# validators/eps_validator.py
import re
import pytesseract
from PIL import Image
from datetime import datetime
from fuzzywuzzy import fuzz, process

def normalize_text(s: str) -> str:
    if not s:
        return ""
    return (
        s.lower()
        .replace("\u00A0", " ")
        .strip()
    )

def limpiar_digitos(s: str) -> str:
    return re.sub(r"\D", "", s or "")

def validar_eps(file_path: str, nombre_esperado: str, cedula_esperada: str):
    # --- OCR
    texto_eps = pytesseract.image_to_string(Image.open(file_path), lang="spa")
    texto_eps = texto_eps.replace("\u00A0", " ")
    texto_plano = normalize_text(texto_eps)
    texto_for_extraction = re.sub(r"[^a-z0-9\s]", " ", texto_plano)
    texto_for_extraction = re.sub(r"\s+", " ", texto_for_extraction).strip()

    # --- Normalización de entradas
    nombre_norm = normalize_text(nombre_esperado)
    cedula_clean = limpiar_digitos(cedula_esperada)

    # ---------- 1) Extraer nombre (anchor "señor")
    nombre_candidato = None
    anchor_match = re.search(r"\b(?:senor|senora|senor\(a\)|sr|sra)\b", texto_for_extraction)
    if anchor_match:
        idx = anchor_match.end()
        after = texto_for_extraction[idx:].strip()
        stop_words = {"identificado", "identificada", "identificad", "identificacion",
                      "con", "cc", "cedula", "numero", "c", "documento"}
        skip_words = {"el","la","del","de","los","las","y","en","por","a","al"}
        tokens = after.split()
        name_tokens = []
        for t in tokens:
            if t in stop_words:
                break
            if t in skip_words or len(t) <= 1:
                continue
            name_tokens.append(t)
            if len(name_tokens) >= 5:
                break
        if name_tokens:
            nombre_candidato = " ".join(name_tokens)

    # ---------- 2) Sliding windows
    best_candidate = None
    best_rating = 0
    if not nombre_candidato and nombre_norm:
        words = texto_for_extraction.split()
        windows = [" ".join(words[i:i+size]) for i in range(len(words)) for size in range(2,6) if i+size <= len(words)]
        if windows:
            best_candidate, best_rating = process.extractOne(nombre_norm, windows, scorer=fuzz.ratio)

    # ---------- 3) Decidir si nombre coincide
    nombre_encontrado = False
    similitud_nombre = 0
    if nombre_candidato:
        similitud_nombre = fuzz.ratio(nombre_norm, nombre_candidato) / 100
        nombre_encontrado = similitud_nombre > 0.5 or all(tok in nombre_candidato for tok in nombre_norm.split())
    elif best_candidate:
        similitud_nombre = best_rating / 100
        nombre_encontrado = similitud_nombre > 0.55 or all(tok in best_candidate for tok in nombre_norm.split())
    else:
        nombre_encontrado = all(tok in texto_for_extraction for tok in nombre_norm.split())

    # ---------- 4) Validar cédula
    posibles_cedulas = re.findall(r"(\d{1,3}(?:\.\d{3}){1,2}|\d{7,12})", texto_eps)
    posibles_cedulas = [limpiar_digitos(c) for c in posibles_cedulas if c]
    cedula_encontrada = False
    for c in posibles_cedulas:
        if c == cedula_clean:
            cedula_encontrada = True
            break
        if len(c) == len(cedula_clean):
            dif = sum(1 for a, b in zip(c, cedula_clean) if a != b)
            if dif <= 1:  # tolera 1 error OCR
                cedula_encontrada = True
                break

    # ---------- 5) Validar fecha expedición (solo ejemplo simplificado aquí)
    fecha_detectada = None
    fecha_valida = False
    diff_dias = None
    regex_fecha = re.search(r"(\d{1,2})[\/\-](\d{1,2})[\/\-](\d{2,4})", texto_eps)
    if regex_fecha:
        d, m, y = regex_fecha.groups()
        y = "20" + y if len(y) == 2 else y
        try:
            fecha_doc = datetime(int(y), int(m), int(d))
            hoy = datetime.today().replace(hour=0, minute=0, second=0, microsecond=0)
            diff_dias = (hoy - fecha_doc).days
            fecha_valida = 0 <= diff_dias <= 30
            fecha_detectada = fecha_doc.strftime("%d/%m/%Y")
        except Exception:
            pass

    # ---------- 6) Palabras clave
    palabras_clave = {
        "afiliado": "afiliado" in texto_plano,
        "activo": "activo" in texto_plano,
        "vinculado": "vinculado" in texto_plano,
        "habilitado": "habilitado" in texto_plano,
        "vigente": "vigente" in texto_plano,
    }
    estado_match = re.search(r"estado\s+de\s+la\s+afiliaci[oó]n[:\s]+([a-z]+)", texto_eps, re.I)
    estado_afiliacion = estado_match.group(1).upper() if estado_match else None

    return {
        "nombreEncontrado": nombre_encontrado,
        "similitudNombre": similitud_nombre,
        "cedulaEncontrada": cedula_encontrada,
        "fechaDetectada": fecha_detectada,
        "fechaValida": fecha_valida,
        "diffDias": diff_dias,
        "estadoAfiliacion": estado_afiliacion,
        "palabrasClave": palabras_clave,
        "texto": texto_eps,
    }
