import os
import shutil
from fastapi import FastAPI, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware

# Importar validadores
from validators.formato_validator import validar_formato_transportador
from validators.cedula_validator import validar_cedula
from validators.eps_validator import validar_eps
# from validators.license_validator import validar_licencia
from validators.arl_validator import validar_arl     
from validators.pension_validator import validar_documento_pension

UPLOAD_DIR = "./uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/validar")
async def validar_documentos(
    # Archivos
    formatoCreacion: UploadFile | None = None,
    documento: UploadFile | None = None,          # Cédula
    licenciaConduccion: UploadFile | None = None,
    certificadoEPS: UploadFile | None = None,
    certificadoARL: UploadFile | None = None,
    certificadoPension: UploadFile | None = None,

    # Datos del formulario
    codigoTransportador: str = Form(None),
    nombreTransportador: str = Form(None),
    cedula: str = Form(None),
    nombreConductor: str = Form(None),
):
    resultados = {}

    # 1) Guardar temporal y validar formato transportador
    if formatoCreacion:
        file_path = os.path.join(UPLOAD_DIR, formatoCreacion.filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(formatoCreacion.file, buffer)

        resultados["formato"] = validar_formato_transportador(
            file_path,
            codigoTransportador,
            nombreTransportador,
            cedula,
            nombreConductor
        )

    # 2) Guardar temporal y validar cédula
    if documento:
        file_path = os.path.join(UPLOAD_DIR, documento.filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(documento.file, buffer)

        resultados["cedula"] = validar_cedula(
            file_path,
            cedula,
            nombreConductor
        )

    # 3) Validar licencia de conducción
    if licenciaConduccion:
        file_path = os.path.join(UPLOAD_DIR, licenciaConduccion.filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(licenciaConduccion.file, buffer)

        # resultados["licencia"] = validar_licencia(file_path, cedula, nombreConductor)

    # 4) Validar EPS
    if certificadoEPS:
        file_path = os.path.join(UPLOAD_DIR, certificadoEPS.filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(certificadoEPS.file, buffer)

        resultados["eps"] = validar_eps(file_path, nombreConductor, cedula)

    # 5) Validar ARL
    if certificadoARL:
        file_path = os.path.join(UPLOAD_DIR, certificadoARL.filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(certificadoARL.file, buffer)

        resultados["arl"] = validar_arl(file_path, nombreConductor, cedula)

    # 6) Validar pensión
    if certificadoPension:
        file_path = os.path.join(UPLOAD_DIR, certificadoPension.filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(certificadoPension.file, buffer)

        resultados["pension"] = validar_documento_pension(file_path, nombreConductor, cedula)

    return {"resultados": resultados}
