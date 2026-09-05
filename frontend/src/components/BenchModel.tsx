"use client";

/**
 * BenchModel
 * ----------
 * Malha da bancada de bomba de teste da Forzy, carregada do GLB gerado a
 * partir do CAD real (STEP tesselado com OpenCascade).
 *
 * O GLB já vem no referencial do three.js (eixo da máquina em X, vertical em Y,
 * profundidade em Z), em METROS e centrado em X/Z com a base em Y=0 — então
 * basta escalar conforme o contexto.
 *
 * As cores vêm como vertex colors do próprio GLB (motor azul, mancais escuros,
 * skid grafite), atribuídas peça a peça na conversão.
 */

import { useGLTF } from "@react-three/drei";
import { useMemo } from "react";
import * as THREE from "three";

import { BENCH_GLB } from "@/lib/benchGeometry";

export function BenchModel() {
  const { scene } = useGLTF(BENCH_GLB);

  const model = useMemo(() => {
    const clone = scene.clone(true);
    clone.traverse((obj) => {
      if (obj instanceof THREE.Mesh) {
        obj.castShadow = true;
        obj.receiveShadow = true;
        const mat = obj.material as THREE.MeshStandardMaterial;
        if (mat) {
          mat.metalness = 0.55;
          mat.roughness = 0.5;
        }
      }
    });
    return clone;
  }, [scene]);

  return <primitive object={model} />;
}

useGLTF.preload(BENCH_GLB);
