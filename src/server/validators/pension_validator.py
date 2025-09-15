import re
import pytesseract
from rapidfuzz import fuzz, process
from datetime import datetime, timedelta
from PIL import Image

# ==============================
# Utilidades de normalización
# ==============================

def normalizar_texto(texto: str) -> str:
    return (
        texto.lower()
        .strip()
        .replace("\u00A0", " ")
        .encode("ascii", "ignore")
        .decode("utf-8")
    )

def limpiar_cedula(cedula: str) -> str:
    return re.sub(r"\D", "", cedula or "")

# ==============================
# Validar documento Pensión
# ==============================

def validar_pension(file_path, nombre_esperado, cedula_limpia):
    # --- OCR
    texto_pension = pytesseract.image_to_string(Image.open(file_path), lang="spa")
    texto_pension = texto_pension.replace("\u00A0", " ")
    
    # Normalizaciones
    nombre_norm = normalizar_texto(nombre_esperado)
    cedula_norm = limpiar_cedula(cedula_limpia)
    texto_plano = normalizar_texto(texto_pension)
    texto_tokens = re.sub(r"[^a-z0-9\s]", " ", texto_plano).split()

    # --- Buscar nombre
    nombre_encontrado = False
    similitud = 0
    candidato = None

    # Sliding windows
    ventanas = []
    for i in range(len(texto_tokens)):
        for size in range(2, 6):
            if i + size <= len(texto_tokens):
                ventanas.append(" ".join(texto_tokens[i:i+size]))

    if ventanas:
        mejor_match = process.extractOne(nombre_norm, ventanas, scorer=fuzz.ratio)
        if mejor_match:
            candidato, similitud = mejor_match[0], mejor_match[1] / 100
            if similitud > 0.55:
                nombre_encontrado = True

    # --- Validar cédula
    posibles_cedulas = [re.sub(r"\D", "", m) for m in re.findall(r"\d{7,12}", texto_pension)]
    cedula_encontrada = cedula_norm in posibles_cedulas

    # --- Validar fecha
    fecha_detectada, fecha_valida, diff_dias = detectar_fecha(texto_plano)

    return {
        "nombreEncontrado": nombre_encontrado,
        "similitudNombre": similitud,
        "cedulaEncontrada": cedula_encontrada,
        "fechaDetectada": fecha_detectada,
        "fechaValida": fecha_valida,
        "diffDias": diff_dias,
        "texto": texto_pension,
    }

# ==============================
# Validar documento Protección
# ==============================

def validar_proteccion(file_path, nombre_esperado, cedula_limpia):
    texto_prot = pytesseract.image_to_string(Image.open(file_path), lang="spa")
    texto_prot = texto_prot.replace("\u00A0", " ")
    
    nombre_norm = normalizar_texto(nombre_esperado)
    cedula_norm = limpiar_cedula(cedula_limpia)
    texto_plano = normalizar_texto(texto_prot)

    # Nombre
    nombre_info = validar_nombre_proteccion(texto_plano, nombre_norm)
    # Cédula
    cedula_info = validar_cedula_proteccion(texto_prot, cedula_norm)
    # Fecha
    fecha_info = detectar_fecha(texto_plano)
    # Palabras clave
    validaciones_proteccion = validar_especificos_proteccion(texto_plano)

    return {
        "nombreEncontrado": nombre_info["encontrado"],
        "similitudNombre": nombre_info["similitud"],
        "cedulaEncontrada": cedula_info["encontrada"],
        "cedulasDetectadas": cedula_info["cedulas"],
        "fechaDetectada": fecha_info[0],
        "fechaValida": fecha_info[1],
        "diffDias": fecha_info[2],
        "esDocumentoProteccion": validaciones_proteccion["esProteccion"],
        "tipoDocumento": validaciones_proteccion["tipoDocumento"],
        "palabrasClave": validaciones_proteccion["palabrasClave"],
        "texto": texto_prot,
    }

# ==============================
# Funciones auxiliares
# ==============================

def validar_nombre_proteccion(texto, nombre_esperado):
    palabras = texto.split()
    ventanas = [" ".join(palabras[i:i+3]) for i in range(len(palabras)-2)]
    mejor_match = process.extractOne(nombre_esperado, ventanas, scorer=fuzz.ratio)

    similitud = mejor_match[1] / 100 if mejor_match else 0
    return {"encontrado": similitud > 0.55, "similitud": similitud, "candidato": mejor_match[0] if mejor_match else None}

def validar_cedula_proteccion(texto, cedula_esperada):
    patrones = re.findall(r"\d{7,12}", texto)
    cedulas = list(set([re.sub(r"\D", "", c) for c in patrones]))
    return {"encontrada": cedula_esperada in cedulas, "cedulas": cedulas}

def detectar_fecha(texto):
    re_num = re.compile(r"(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})")
    re_text = re.compile(r"(\d{1,2})\s*de\s*(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)\s*de\s*(\d{2,4})", re.I)

    meses = {
        "enero": 1, "febrero": 2, "marzo": 3, "abril": 4,
        "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
        "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12
    }

    hoy = datetime.today()
    fecha_detectada = None
    fecha_valida = False
    diff_dias = None

    for match in re_num.finditer(texto):
        d, m, y = int(match[1]), int(match[2]), int(match[3])
        if y < 100: y += 2000
        try:
            fecha_doc = datetime(y, m, d)
            diff_dias = (hoy - fecha_doc).days
            fecha_detectada = fecha_doc.strftime("%d/%m/%Y")
            fecha_valida = 0 <= diff_dias <= 30
            break
        except: continue

    if not fecha_detectada:
        for match in re_text.finditer(texto):
            d, mes_nombre, y = int(match[1]), match[2].lower(), int(match[3])
            m = meses.get(mes_nombre)
            if not m: continue
            try:
                fecha_doc = datetime(y, m, d)
                diff_dias = (hoy - fecha_doc).days
                fecha_detectada = fecha_doc.strftime("%d/%m/%Y")
                fecha_valida = 0 <= diff_dias <= 30
                break
            except: continue

    return fecha_detectada, fecha_valida, diff_dias

def validar_especificos_proteccion(texto):
    palabras = {
        "proteccion": "proteccion" in texto,
        "fondoPensiones": "fondo" in texto and "pensiones" in texto,
        "obligatorias": "obligatorias" in texto,
        "afiliado": "afiliado" in texto or "afiliada" in texto,
        "constancia": "constancia" in texto,
        "nit": "nit" in texto,
        "expedicion": "expedicion" in texto or "expide" in texto,
    }

    es_proteccion = palabras["proteccion"] or (palabras["fondoPensiones"] and palabras["obligatorias"])
    tipo_doc = "documento_proteccion"
    if es_proteccion:
        if palabras["constancia"]:
            tipo_doc = "constancia_afiliacion"
        elif palabras["afiliado"]:
            tipo_doc = "certificado_pensiones"

    return {"esProteccion": es_proteccion, "tipoDocumento": tipo_doc, "palabrasClave": palabras}

# ==============================
# Wrapper para decidir tipo
# ==============================

def validar_documento_pension(file_path, nombre_esperado, cedula_limpia):
    texto_inicial = pytesseract.image_to_string(Image.open(file_path), lang="spa").lower()
    if "proteccion" in texto_inicial or "fondo de pensiones obligatorias" in texto_inicial:
        return validar_proteccion(file_path, nombre_esperado, cedula_limpia)
    return validar_pension(file_path, nombre_esperado, cedula_limpia)
