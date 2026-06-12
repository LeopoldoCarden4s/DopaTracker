import os
import sys
import re
from datetime import datetime
from dotenv import load_dotenv
from groq import Groq
from notion_client import Client

# ─── CONFIGURACION ───────────────────────────────────────────────
load_dotenv()

GROQ_API_KEY   = os.getenv("GROQ_API_KEY")
NOTION_TOKEN   = os.getenv("NOTION_TOKEN")
MATERIAS_DB_ID = os.getenv("MATERIAS_DB_ID")
SESIONES_DB_ID = os.getenv("SESIONES_DB_ID")

if not all([GROQ_API_KEY, NOTION_TOKEN, MATERIAS_DB_ID, SESIONES_DB_ID]):
    print("ERROR: Faltan variables en el archivo .env")
    sys.exit(1)

groq_client = Groq(api_key=GROQ_API_KEY)
notion      = Client(auth=NOTION_TOKEN)

# ─── PROMPTS POR TIPO DE MATERIA ─────────────────────────────────
PROMPTS_POR_TIPO = {
    "Tecnica": """
MODO TECNICO ACTIVO:
Cada mision debe terminar con un output ejecutable concreto:
un script que corra, un calculo verificable o un ejercicio resuelto.
Si la mision no tiene output medible, no es valida.
Prioriza ejecucion sobre explicacion.
Nunca termines una sesion tecnica sin un artefacto concreto producido.
""",
    "Teorica": """
MODO TEORICO ACTIVO:
Cada mision debe terminar con el Estratega capaz de explicar
el concepto sin notas en menos de 2 minutos.
Si el concepto no conecta con una aplicacion real de negocio, no esta dominado.
La prueba de dominio es poder explicarlo, no poder repetirlo.
""",
    "Mixta": """
MODO MIXTO ACTIVO:
Alterna sesiones: una de concepto seguida de una de aplicacion.
Nunca dos sesiones teoricas consecutivas.
Cada concepto debe tener un ejercicio de aplicacion antes de avanzar.
El ciclo es: entender, aplicar, verificar.
"""
}

# ─── PROMPT MAESTRO ──────────────────────────────────────────────
AUDITOR_BASE = """
Eres el Auditor de un sistema de aprendizaje de alto rendimiento.
Tu unico rol es analizar, dictar misiones y estructurar sintesis.
No eres un tutor. No explicas sin que te lo pidan.

PERFIL DEL ESTRATEGA:
- Perfil cognitivo: ENTP
- Aprende por friccion tecnica y resolucion de problemas reales
- Entiende conceptos rapido pero descuida la ejecucion tecnica
- Frenos: procrastinacion optimista, teoria sin aplicacion,
  errores de sintaxis por falta de atencion al detalle
- Objetivo: Ingeniero Comercial especializado en Estrategia
  de Datos y Comportamiento Economico
- Norte: maestria tecnica nivel 10

REGLAS FIJAS:
1. Al recibir el contexto, dicta la mision del dia.
   Sin introduccion, sin relleno. Directo.

2. Si hay error activo o patron de error, el primer ejercicio
   lo confronta directamente. Sin excepcion.

3. Si hay URGENCIA de evaluacion, esa es la prioridad absoluta.
   Ignora el orden normal del silabo.

4. Cuando recibas la sintesis estructurada devuelve
   EXACTAMENTE este bloque sin agregar nada mas:

SESION: [FECHA]
MATERIA: [nombre]
NIVEL ENTRADA -> SALIDA: [X -> Y]
HITO LOGRADO: [descripcion concreta en una oracion]
ERROR DETECTADO: [naturaleza del error o Ninguno nuevo]
PROXIMA MISION: [condicion especifica y medible]
NOTA AUDITOR: [fragilidad, consolidacion, alerta o patron]

5. Para asignar el nivel de salida usa la RUBRICA DE NIVELES
   del silabo. Nivel real demostrado hoy, no el aspiracional.

6. Nunca des teoria sin mision de ejecucion asociada.

7. Nivel que subio mas de 1.5 puntos en una sesion = NIVEL FRAGIL.

8. Directo y breve. Sin motivacion. Sin relleno.
"""

# ─── LLAMADA A GROQ ──────────────────────────────────────────────
def llamar_ia(mensajes: list) -> str:
    try:
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=mensajes,
            max_tokens=1200
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error llamando a Groq: {e}"

# ─── PARSEAR SAVE GAME ───────────────────────────────────────────
def parsear_save_game(texto: str) -> dict:
    def extraer(etiqueta):
        patron = rf"[\*\[]*{etiqueta}[\*\]]*:\s*(.+)"
        match  = re.search(patron, texto, re.IGNORECASE)
        if match:
            return match.group(1).replace("**","").replace("[","").replace("]","").strip()
        return ""

    nivel_entrada = None
    nivel_salida  = None
    nivel_raw = extraer(r"NIVEL ENTRADA.*?SALIDA")
    if not nivel_raw:
        nivel_raw = extraer(r"NIVEL ENTRADA")
    if nivel_raw:
        nums = re.findall(r"\d+(?:\.\d+)?", nivel_raw)
        if len(nums) >= 2:
            try:
                nivel_entrada = float(nums[0])
                nivel_salida  = float(nums[1])
            except ValueError:
                pass

    return {
        "hito_logrado":    extraer("HITO LOGRADO"),
        "error_detectado": extraer("ERROR DETECTADO"),
        "proxima_mision":  extraer("PROXIMA MISION"),
        "nota_auditor":    extraer("NOTA AUDITOR"),
        "nivel_entrada":   nivel_entrada,
        "nivel_salida":    nivel_salida,
    }

# ─── CALCULAR URGENCIA ───────────────────────────────────────────
def calcular_urgencia(evaluaciones: str, semana_actual) -> str:
    if not evaluaciones or not semana_actual:
        return ""
    try:
        sa      = int(semana_actual)
        semanas = re.findall(r'[Ss]emana\s+(\d+)', evaluaciones)
        alertas = []
        for s in semanas:
            diff = int(s) - sa
            if 0 <= diff <= 1:
                alertas.append("EVALUACION ESTA SEMANA O LA PROXIMA — MAXIMA PRIORIDAD")
            elif 2 <= diff <= 3:
                alertas.append(f"EVALUACION EN {diff} SEMANAS — PRIORIDAD ALTA")
        return " | ".join(alertas)
    except:
        return ""

# ─── BUSCAR MATERIA ──────────────────────────────────────────────
def buscar_materia(nombre: str):
    try:
        res = notion.databases.query(
            database_id=MATERIAS_DB_ID,
            filter={"property": "Nombre", "title": {"contains": nombre}}
        )
        if not res["results"]:
            return None

        page  = res["results"][0]
        props = page["properties"]

        def txt(p):
            items = props.get(p, {}).get("rich_text", [])
            return items[0]["text"]["content"] if items else ""
        def ttl(p):
            items = props.get(p, {}).get("title", [])
            return items[0]["text"]["content"] if items else ""
        def num(p):
            return props.get(p, {}).get("number")
        def sel(p):
            s = props.get(p, {}).get("select")
            return s["name"] if s else ""

        return {
            "id":               page["id"],
            "nombre":           ttl("Nombre"),
            "categoria":        sel("Categoria"),
            "tipo":             sel("Tipo Materia"),
            "nivel":            num("Nivel Actual"),
            "error_activo":     txt("Error Activo"),
            "patron_error":     txt("Patron Error"),
            "prox_mision":      txt("Proxima Mision"),
            "silabo":           txt("Silabo"),
            "evaluaciones":     txt("Evaluaciones"),
            "semana_actual":    num("Semana Actual"),
            "semanas_total":    num("Semanas Total"),
            "temas_dominados":  txt("Temas Dominados"),
            "temas_pendientes": txt("Temas Pendientes"),
            "objetivo_semana":  txt("Objetivo Semana"),
        }
    except Exception as e:
        print(f"Error buscando materia: {e}")
        return None

# ─── ULTIMAS SESIONES ────────────────────────────────────────────
def obtener_ultimas_sesiones(materia_id: str, limite: int = 3):
    try:
        res = notion.databases.query(
            database_id=SESIONES_DB_ID,
            filter={"property": "Materia", "relation": {"contains": materia_id}},
            sorts=[{"property": "Fecha", "direction": "descending"}],
            page_size=limite
        )
        sesiones = []
        for page in res["results"]:
            props = page["properties"]
            def txt(p):
                items = props.get(p, {}).get("rich_text", [])
                return items[0]["text"]["content"] if items else ""
            def fch(p):
                d = props.get(p, {}).get("date")
                return d["start"] if d else ""
            def num(p):
                return props.get(p, {}).get("number")
            sesiones.append({
                "fecha":         fch("Fecha"),
                "hito":          txt("Hito Logrado"),
                "error":         txt("Error Detectado"),
                "sintesis":      txt("Sintesis"),
                "nivel_entrada": num("Nivel Entrada"),
                "nivel_salida":  num("Nivel Salida"),
                "duracion":      num("Duracion Min"),
                "dificultad":    num("Dificultad"),
                "temas_vistos":  txt("Temas Vistos"),
            })
        return sesiones
    except Exception as e:
        print(f"Error obteniendo sesiones: {e}")
        return []

# ─── GUARDAR SESION ──────────────────────────────────────────────
def guardar_sesion(materia_id, materia_nombre, save_game,
                   campos, duracion, dificultad, temas_vistos, conexiones):
    today = datetime.now().strftime("%Y-%m-%d")
    props = {
        "Nombre":  {"title":    [{"text": {"content": f"{materia_nombre} - {today}"}}]},
        "Fecha":   {"date":     {"start": today}},
        "Materia": {"relation": [{"id": materia_id}]},
        "Sintesis":{"rich_text":[{"text": {"content": save_game[:1999]}}]},
    }
    if campos["hito_logrado"]:
        props["Hito Logrado"]    = {"rich_text": [{"text": {"content": campos["hito_logrado"][:1999]}}]}
    if campos["error_detectado"]:
        props["Error Detectado"] = {"rich_text": [{"text": {"content": campos["error_detectado"][:1999]}}]}
    if campos["proxima_mision"]:
        props["Proxima Mision"]  = {"rich_text": [{"text": {"content": campos["proxima_mision"][:1999]}}]}
    if campos["nivel_entrada"] is not None:
        props["Nivel Entrada"]   = {"number": float(campos["nivel_entrada"])}
    if campos["nivel_salida"] is not None:
        props["Nivel Salida"]    = {"number": float(campos["nivel_salida"])}
    if duracion:
        props["Duracion Min"]    = {"number": duracion}
    if dificultad:
        props["Dificultad"]      = {"number": dificultad}
    if temas_vistos:
        props["Temas Vistos"]    = {"rich_text": [{"text": {"content": temas_vistos[:1999]}}]}
    if conexiones:
        props["Conexiones"]      = {"rich_text": [{"text": {"content": conexiones[:1999]}}]}
    notion.pages.create(parent={"database_id": SESIONES_DB_ID}, properties=props)

# ─── ACTUALIZAR MATERIA ──────────────────────────────────────────
def actualizar_materia(materia_id, error, patron_error,
                       prox_mision, nivel_salida,
                       temas_dominados, temas_pendientes):
    props = {"Ultima Sesion": {"date": {"start": datetime.now().strftime("%Y-%m-%d")}}}
    if prox_mision:
        props["Proxima Mision"]   = {"rich_text": [{"text": {"content": prox_mision[:1999]}}]}
    if error:
        props["Error Activo"]     = {"rich_text": [{"text": {"content": error[:1999]}}]}
    if patron_error:
        props["Patron Error"]     = {"rich_text": [{"text": {"content": patron_error[:1999]}}]}
    if nivel_salida is not None:
        props["Nivel Actual"]     = {"number": float(nivel_salida)}
    if temas_dominados:
        props["Temas Dominados"]  = {"rich_text": [{"text": {"content": temas_dominados[:1999]}}]}
    if temas_pendientes:
        props["Temas Pendientes"] = {"rich_text": [{"text": {"content": temas_pendientes[:1999]}}]}
    notion.pages.update(page_id=materia_id, properties=props)

# ─── LISTAR MATERIAS ─────────────────────────────────────────────
def listar_materias():
    try:
        res = notion.databases.query(database_id=MATERIAS_DB_ID)
        print("\nTUS MATERIAS:\n")
        for page in res["results"]:
            props  = page["properties"]
            titems = props.get("Nombre", {}).get("title", [])
            nombre = titems[0]["text"]["content"] if titems else "Sin nombre"
            nivel  = props.get("Nivel Actual", {}).get("number")
            cat    = props.get("Categoria", {}).get("select")
            semana = props.get("Semana Actual", {}).get("number")
            sem_str= f" | Sem {int(semana)}" if semana else ""
            print(f"  * {nombre} - Nivel {nivel or '?'}/10 [{cat['name'] if cat else ''}]{sem_str}")
        print()
    except Exception as e:
        print(f"Error listando materias: {e}")

# ─── COMANDO ACTUALIZACION ───────────────────────────────────────
def cmd_actualizacion():
    print("\n" + "="*55)
    print("        ACTUALIZACION SEMANAL")
    print("="*55)
    print("Actualiza la semana y objetivo de una materia.")
    print("Escribe 'cancelar' en cualquier momento.\n")

    # Elegir materia
    nombre_input = input("Que materia quieres actualizar? ").strip()
    if nombre_input.lower() == "cancelar":
        return

    materia = buscar_materia(nombre_input)
    if not materia:
        print(f"No encontre '{nombre_input}'. Escribe 'materias' para ver los nombres exactos.")
        return

    print(f"\nMateria encontrada: {materia['nombre']}")
    print(f"Semana actual registrada: {materia['semana_actual'] or 'sin registro'}")
    print(f"Semanas totales: {materia['semanas_total'] or 'sin registro'}\n")

    # Pedir semana actual
    semana_nueva = 0
    while not semana_nueva:
        try:
            s = int(input("En que semana vas ahora? (numero): ").strip())
            if s > 0:
                semana_nueva = s
            else:
                print("   Numero mayor a 0.")
        except ValueError:
            print("   Solo el numero.")

    # Pedir objetivo de la semana
    print("\nCual es tu objetivo para esta semana?")
    print("(lo que quieres lograr o dominar antes del domingo)")
    lineas = []
    while True:
        linea = input("  > ").strip()
        if linea == "" and lineas:
            break
        if linea:
            lineas.append(linea)
    objetivo_nuevo = " ".join(lineas)

    # Consultar a Groq qué debería estar viendo según el sílabo
    print("\nAnalizando silabo...\n")

    prompt_analisis = f"""
Eres el Auditor de un sistema de aprendizaje.
Analiza el silabo de esta materia y responde directamente.
Sin introduccion, sin relleno.

MATERIA: {materia['nombre']}
SEMANA ACTUAL: {semana_nueva} de {materia['semanas_total'] or '?'}
EVALUACIONES: {materia['evaluaciones'] or 'sin registro'}
OBJETIVO DEL ESTUDIANTE ESTA SEMANA: {objetivo_nuevo}
NIVEL ACTUAL: {materia['nivel'] or 'sin registro'}/10

SILABO COMPLETO:
{materia['silabo'] or 'sin silabo registrado'}

Responde con este formato exacto:

SEMANA {semana_nueva} — QUE DEBERIAS ESTAR VIENDO:
[temas y contenidos que corresponden a esta semana segun el silabo]

EVALUACIONES PROXIMAS:
[evaluaciones que se acercan con cuantas semanas faltan]

ALINEACION DEL OBJETIVO:
[si el objetivo del estudiante esta bien alineado con el silabo
o si deberia ajustarlo, en una oracion directa]

FOCO RECOMENDADO ESTA SEMANA:
[una sola prioridad clara y especifica para maximizar el avance]
"""

    mensajes = [
        {"role": "system", "content": "Eres el Auditor. Directo y breve. Sin relleno."},
        {"role": "user",   "content": prompt_analisis}
    ]
    analisis = llamar_ia(mensajes)
    print(analisis)

    # Actualizar Notion
    print("\nActualizando Notion...")
    try:
        props = {
            "Semana Actual":   {"number": semana_nueva},
            "Objetivo Semana": {"rich_text": [{"text": {"content": objetivo_nuevo[:1999]}}]},
        }
        notion.pages.update(page_id=materia["id"], properties=props)
        print(f"\n✅ Actualizado correctamente.")
        print(f"   Materia:        {materia['nombre']}")
        print(f"   Semana actual:  {semana_nueva}")
        print(f"   Objetivo:       {objetivo_nuevo}")
    except Exception as e:
        print(f"\n❌ Error al actualizar Notion: {e}")

    print("\n" + "="*55 + "\n")

# ─── CONSTRUIR CONTEXTO ──────────────────────────────────────────
def construir_contexto(materia: dict, sesiones: list) -> str:
    urgencia = calcular_urgencia(materia["evaluaciones"], materia["semana_actual"])

    progreso = ""
    if materia["semana_actual"] and materia["semanas_total"]:
        restantes = int(materia["semanas_total"]) - int(materia["semana_actual"])
        progreso  = f"Semana {int(materia['semana_actual'])} de {int(materia['semanas_total'])} — {restantes} restantes"

    historial = "\nULTIMAS SESIONES:\n"
    if sesiones:
        for s in sesiones:
            niv = f"{s['nivel_entrada']} -> {s['nivel_salida']}" if s['nivel_entrada'] and s['nivel_salida'] else "sin registro"
            dur = f"{s['duracion']} min" if s['duracion'] else "?"
            dif = f"{s['dificultad']}/10" if s['dificultad'] else "?"
            hito= s['hito'] or s['sintesis'][:150] or "sin registro"
            err = s['error'] or "ninguno"
            tem = s['temas_vistos'] or "sin registro"
            historial += f"""
[{s['fecha']}] Nivel: {niv} | {dur} | Dif: {dif}
  Temas: {tem}
  Hito: {hito}
  Error: {err}
"""
    else:
        historial += "  Sin sesiones previas.\n"

    return f"""
{"="*55}
CONTEXTO — {materia['nombre'].upper()}
{"="*55}
CATEGORIA: {materia['categoria']} | TIPO: {materia['tipo'] or 'sin definir'}
PROGRESO: {progreso or 'sin registro'}
NIVEL ACTUAL: {materia['nivel'] or 'sin registro'}/10
{("URGENCIA: " + urgencia) if urgencia else ""}

EVALUACIONES:
{materia['evaluaciones'] or 'sin registro'}

OBJETIVO ESTA SEMANA:
{materia['objetivo_semana'] or 'sin registro'}

TEMAS DOMINADOS:
{materia['temas_dominados'] or 'sin registro'}

TEMAS PENDIENTES:
{materia['temas_pendientes'] or 'sin registro'}

ERROR ACTIVO: {materia['error_activo'] or 'ninguno'}
PATRON ERROR HISTORICO: {materia['patron_error'] or 'sin patron aun'}
MISION ANTERIOR: {materia['prox_mision'] or 'sin registro'}

SILABO Y RUBRICA DE NIVELES:
{materia['silabo'] or 'SILABO VACIO — usar nivel actual y categoria'}
{historial}
{"="*55}
Dicta la mision de hoy basandote en TODO el contexto.
{("PRIORIDAD: " + urgencia) if urgencia else ""}
{"="*55}
"""

# ─── SINTESIS ESTRUCTURADA ───────────────────────────────────────
def recopilar_sintesis():
    print("\n" + "="*55)
    print("SINTESIS — responde cada pregunta y presiona Enter")
    print("="*55 + "\n")

    def pedir(pregunta):
        print(pregunta)
        lineas = []
        while True:
            linea = input("  > ").strip()
            if linea == "" and lineas:
                break
            if linea:
                lineas.append(linea)
        return " ".join(lineas)

    temas    = pedir("1. Temas que trabajaste hoy:")
    logros   = pedir("2. Que lograste hacer SOLO sin ayuda:")
    trabas   = pedir("3. Donde te trabaste o no entendiste:")
    conexion = pedir("4. Conexion con otra materia (o 'ninguna'):")

    duracion = 0
    while not duracion:
        try:
            duracion = int(input("\n5. Minutos reales de estudio: ").strip())
        except ValueError:
            print("   Solo el numero.")

    dificultad = 0
    while not dificultad:
        try:
            d = int(input("6. Dificultad percibida del 1 al 10: ").strip())
            if 1 <= d <= 10:
                dificultad = d
            else:
                print("   Entre 1 y 10.")
        except ValueError:
            print("   Solo el numero.")

    texto = f"""
TEMAS TRABAJADOS: {temas}
LOGROS AUTONOMOS: {logros}
DIFICULTADES: {trabas}
CONEXIONES: {conexion}
DURACION: {duracion} minutos
DIFICULTAD PERCIBIDA: {dificultad}/10
"""
    return texto, duracion, dificultad, temas, conexion

# ─── MAIN ────────────────────────────────────────────────────────
def main():
    print("\n" + "="*55)
    print("        AUDITOR DE APRENDIZAJE V3")
    print("="*55)
    print("\n  materias      -> ver lista de materias")
    print("  actualizacion -> actualizar semana y objetivo")
    print("  fin           -> terminar sesion y guardar")
    print("  salir         -> cerrar sin guardar")
    print("-"*55 + "\n")

    while True:
        entrada = input("Que materia quieres trabajar hoy? ").strip()
        if entrada.lower() == "salir":
            sys.exit(0)
        if entrada.lower() == "materias":
            listar_materias()
            continue
        if entrada.lower() == "actualizacion":
            cmd_actualizacion()
            continue
        if entrada:
            break

    print("\nCargando contexto desde Notion...\n")

    materia = buscar_materia(entrada)
    if not materia:
        print(f"No encontre '{entrada}'. Escribe 'materias' para ver los nombres exactos.")
        sys.exit(1)

    sesiones      = obtener_ultimas_sesiones(materia["id"])
    contexto      = construir_contexto(materia, sesiones)
    tipo_prompt   = PROMPTS_POR_TIPO.get(materia["tipo"], "")
    system_prompt = AUDITOR_BASE + "\n" + tipo_prompt

    mensajes = [
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": contexto}
    ]

    mision = llamar_ia(mensajes)
    mensajes.append({"role": "assistant", "content": mision})

    print(f"AUDITOR:\n{mision}\n")
    print("-"*55)
    print("Chat abierto. Dialoga, pregunta o cambia la mision.")
    print("Escribe 'fin' cuando termines.")
    print("-"*55 + "\n")

    while True:
        entrada = input("TU: ").strip()
        if not entrada:
            continue
        if entrada.lower() == "salir":
            print("\nSesion cerrada sin guardar.")
            sys.exit(0)
        if entrada.lower() == "fin":
            break
        mensajes.append({"role": "user", "content": entrada})
        respuesta = llamar_ia(mensajes)
        mensajes.append({"role": "assistant", "content": respuesta})
        print(f"\nAUDITOR:\n{respuesta}\n")

    sintesis_texto, duracion, dificultad, temas_vistos, conexiones = recopilar_sintesis()
    today = datetime.now().strftime("%d/%m/%Y")

    mensajes.append({"role": "user", "content": f"""
FECHA: {today}
NIVEL ENTRADA: {materia['nivel'] or '0'}/10
ERROR ACTIVO PREVIO: {materia['error_activo'] or 'Ninguno'}
PATRON ERROR: {materia['patron_error'] or 'Ninguno'}

{sintesis_texto}

Usa la RUBRICA DE NIVELES del silabo para asignar el nivel de salida.
Nivel real demostrado hoy. No el aspiracional.
Devuelve el formato Save Game exacto.
"""})

    print("\nEstructurando Save Game...\n")
    save_game = llamar_ia(mensajes)
    print(save_game)

    campos = parsear_save_game(save_game)

    patron_actualizado = materia["patron_error"] or ""
    if campos["error_detectado"] and "ninguno" not in campos["error_detectado"].lower():
        fecha_hoy          = datetime.now().strftime("%d/%m")
        patron_actualizado = f"{patron_actualizado} | [{fecha_hoy}] {campos['error_detectado']}".strip(" | ")

    print("\nGuardando en Notion...")
    try:
        guardar_sesion(
            materia["id"], materia["nombre"],
            save_game, campos,
            duracion, dificultad,
            temas_vistos, conexiones
        )
        actualizar_materia(
            materia["id"],
            error            = campos["error_detectado"] or materia["error_activo"] or "",
            patron_error     = patron_actualizado,
            prox_mision      = campos["proxima_mision"] or "",
            nivel_salida     = campos["nivel_salida"],
            temas_dominados  = materia["temas_dominados"] or "",
            temas_pendientes = materia["temas_pendientes"] or ""
        )
        print("\n✅ Sesion guardada en Notion.")
        print(f"   Hito:           {campos['hito_logrado']}")
        print(f"   Error:          {campos['error_detectado']}")
        print(f"   Proxima mision: {campos['proxima_mision']}")
        print(f"   Nivel:          {campos['nivel_entrada']} -> {campos['nivel_salida']}")
        print(f"   Duracion:       {duracion} min | Dificultad: {dificultad}/10")
    except Exception as e:
        print(f"\n❌ Error al guardar: {e}")
        print("Columnas esperadas: Hito Logrado, Error Detectado, Proxima Mision,")
        print("Nivel Entrada, Nivel Salida, Duracion Min, Dificultad,")
        print("Temas Vistos, Conexiones, Patron Error, Temas Dominados, Temas Pendientes")

    print("\n" + "="*55)
    print("        Sesion completada — Auditor V3")
    print("="*55 + "\n")

if __name__ == "__main__":
    main()
