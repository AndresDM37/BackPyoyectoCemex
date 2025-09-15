import pytesseract
from PIL import Image
import re
import unicodedata
from rapidfuzz import fuzz


def normalize_text(s: str) -> str:
    if not s:
        return ""
    s = s.lower()
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")  # quitar acentos
    s = re.sub(r"[^a-z0-9\s]", " ", s)  # limpiar símbolos raros
    s = re.sub(r"\s+", " ", s).strip()
    return s


def validar_cedula(file_path: str, cedula: str, nombre_conductor: str):
    try:
        print("🚀 Iniciando validación de cédula...")

        # === OCR ===
        texto_cedula = pytesseract.image_to_string(Image.open(file_path), lang="spa")
        print("✅ OCR completado")
        print("📝 Longitud del texto:", len(texto_cedula))
        print("🔍 OCR bruto:", texto_cedula[:200])

        # Si el texto es muy corto, probar con inglés
        if len(texto_cedula) < 10:
            print("⚠️ Texto muy corto, intentando con inglés...")
            texto2 = pytesseract.image_to_string(Image.open(file_path), lang="eng")
            if len(texto2) > len(texto_cedula):
                texto_cedula = texto2
                print("✅ Inglés funcionó mejor")

        # Si sigue corto, probar con español+inglés
        if len(texto_cedula) < 10:
            print("⚠️ Aún muy corto, intentando con spa+eng...")
            texto3 = pytesseract.image_to_string(Image.open(file_path), lang="spa+eng")
            if len(texto3) > len(texto_cedula):
                texto_cedula = texto3
                print("✅ Idioma combinado funcionó mejor")

        # === NORMALIZACIÓN ===
        texto_plano_cedula = normalize_text(texto_cedula)
        print("🧹 Texto normalizado:", texto_plano_cedula[:100])

        # === VALIDACIÓN DE CÉDULA ===
        cedula_limpia = re.sub(r"\D", "", cedula)
        print("🎯 Buscando cédula:", cedula_limpia)

        numeros_en_texto = [re.sub(r"[\.,\s]", "", n) for n in re.findall(r"[\d\.\,]+", texto_cedula)]
        numeros_largos = [n for n in numeros_en_texto if len(n) >= 6]

        print("🔢 Números largos:", numeros_largos)

        cedula_encontrada = False
        mejor_coincidencia = ""
        tipo_coincidencia = ""

        # 1. Exacta
        if cedula_limpia in numeros_largos:
            cedula_encontrada = True
            mejor_coincidencia = cedula_limpia
            tipo_coincidencia = "exacta"

        # 2. Contenida
        if not cedula_encontrada:
            for numero in numeros_largos:
                if cedula_limpia in numero or numero in cedula_limpia:
                    cedula_encontrada = True
                    mejor_coincidencia = numero
                    tipo_coincidencia = "contenida"
                    break

        # 3. Fuzzy
        if not cedula_encontrada:
            for numero in numeros_largos:
                similitud = fuzz.ratio(numero, cedula_limpia) / 100
                if similitud > 0.65:
                    cedula_encontrada = True
                    mejor_coincidencia = numero
                    tipo_coincidencia = f"fuzzy ({int(similitud*100)}%)"
                    break

        # 4. Longitud cercana
        if not cedula_encontrada:
            for numero in numeros_largos:
                if abs(len(numero) - len(cedula_limpia)) <= 2 and numero.startswith(cedula_limpia[:4]):
                    cedula_encontrada = True
                    mejor_coincidencia = numero
                    tipo_coincidencia = "longitud cercana con prefijo igual"
                    break

        # === VALIDACIÓN DE NOMBRE ===
        nombre_esperado = normalize_text(nombre_conductor)
        palabras_nombre = [p for p in nombre_esperado.split() if len(p) >= 3]

        palabras_encontradas = []
        for palabra in palabras_nombre:
            if palabra in texto_plano_cedula:
                palabras_encontradas.append({"palabra": palabra, "tipo": "exacta"})
                continue
            if len(palabra) >= 4 and palabra[:4] in texto_plano_cedula:
                palabras_encontradas.append({"palabra": palabra, "tipo": "prefijo"})
                continue
            for palabra_texto in texto_plano_cedula.split():
                if len(palabra_texto) >= 3:
                    similitud = fuzz.ratio(palabra, palabra_texto) / 100
                    if similitud > 0.6:
                        palabras_encontradas.append({"palabra": palabra, "tipo": f"fuzzy ({int(similitud*100)}%)"})
                        break

        porcentaje_palabras = len(palabras_encontradas) / len(palabras_nombre) if palabras_nombre else 0
        nombre_encontrado = porcentaje_palabras > 0.25 or len(palabras_encontradas) >= 1

        resultado = {
            "textoCedula": texto_cedula,
            "textoPlanoCedula": texto_plano_cedula,
            "coincidencias": {
                "cedula": cedula_encontrada,
                "nombre": nombre_encontrado
            },
            "metricas": {
                "similitudNombre": porcentaje_palabras,
                "palabrasEncontradas": len(palabras_encontradas),
                "totalPalabrasEsperadas": len(palabras_nombre),
                "porcentajePalabras": porcentaje_palabras,
                "longitudTextoOCR": len(texto_cedula)
            },
            "debug": {
                "nombreEsperado": nombre_esperado,
                "palabrasNombre": palabras_nombre,
                "palabrasEncontradasDetalle": palabras_encontradas,
                "cedulaLimpia": cedula_limpia,
                "numerosEncontrados": numeros_largos,
                "mejorCoincidenciaCedula": mejor_coincidencia,
                "tipoCoincidencia": tipo_coincidencia,
            }
        }

        print("✅ Validación completada")
        return resultado

    except Exception as e:
        print("❌ Error en validación:", str(e))
        return {
            "textoCedula": "",
            "textoPlanoCedula": "",
            "coincidencias": {"cedula": False, "nombre": False},
            "metricas": {
                "similitudNombre": 0,
                "palabrasEncontradas": 0,
                "totalPalabrasEsperadas": 0,
                "porcentajePalabras": 0,
                "longitudTextoOCR": 0
            },
            "debug": {"error": str(e)}
        }
