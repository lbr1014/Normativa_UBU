import asyncio
import json
import re
import time
from typing import Any, List

from playwright.async_api import Frame, Page, async_playwright, expect
from playwright.async_api import TimeoutError as PWTimeoutError

# ======== Constantes ========
BASE_URL = "https://contrataciondelestado.es/wps/portal/plataforma"
OUTPUT_JSON = "resultados_playwright_asincrono.json"
QUERY = "licitacion"
OBJETIVO = "Junta de Gobierno de la Diputación Provincial de Burgos"


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


# ---------- Funciones ----------
async def encontrar_frame(page, selector: str, timeout_ms: int = 30_000) -> Frame:
    """
    Devuelve el primer Frame de la página que contenga `selector`.
    Recorre todos los frames e intenta esperar el selector con un timeout corto.
    """
    deadline = time.monotonic() + (timeout_ms / 1000.0)

    while time.monotonic() < deadline:
        for f in page.frames:
            try:
                await f.wait_for_selector(selector, timeout=800)
                return f
            except PWTimeoutError:
                continue
        await asyncio.sleep(0.25)

    raise PWTimeoutError(f"No se encontró ningún frame con el selector: {selector}")


async def eleccion_organo(frame_arbol: Frame, texto_objetivo: str) -> None:
    """
    Selecciona en el listbox inferior (comboNombreOrgano) la option cuyo texto contiene
    `texto_objetivo` y pulsa Añadir.
    """
    # Recuadro inferior, id dinámico
    sel = frame_arbol.locator(r'[id$=":comboNombreOrgano"]').first
    await sel.wait_for(state="visible")
    await sel.scroll_into_view_if_needed()

    print("SELECT ENCONTRADO")

    # Asegura que hay opciones cargadas
    await sel.locator("option").first.wait_for(state="attached")

    print("OPTIONS CARGADAS")

    # Busca la option por texto
    opcion = sel.locator(
        "option", has_text=re.compile(re.escape(texto_objetivo), re.I)
    ).first
    await opcion.wait_for(state="attached")

    print("BÚSQUEDA POR TEXTO")
    # Selecciona por value la opción
    value = await opcion.get_attribute("value")
    if value:
        await sel.select_option(value=value)
    else:
        await sel.select_option(label=texto_objetivo)
    print("SELECCiÓN POR ÍNDICES")

    # Pulsa el botón Añadir
    btn_anadir = frame_arbol.get_by_role("button", name=re.compile(r"^Añadir$", re.I))
    await btn_anadir.wait_for(state="visible")
    await btn_anadir.click()


async def pestana_diputacion(busqueda: str) -> str:
    """
    Devuelve la clave de pestaña a abrir según el texto de búsqueda.

    Argumentos:
        busqeuda: texto que de búsqueda segun el cual se va a seleccioanr la pestaña.
    Returns:
        nombre de pestaña a abrir

    """
    b = (busqueda or "").lower()
    print(busqueda)
    print(any(k in b for k in ("pliego", "pliegos", "doc", "documento", "documentos")))
    if any(k in b for k in ("pliego", "pliegos", "doc", "documento", "documentos")):
        return "Documentos"
    if any(
        k in b
        for k in (
            "licitacion",
            "licitación",
            "licitaciones",
            "expediente",
            "expedientes",
        )
    ):
        return "Licitaciones"
    if any(k in b for k in ("menor", "contrato menor", "contratos menores")):
        return "Contratos Menores"
    if any(k in b for k in ("encargo", "medios propios", "medio propio")):
        return "Encargos a medios propios"
    if any(
        k in b for k in ("consulta preliminar", "consultas preliminares", "consulta")
    ):
        return "Consultas preliminares"
    return "perfil"


async def ir_pestana(page: Page, clave: str, timeout: float = 10_000) -> None:
    """
    Hace clic en la pestaña indicada en la clave usando Playwright.

    Argumentos:
        page: Playwright Page.
        clave: la clave para ir a la pestaña.
        timeout: timeout en ms para localizar/clickar.

    Excepciones:
        ValueError: Si la pestaña no está mapeada.
        PlaywrightTimeoutError: Si no se puede abrir la pestaña.
    """

    mapping = {
        "Perfil del Contratante": (
            r"#viewns_Z7_AVEQAI930GRPE02BR764FO30G0_" + r"\:perfilComp\:textLinkOff"
        ),
        "Documentos": (
            r"#viewns_Z7_AVEQAI930GRPE02BR764FO30G0_" + r"\:perfilComp\:linkPrepDocs"
        ),
        "Licitaciones": (
            r"#viewns_Z7_AVEQAI930GRPE02BR764FO30G0_" + r"\:perfilComp\:linkPrepLic"
        ),
        "Contratos Menores": (
            r"#viewns_Z7_AVEQAI930GRPE02BR764FO30G0_"
            + r"\:perfilComp\:linkPrepContratosMenores"
        ),
        "Encargos a medios propios": (
            r"#viewns_Z7_AVEQAI930GRPE02BR764FO30G0_"
            + r"\:perfilComp\:linkPrepEncargosMP"
        ),
        "Consultas preliminares": (
            r"#viewns_Z7_AVEQAI930GRPE02BR764FO30G0_"
            + r"\:perfilComp\:linkPrepConsultasAnuncio"
        ),
    }

    sel = mapping.get(clave)
    if not sel:
        raise ValueError(f"Pestaña no soportada: {clave}")

    try:
        locator = page.locator(sel).first
        await locator.wait_for(state="visible", timeout=timeout)
        await locator.scroll_into_view_if_needed(timeout=timeout)
        await expect(locator).to_be_enabled(timeout=timeout)
        await locator.click(timeout=timeout, trial=True)
        await locator.click(timeout=timeout)
    except PWTimeoutError as err:
        raise PWTimeoutError(f"No se pudo abrir la pestaña: {clave}") from err

    try:
        await page.wait_for_timeout(5_000)
    except Exception:
        pass
    await page.wait_for_timeout(400)


async def extraer_licitaciones(page: Page) -> list[dict]:
    """
    Recorre las licitaciones de la página entrando en cada una
    Argumentos:
        page: la página actual (Licitacion) de la cual queremos extrear el JSON

    Return:
        Devuelve un diccionario con la información extraida.
    """
    print("voy a descaragr licitaciones")
    url = page.url
    tabla = page.locator(r"#tableLicitacionesPerfilContratante")
    await tabla.wait_for(state="visible")

    filas = tabla.locator("tbody tr")
    total = await filas.count()
    print(f"Filas en la página: {total}")

    botonSiguiente = page.locator(
        r"#viewns_Z7_AVEQAI930GRPE02BR764FO30G0_\:form1\:siguienteLink"
    )
    await botonSiguiente.wait_for(state="visible", timeout=30_000)
    await botonSiguiente.scroll_into_view_if_needed()
    j = 0
    pagina = 1
    resultados = []
    while True:

        total = await filas.count()
        print(f"Filas en la página {pagina} : {total}")

        for i in range(total):
            await tabla.wait_for(state="visible", timeout=30_000)
            fila = tabla.locator("tbody tr").nth(i)

            enlace = fila.locator('td.tdExpediente a:not([target="_blank"])').first
            await enlace.wait_for(state="visible", timeout=30_000)
            await enlace.scroll_into_view_if_needed()

            async with page.expect_navigation(wait_until="domcontentloaded"):
                await enlace.click(force=True)

            await page.wait_for_load_state("networkidle")

            await page.wait_for_timeout(400)

            datos = await extraer_detalles_licitacion(page)
            resultados.append({"datos": datos})

            j += 1
            print(f"Licitación visitada #{i + 1} Total {j}")

            await page.goto(url)
            await ir_pestana(page, "Licitaciones")
            await page.wait_for_load_state("domcontentloaded")
            await tabla.wait_for(state="visible", timeout=30_000)
            await page.wait_for_load_state("networkidle")

        if not await botonSiguiente.is_visible():
            break

        await botonSiguiente.click(force=True)
        await page.wait_for_load_state("domcontentloaded")
        await tabla.wait_for(state="visible", timeout=30_000)
        await page.wait_for_load_state("networkidle")
        pagina += 1

    return resultados


async def extraer_detalles_licitacion(page: Page) -> dict:
    """
    Extrae los campos visibles de la página actual de licitaciones en formato JSON
    Argumentos:
        page: la página actual de la cual queremos extrear el JSON

    Return:
        Devuelve un diccionario con la información extraida.
    """
    datos = []
    print("EMPIEZA A EXTRAER DATOS")
    tabla = page.locator(
        r"#viewns_Z7_AVEQAI930OBRD02JPMTPG21006_\:form1 > div > div > div.row > table"
    ).first
    await tabla.wait_for(state="visible", timeout=20000)
    await tabla.scroll_into_view_if_needed()

    datos: dict[str, str] = {}
    print(f"DATOS ENCONTRADOS: {tabla }")

    filas = tabla.locator("tr")
    n = await filas.count()
    for i in range(n):
        celdas = filas.nth(i).locator("td")
        if await celdas.count() < 2:
            continue

        # Normalizar los datos obtenidos
        # Quita los espacios dejando solo uno y quita los dos puntos
        k_raw = await celdas.nth(0).inner_text()
        v_raw = await celdas.nth(1).inner_text()

        k = _norm(re.sub(r":\s*$", "", k_raw))
        v = _norm(v_raw)

        # Quita los dos puntos finales típicos

        if k and v:
            datos[k] = v

    if not datos:
        pares = page.locator(
            r"#viewns_Z7_AVEQAI930OBRD02JPMTPG21006_\:form1 div.flex-inline"
        )
        total = await pares.count()
        for i in range(total):
            bloque = pares.nth(i)

            # etiqueta (label o span con id)
            k_raw = await bloque.locator("label, span[id]").first.inner_text()
            k = _norm(re.sub(r":\s*$", "", k_raw))

            # valores: span sin id, enlaces, strong, em…
            vals = await bloque.locator(
                "span:not([id]), a, strong, em"
            ).all_inner_texts()
            # all_inner_texts() devuelve lista → ¡únela antes de normalizar!
            v = _norm(" ".join(vals)) if vals else ""

            if k and v:
                datos[k] = v

    print(f"\nLA TABLA ES: {datos}")

    return datos


async def guardar_licitacion_json(resultados: List[Any]) -> None:
    """
    Guarda las licitaciones en OUTPUT_JSON como una lista de objetos {datos, documentos}

    Argumentos:
        resultados: La lista con los resultados que se van a almacenar en el json
    """

    def _write():
        with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
            json.dump(resultados, f, ensure_ascii=False, indent=2)

    await asyncio.to_thread(_write)


# ========== MAIN ============
async def run() -> None:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            locale="es-ES",
            timezone_id="Europe/Madrid",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1366, "height": 900},
        )

        await context.tracing.start(screenshots=True, snapshots=True, sources=True)
        page = await context.new_page()

        try:
            await page.goto(BASE_URL, wait_until="networkidle", timeout=45_000)
            print("Título:", await page.title())

            # Abre la pestaña "Perfil Contratante"
            try:
                async with page.expect_navigation(timeout=45_000):
                    await page.get_by_role(
                        "link", name="Perfil Contratante", exact=True
                    ).click()
            except PWTimeoutError:
                pass
            await page.wait_for_load_state("networkidle")

            # Pulsa "Seleccionar"
            try:
                async with page.expect_navigation(timeout=45_000):
                    await page.get_by_role(
                        "link", name="Seleccionar", exact=True
                    ).click()
            except PWTimeoutError:
                pass
            await page.wait_for_load_state("networkidle")

            # --- Buscar el frame del diálogo por el <select> del recuadro inferior ---
            selector_select = r'[id$=":comboNombreOrgano"]'
            frame_arbol = await encontrar_frame(page, selector_select)

            # Pulsa "Sector Público" dentro de ese frame (usar Locator, no el string)
            selector_nodo = r"#tafelTree_maceoArbol_id_1"
            nodo_sector_publico = frame_arbol.locator(selector_nodo)
            await nodo_sector_publico.wait_for(state="attached", timeout=30_000)
            await nodo_sector_publico.scroll_into_view_if_needed()
            await nodo_sector_publico.click()

            # Buscar la Junta de gobierno de la diputación de Burgos en el listado
            await eleccion_organo(frame_arbol, OBJETIVO)
            await page.wait_for_load_state("networkidle")

            # Botón buscar
            btn_buscar = page.locator(
                r"#viewns_Z7_AVEQAI930GRPE02BR764FO30G0_\:listaperfiles\:botonbuscar"
            )
            await btn_buscar.wait_for(state="visible", timeout=30_000)
            await btn_buscar.scroll_into_view_if_needed()
            await btn_buscar.click(force=True)
            await page.wait_for_load_state("networkidle")

            # Link de la junta
            lnk_junta = page.locator(
                r"#viewns_Z7_AVEQAI930GRPE02BR764FO30G0_\:listaperfiles\:enlaceExpedienteBP_0_textoEnlace"
            )
            await lnk_junta.wait_for(state="visible", timeout=30_000)
            await lnk_junta.scroll_into_view_if_needed()
            await lnk_junta.click(force=True)
            await page.wait_for_load_state("networkidle")

            # Va a la pestaña correcta segun la query
            destino = await pestana_diputacion(QUERY)
            print(f"Iré a la pestaña: {destino}")
            await ir_pestana(page, destino)

            # Extrae las licitaciones y las guarda
            resultado = []
            if destino == "Licitaciones":
                resultado = await extraer_licitaciones(page)
            await guardar_licitacion_json(resultado)

        except PWTimeoutError:
            print("Timeout al cargar o encontrar elementos.")
        finally:
            await context.tracing.stop(path="trace.zip")
            await context.close()
            await browser.close()


if __name__ == "__main__":
    asyncio.run(run())
