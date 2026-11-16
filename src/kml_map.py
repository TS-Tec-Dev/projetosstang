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


def map_for_kml(geometry):
    """Deck com desenhos próprios; sem depender de um token Mapbox do usuário."""
    import pydeck as pdk
    allpoints=geometry['all']
    if not allpoints:return None
    centerlon=sum(v[0] for v in allpoints)/len(allpoints)
    centerlat=sum(v[1] for v in allpoints)/len(allpoints)
    spread=max(max(abs(x[0]-centerlon),abs(x[1]-centerlat)) for x in allpoints)
    zoom=14 if spread<0.003 else 12 if spread<0.02 else 10 if spread<0.1 else 7 if spread<1 else 4
    layers=[]
    if geometry['polygons']:
        layers.append(pdk.Layer('PolygonLayer',data=[{'polygon':p} for p in geometry['polygons']],
                                get_polygon='polygon',get_fill_color=[8,127,128,55],
                                get_line_color=[7,109,111,225],stroked=True,filled=True,
                                line_width_min_pixels=2,pickable=True))
    if geometry['paths']:
        layers.append(pdk.Layer('PathLayer',data=[{'path':p} for p in geometry['paths']],
                                get_path='path',get_color=[8,127,128,230],width_min_pixels=3,
                                pickable=True))
    if geometry['points']:
        layers.append(pdk.Layer('ScatterplotLayer',data=[{'position':p} for p in geometry['points']],
                                get_position='position',get_fill_color=[230,120,27,240],
                                get_radius=8,radius_min_pixels=5,pickable=True))
    return pdk.Deck(layers=layers,initial_view_state=pdk.ViewState(latitude=centerlat,longitude=centerlon,zoom=zoom,pitch=0),
                    map_style='light',tooltip={'text':'Localização do empreendimento'})
