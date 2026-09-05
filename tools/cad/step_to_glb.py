# -*- coding: utf-8 -*-
"""Converte o STEP da bancada Forzy em GLB, tesselando o B-rep de verdade.

- Le o STEP com OpenCascade (OCP), tessela cada solido
- Reorienta: eixo da maquina -> X, vertical -> Y, profundidade -> Z (three.js)
- Recentra na origem, converte mm -> metros
- Colore cada solido conforme a peca (motor azul, mancais escuros, etc.)
"""
from pathlib import Path

import numpy as np
import trimesh
from OCP.BRep import BRep_Tool
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.IFSelect import IFSelect_RetDone
from OCP.STEPControl import STEPControl_Reader
from OCP.TopAbs import TopAbs_FACE, TopAbs_REVERSED, TopAbs_SOLID
from OCP.TopExp import TopExp_Explorer
from OCP.TopLoc import TopLoc_Location
from OCP.TopoDS import TopoDS

SRC = Path(r"C:\Users\vinic\Downloads\ChallengeForzy-bomba-teste (2).stp")
OUT = Path(r"C:\Users\vinic\Downloads\PredictaCC\frontend\public\models\bomba-teste.glb")

# --- 1) leitura -----------------------------------------------------------
reader = STEPControl_Reader()
if reader.ReadFile(str(SRC)) != IFSelect_RetDone:
    raise SystemExit("falha ao ler o STEP")
reader.TransferRoots()
shape = reader.OneShape()

# --- 2) tesselacao (deflexao em mm; pecas de 100-400mm => 0.4 fica liso) ---
BRepMesh_IncrementalMesh(shape, 0.4, False, 0.3, True)


def solid_mesh(solid):
    """Extrai (vertices, faces) de um solido ja tesselado."""
    verts: list[tuple[float, float, float]] = []
    faces: list[tuple[int, int, int]] = []
    exp = TopExp_Explorer(solid, TopAbs_FACE)
    while exp.More():
        face = TopoDS.Face_s(exp.Current())
        loc = TopLoc_Location()
        tri = BRep_Tool.Triangulation_s(face, loc)
        if tri is not None:
            trsf = loc.Transformation()
            base = len(verts)
            for i in range(1, tri.NbNodes() + 1):
                p = tri.Node(i).Transformed(trsf)
                verts.append((p.X(), p.Y(), p.Z()))
            reversed_ = face.Orientation() == TopAbs_REVERSED
            for i in range(1, tri.NbTriangles() + 1):
                a, b, c = tri.Triangle(i).Get()
                t = (base + a - 1, base + c - 1, base + b - 1) if reversed_ else (
                    base + a - 1, base + b - 1, base + c - 1
                )
                faces.append(t)
        exp.Next()
    return np.array(verts, dtype=np.float64), np.array(faces, dtype=np.int64)


# --- 3) percorre os solidos ------------------------------------------------
raw = []
exp = TopExp_Explorer(shape, TopAbs_SOLID)
while exp.More():
    v, f = solid_mesh(TopoDS.Solid_s(exp.Current()))
    if len(v) and len(f):
        raw.append((v, f))
    exp.Next()
print(f"solidos tesselados: {len(raw)}")
if not raw:
    raise SystemExit("nenhum solido tesselado")

allv = np.vstack([v for v, _ in raw])
print(f"vertices totais: {len(allv)}  | triangulos: {sum(len(f) for _, f in raw)}")

# --- 4) reorientacao + recentragem ----------------------------------------
# STEP: X=profundidade, Y=eixo da maquina, Z=vertical.  Alvo: X=eixo, Y=cima, Z=prof.
x_mid = (allv[:, 0].min() + allv[:, 0].max()) / 2
y_mid = (allv[:, 1].min() + allv[:, 1].max()) / 2
z_min = allv[:, 2].min()


def transform(v: np.ndarray) -> np.ndarray:
    out = np.empty_like(v)
    out[:, 0] = (v[:, 1] - y_mid) / 1000.0  # eixo da maquina -> X (m)
    out[:, 1] = (v[:, 2] - z_min) / 1000.0  # vertical        -> Y (m)
    out[:, 2] = (v[:, 0] - x_mid) / 1000.0  # profundidade    -> Z (m)
    return out


# --- 5) cor por peca (u = mm a partir da extremidade da bomba) ------------
def color_for(u: float, dims: np.ndarray) -> tuple[int, int, int, int]:
    length, height, depth = dims  # em metros, ja no referencial novo
    # base/skid: peca larga e baixa
    if depth > 0.35 and height < 0.25:
        return (63, 72, 85, 255)
    if u > 640:                      # motor + tampas
        return (47, 111, 179, 255)   # azul, como o real
    if 560 <= u <= 620 or 470 <= u <= 530:
        return (31, 41, 55, 255)     # os dois mancais
    if 520 < u < 580:
        return (203, 213, 225, 255)  # eixo
    if 300 <= u <= 400:
        return (154, 164, 178, 255)  # acoplamento
    return (107, 114, 128, 255)      # bomba / suportes


scene = trimesh.Scene()
report = []
for idx, (v, f) in enumerate(raw):
    tv = transform(v)
    mesh = trimesh.Trimesh(vertices=tv, faces=f, process=False)
    # normais vem da orientacao da face (TopAbs_REVERSED), sem precisar de scipy
    lo, hi = tv.min(axis=0), tv.max(axis=0)
    dims = hi - lo
    u = ((lo[0] + hi[0]) / 2) * 1000 + 600
    # cor uniforme por solido, aplicada por VERTICE (evita a conversao
    # face->vertice do trimesh, que exigiria scipy)
    col = np.array(color_for(u, dims), dtype=np.uint8)
    mesh.visual = trimesh.visual.ColorVisuals(
        mesh=mesh, vertex_colors=np.tile(col, (len(tv), 1))
    )
    scene.add_geometry(mesh, node_name=f"peca_{idx:02d}")
    report.append((idx, u, dims))

report.sort(key=lambda r: r[1])
print("\npeca   u(mm)   compr.  altura  prof.  (m)")
for idx, u, d in report:
    print(f"  {idx:02d}  {u:7.1f}   {d[0]:.3f}   {d[1]:.3f}   {d[2]:.3f}")

bounds = scene.bounds
print(f"\nconjunto (m): X {bounds[0][0]:.3f}..{bounds[1][0]:.3f} | "
      f"Y {bounds[0][1]:.3f}..{bounds[1][1]:.3f} | Z {bounds[0][2]:.3f}..{bounds[1][2]:.3f}")

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_bytes(trimesh.exchange.gltf.export_glb(scene))
print(f"\nGLB escrito: {OUT}  ({OUT.stat().st_size/1024:.0f} KB)")
