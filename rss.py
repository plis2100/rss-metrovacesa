import html
import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path


BASE_URL = "https://metrovacesa.com"

PAGINA_PRINCIPAL = (
    "https://metrovacesa.com/"
    "category/sala-de-prensa"
)

API_CATEGORIAS = (
    "https://metrovacesa.com/"
    "wp-json/wp/v2/categories"
)

API_PUBLICACIONES = (
    "https://metrovacesa.com/"
    "wp-json/wp/v2/posts"
)

ARCHIVO_RSS = "metrovacesa.xml"


def descargar_json(url):
    solicitud = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0 Safari/537.36"
            ),
            "Accept": "application/json",
            "Accept-Language": "es-ES,es;q=0.9",
            "Cache-Control": "no-cache",
        },
    )

    with urllib.request.urlopen(
        solicitud,
        timeout=60,
    ) as respuesta:
        contenido = respuesta.read().decode(
            "utf-8",
            errors="replace",
        )

    return json.loads(contenido)


def limpiar_html(texto):
    texto = texto or ""

    texto = re.sub(
        r"<script[^>]*>.*?</script>",
        " ",
        texto,
        flags=re.IGNORECASE | re.DOTALL,
    )

    texto = re.sub(
        r"<style[^>]*>.*?</style>",
        " ",
        texto,
        flags=re.IGNORECASE | re.DOTALL,
    )

    texto = re.sub(
        r"<[^>]+>",
        " ",
        texto,
    )

    texto = html.unescape(texto)

    return re.sub(
        r"\s+",
        " ",
        texto,
    ).strip()


def convertir_fecha(fecha_texto):
    if not fecha_texto:
        return None

    try:
        fecha_limpia = fecha_texto.replace(
            "Z",
            "+00:00",
        )

        fecha = datetime.fromisoformat(
            fecha_limpia
        )

        if fecha.tzinfo is None:
            fecha = fecha.replace(
                tzinfo=timezone.utc
            )

        return fecha.astimezone(timezone.utc)

    except ValueError:
        return None


def obtener_categoria():
    parametros = urllib.parse.urlencode(
        {
            "slug": "sala-de-prensa",
            "per_page": 10,
        }
    )

    url = f"{API_CATEGORIAS}?{parametros}"

    categorias = descargar_json(url)

    if not categorias:
        raise RuntimeError(
            "No se encontró la categoría "
            "Sala de Prensa de Metrovacesa"
        )

    categoria = categorias[0]

    if "id" not in categoria:
        raise RuntimeError(
            "La categoría no tiene identificador"
        )

    return categoria["id"]


def obtener_publicaciones(categoria_id):
    parametros = urllib.parse.urlencode(
        {
            "categories": categoria_id,
            "per_page": 50,
            "page": 1,
            "orderby": "date",
            "order": "desc",
            "_fields": (
                "id,date_gmt,modified_gmt,"
                "link,title,excerpt"
            ),
        }
    )

    url = f"{API_PUBLICACIONES}?{parametros}"

    publicaciones = descargar_json(url)

    if not publicaciones:
        raise RuntimeError(
            "La categoría Sala de Prensa "
            "no contiene publicaciones"
        )

    return publicaciones


def obtener_noticias():
    categoria_id = obtener_categoria()

    publicaciones = obtener_publicaciones(
        categoria_id
    )

    noticias = []
    enlaces_vistos = set()

    for publicacion in publicaciones:
        titulo_datos = publicacion.get(
            "title",
            {},
        )

        extracto_datos = publicacion.get(
            "excerpt",
            {},
        )

        titulo = limpiar_html(
            titulo_datos.get("rendered", "")
        )

        descripcion = limpiar_html(
            extracto_datos.get("rendered", "")
        )

        url = publicacion.get(
            "link",
            "",
        ).strip()

        fecha = convertir_fecha(
            publicacion.get("date_gmt")
            or publicacion.get("modified_gmt")
        )

        if not titulo or not url:
            continue

        if url in enlaces_vistos:
            continue

        enlaces_vistos.add(url)

        if not descripcion:
            descripcion = (
                "Noticia oficial publicada "
                "por Metrovacesa."
            )

        noticias.append(
            {
                "titulo": titulo,
                "url": url,
                "fecha": fecha,
                "descripcion": descripcion[:1000],
            }
        )

        print(f"Noticia encontrada: {titulo}")

    if not noticias:
        raise RuntimeError(
            "No se pudieron obtener noticias "
            "de Metrovacesa"
        )

    noticias.sort(
        key=lambda noticia: (
            noticia["fecha"]
            or datetime(
                1970,
                1,
                1,
                tzinfo=timezone.utc,
            )
        ),
        reverse=True,
    )

    return noticias


def crear_rss(noticias):
    rss = ET.Element(
        "rss",
        {
            "version": "2.0",
            "xmlns:atom": (
                "http://www.w3.org/2005/Atom"
            ),
        },
    )

    canal = ET.SubElement(
        rss,
        "channel",
    )

    ET.SubElement(
        canal,
        "title",
    ).text = "Metrovacesa – Sala de Prensa"

    ET.SubElement(
        canal,
        "link",
    ).text = PAGINA_PRINCIPAL

    ET.SubElement(
        canal,
        "description",
    ).text = (
        "Últimas publicaciones oficiales "
        "de la Sala de Prensa de Metrovacesa"
    )

    ET.SubElement(
        canal,
        "language",
    ).text = "es-es"

    ET.SubElement(
        canal,
        "ttl",
    ).text = "60"

    ET.SubElement(
        canal,
        "{http://www.w3.org/2005/Atom}link",
        {
            "href": (
                "https://raw.githubusercontent.com/"
                "plis2100/rss-metrovacesa/"
                "main/metrovacesa.xml"
            ),
            "rel": "self",
            "type": "application/rss+xml",
        },
    )

    ahora = datetime.now(timezone.utc)

    ET.SubElement(
        canal,
        "lastBuildDate",
    ).text = format_datetime(ahora)

    for noticia in noticias:
        elemento = ET.SubElement(
            canal,
            "item",
        )

        ET.SubElement(
            elemento,
            "title",
        ).text = noticia["titulo"]

        ET.SubElement(
            elemento,
            "link",
        ).text = noticia["url"]

        ET.SubElement(
            elemento,
            "guid",
            {"isPermaLink": "true"},
        ).text = noticia["url"]

        ET.SubElement(
            elemento,
            "description",
        ).text = noticia["descripcion"]

        ET.SubElement(
            elemento,
            "source",
            {"url": PAGINA_PRINCIPAL},
        ).text = "Metrovacesa"

        if noticia["fecha"]:
            ET.SubElement(
                elemento,
                "pubDate",
            ).text = format_datetime(
                noticia["fecha"]
            )

    arbol = ET.ElementTree(rss)

    ET.indent(
        arbol,
        space="  ",
    )

    arbol.write(
        ARCHIVO_RSS,
        encoding="utf-8",
        xml_declaration=True,
    )


def validar_rss():
    archivo = Path(ARCHIVO_RSS)

    if not archivo.exists():
        raise RuntimeError(
            "No se creó metrovacesa.xml"
        )

    if archivo.stat().st_size < 500:
        raise RuntimeError(
            "metrovacesa.xml está vacío"
        )

    raiz = ET.parse(archivo).getroot()

    elementos = raiz.findall(
        "./channel/item"
    )

    if not elementos:
        raise RuntimeError(
            "La RSS de Metrovacesa "
            "no contiene noticias"
        )

    return len(elementos)


def main():
    noticias = obtener_noticias()

    crear_rss(noticias)

    cantidad = validar_rss()

    print(
        f"RSS de Metrovacesa creada: "
        f"{cantidad} noticias"
    )

    print(
        f"Última noticia: "
        f"{noticias[0]['titulo']}"
    )

    print(
        f"Archivo generado: {ARCHIVO_RSS}"
    )


if __name__ == "__main__":
    main()
