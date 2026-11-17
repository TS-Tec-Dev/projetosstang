"""Leitura local de KML para pré-visualização; nunca acessa links externos do KML.

Visualiza Point, LineString e Polygon; arquivos com overlays/modelos podem ser
baixados e abertos no Google Earth, mas não são renderizados pelo mapa interno.
"""
from __future__ import annotations
from math import isfinite
from defusedxml import ElementTree

MAX_KML_PREVIEW_BYTES = 10 * 1024 * 1024
MAX_COORDINATES = 6000


def read_kml_geometries(data: bytes) -> dict:
    if not data or len(data) > MAX_KML_PREVIEW_BYTES:
        raise ValueError('KML vazio ou maior que 10 MB para visualização.')
    root = ElementTree.fromstring(data)
    geometry={'points':[], 'paths':[], 'polygons':[], 'all':[]}
    def tag(node):return str(node.tag).rsplit('}',1)[-1]
    def coords(node):
        result=[]
        for child in node.iter():
            if tag(child)!='coordinates' or not child.text:continue
            for part in child.text.split():
                fields=part.split(',')
                if len(fields)<2:continue
                try:
                    lon=float(fields[0]);lat=float(fields[1])
                except (ValueError,OverflowError):continue
                if not (isfinite(lon) and isfinite(lat) and -180<=lon<=180 and -90<=lat<=90):continue
                result.append([lon,lat])
                if len(result)+len(geometry['all'])>MAX_COORDINATES:
                    raise ValueError('KML com mais pontos que o limite de visualização (6.000).')
        return result
    # Não repetir geometrias de MultiGeometry: procurar somente tags geométricas.
    for node in root.iter():
        t=tag(node)
        if t not in ('Point','LineString','Polygon'):continue
        points=coords(node)
        if not points:continue
        geometry['all'].extend(points)
        if len(geometry['all'])>MAX_COORDINATES:
            raise ValueError('KML ultrapassou 6.000 coordenadas.')
        if t=='Point':geometry['points'].extend(points[:1])
        if t=='LineString' and len(points)>=2:geometry['paths'].append(points)
        if t=='Polygon' and len(points)>=3:geometry['polygons'].append(points)
    return geometry


# Imagens de satélite por serviço Esri World Imagery (requer internet no navegador).
# Crédito do provedor visível no mapa. Não é o mosaico do Google Earth.
ESRI_IMAGERY_URL = (
    "https://server.arcgisonline.com/ArcGIS/rest/services/"
    "World_Imagery/MapServer/tile/{z}/{y}/{x}"
)
ESRI_ATTRIBUTION = (
    "Tiles &copy; Esri &mdash; Sources: Esri, Maxar, Earthstar Geographics, "
    "and the GIS User Community"
)


def map_for_kml(geometry):
    """Mapa Folium com satélite como base e perímetro KML sobreposto.

    Apenas a camada de imagens busca dados externos (Esri). O KML é analisado
    localmente e nunca executa links nem scripts existentes no arquivo.
    """
    import folium

    points = geometry.get('all') or []
    if not points:
        return None

    # O KML usa longitude,latitude; o Leaflet/Folium usa latitude,longitude.
    lats = [float(p[1]) for p in points]
    lons = [float(p[0]) for p in points]
    center = [(min(lats) + max(lats)) / 2, (min(lons) + max(lons)) / 2]
    m = folium.Map(
        location=center, tiles=None, zoom_start=17, control_scale=True,
        prefer_canvas=True, max_zoom=19,
    )
    folium.TileLayer(
        tiles=ESRI_IMAGERY_URL,
        attr=ESRI_ATTRIBUTION,
        name='Satélite (Esri)',
        overlay=False, control=True, show=True,
        max_zoom=19,
    ).add_to(m)
    # Alternativa útil quando a imagem de satélite não carregar em algum navegador.
    folium.TileLayer(
        tiles='OpenStreetMap',
        name='Mapa de ruas', overlay=False, control=True, show=False,
    ).add_to(m)

    for polygon in geometry.get('polygons', []):
        folium.Polygon(
            locations=[[lat, lon] for lon, lat in polygon],
            color='#00e5d3', weight=3, opacity=0.95,
            fill=True, fill_color='#05b9aa', fill_opacity=0.19,
            tooltip='Perímetro do empreendimento',
        ).add_to(m)
    for path in geometry.get('paths', []):
        folium.PolyLine(
            locations=[[lat, lon] for lon, lat in path],
            color='#ffcb52', weight=4, opacity=0.95,
            tooltip='Traçado do KML',
        ).add_to(m)
    for lon, lat in geometry.get('points', []):
        folium.CircleMarker(
            location=[lat, lon], radius=6,
            color='#ffdc62', fill=True, fill_color='#ffeeb0',
            fill_opacity=1, tooltip='Ponto do KML',
        ).add_to(m)

    if len(points) > 1 and (max(lats) - min(lats) > 1e-7 or max(lons) - min(lons) > 1e-7):
        m.fit_bounds(
            [[min(lats), min(lons)], [max(lats), max(lons)]],
            padding=(24, 24), max_zoom=18,
        )
    folium.LayerControl(position='topright', collapsed=True).add_to(m)
    return m
