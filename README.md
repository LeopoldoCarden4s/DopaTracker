# DopaTracker: Auditor De Estudio 🧠📊

Este proyecto es un sistema automatizado de auditoría analítica y optimización del aprendizaje continuo. Conecta una infraestructura de base de datos relacional (Notion) con modelos de lenguaje de gran escala (LLMs a través de Groq Cloud API) para evaluar, trackear y optimizar sesiones de estudio en tiempo real, aplicando principios conductuales y de gestión de procesos.

## 🚀 Características Principales (DopaTracker)

* **Extracción de Datos Dinámica:** Conexión directa a la API de Notion para auditar bases de datos de materias y sesiones.
* **Diferenciación de Prompts por Carga Cognitiva:** El sistema inyecta prompts condicionales rígidos dependiendo del tipo de materia:
  * **Técnica:** Enfoque algorítmico y ejecutable (código, matemáticas).
  * **Teórica:** Enfoque conceptual (explicación sintética y retención).
  * **Mixta:** Híbrido estratégico.
* **Análisis de Fricción Operativa:** Procesamiento por expresiones regulares (Regex) para identificar y actualizar patrones de errores recurrentes.
* **Rúbricas de Evaluación Automatizadas:** El backend evalúa hitos logrados, niveles de entrada/salida y calcula de forma autónoma la "próxima misión" del usuario para mitigar el sesgo de procrastinación.

## 🗃️ Arquitectura Requerida en Notion

Para que el script funcione correctamente, tu entorno de Notion debe contar con dos bases de datos relacionales vinculadas entre sí. A continuación se detallan los nombres exactos y tipos de propiedades que el código espera encontrar:

### 1. Base de Datos: Materias (`MATERIAS_DB_ID`)
Esta base actúa como el **Panel de Control de tu Carrera**. Aquí se almacena el sílabo académico y las métricas acumuladas de tu cerebro por asignatura.

| Nombre de la Propiedad | Tipo en Notion | Descripción / Formato esperado por el Script |
| :--- | :--- | :--- |
| `Nombre` | Title (Título) | Nombre de la asignatura (ej: *Econometría*, *Álgebra*). |
| `Tipo` | Select (Selección) | Opciones estrictas: `Técnica`, `Teórica` o `Mixta`. |
| `Próxima Misión` | Text (Texto) | Meta táctica inmediata inyectada automáticamente por la IA. |
| `Error Activo` | Text (Texto) | El último cuello de botella técnico detectado en la materia. |
| `Patrón Error` | Text (Texto) | Historial resumido de errores recurrentes analizados por Regex. |
| `Nivel Salida` | Number (Número) | Nota o nivel de dominio actual calculado por el bot. |
| `Temas Dominados` | Text o Multi-select | Componentes del **Sílabo** ya consolidados. |
| `Temas Pendientes`| Text o Multi-select | Componentes del **Sílabo** que faltan por abordar. |
| `Próxima Evaluación`| Date (Fecha) | Fecha del próximo certamen o hito (utilizado para calcular urgencia). |

### 2. Base de Datos: Sesiones (`SESIONES_DB_ID`)
Esta base actúa como el **Historial de Operaciones**. Cada fila representa un bloque de estudio ejecutado.

| Nombre de la Propiedad | Tipo en Notion | Descripción / Formato esperado por el Script |
| :--- | :--- | :--- |
| `Nombre` | Title (Título) | Identificador de la sesión o código del "Save Game". |
| `Materia` | Relation (Relación) | Enlace obligatorio hacia la base de datos de Materias. |
| `Hito Logrado` | Text (Texto) | El entregable o meta alcanzada en este bloque específico. |
| `Error Detectado` | Text (Texto) | Qué te trancó o te hizo perder tiempo durante la sesión. |
| `Nivel Entrada` | Number (Número) | Autoevaluación del estado cognitivo antes de empezar. |
| `Nivel Salida` | Number (Número) | Evaluación final del dominio tras la sesión. |
| `Duración Min` | Number (Número) | Tiempo exacto en minutos del bloque de estudio. |
| `Dificultad` | Number (Número) | Escala del 1 al 10 de la resistencia del contenido. |
| `Temas Vistos` | Text (Texto) | Qué conceptos específicos del sílabo se atacaron hoy. |
| `Conexiones` | Text (Texto) | Ideas o links asociativos cruzados descubiertos en la sesión. |

## 🛠️ Tecnologías Utilizadas
- **Lenguaje Principal:** Python 3.10+
- **Orquestación de IA:** Groq SDK (Modelos LLaMA-3 de ultra-baja latencia).
- **Integración de Servicios:** Notion Client API.
- **Gestión de Entorno:** Python-Dotenv (Seguridad de credenciales).

## 📋 Requisitos e Instalación
1. Clona este repositorio.
2. Instala las dependencias necesarias:
   ```bash
   pip install -r requirements.txt

   ## ⚙️ Personalización del Auditor (System Prompt)
El motor de IA está configurado en `auditor.py` bajo un perfil conductual optimizado para perfiles analíticos y de estrategia de negocios (perfil ENTP enfocado en Ingeniería Comercial, Estrategia de Datos y Procesos). 

Si deseas adaptar el comportamiento del auditor a tu propia carrera, estilo cognitivo (MBTI) o debilidades de aprendizaje, puedes editar la variable `AUDITOR_BASE` dentro del script principal para personalizar el comportamiento del bot según tus necesidades operativas.
