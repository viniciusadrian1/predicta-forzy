"use client";

/**
 * Malha do motor eletrico generico — UMA fonte para todas as telas.
 *
 * Antes existiam dois motores procedurais independentes: um na pagina do ativo
 * e outro na planta isometrica, este ultimo com a carcaca TINGIDA pela cor do
 * status (verde quando ok). O mesmo MTR-001 aparecia cinza numa tela e verde na
 * outra, como se fossem modelos diferentes. Havia ainda uma referencia a
 * `/models/motor.glb`, arquivo que nunca foi entregue: a deteccao por HEAD
 * falhava sempre e a planta caia no procedural, entao o caminho do glTF era
 * codigo morto que so alimentava a confusao.
 *
 * O status NAO colore mais a maquina: ele ja e comunicado pelo badge acima dela,
 * pelos marcadores dos pontos de medicao e pela legenda. Pintar a carcaca
 * inteira de verde escondia o proprio equipamento.
 *
 * Geometria procedural, sem binario. Unidades Three.js ~ metros.
 */

import * as THREE from "three";

export const BODY_RADIUS = 0.38;
export const BODY_LENGTH = 1.2;
const SHAFT_RADIUS = 0.06;
const SHAFT_OVERHANG = 0.32;
const FIN_COUNT = 9;
const FIN_TUBE_RADIUS = 0.025;
const TERMINAL_BOX_W = 0.3;
const TERMINAL_BOX_H = 0.18;
const TERMINAL_BOX_D = 0.22;

// Paleta industrial. Metalness baixo de proposito: sem mapa de ambiente, metal
// alto nao tem o que refletir e a peca renderiza quase preta no fundo escuro.
const CARCACA = "#7c8ba1";
const DETALHE = "#5c6a80";
const TAMPA = "#68788f";
const EIXO = "#cbd5e1";

function MotorBody() {
  return (
    <mesh rotation={[0, 0, Math.PI / 2]} receiveShadow castShadow>
      <cylinderGeometry args={[BODY_RADIUS, BODY_RADIUS, BODY_LENGTH, 48]} />
      <meshStandardMaterial color={CARCACA} roughness={0.45} metalness={0.35} />
    </mesh>
  );
}

function MotorShaft() {
  return (
    <>
      <mesh
        position={[-(BODY_LENGTH / 2 + SHAFT_OVERHANG / 2), 0, 0]}
        rotation={[0, 0, Math.PI / 2]}
        castShadow
      >
        <cylinderGeometry args={[SHAFT_RADIUS, SHAFT_RADIUS, SHAFT_OVERHANG, 24]} />
        <meshStandardMaterial color={EIXO} roughness={0.28} metalness={0.5} />
      </mesh>
      <mesh
        position={[BODY_LENGTH / 2 + SHAFT_OVERHANG / 4, 0, 0]}
        rotation={[0, 0, Math.PI / 2]}
        castShadow
      >
        <cylinderGeometry args={[SHAFT_RADIUS, SHAFT_RADIUS, SHAFT_OVERHANG / 2, 24]} />
        <meshStandardMaterial color={EIXO} roughness={0.28} metalness={0.5} />
      </mesh>
    </>
  );
}

function CoolingFins() {
  return (
    <>
      {Array.from({ length: FIN_COUNT }).map((_, i) => {
        const x = -BODY_LENGTH / 2 + (i / (FIN_COUNT - 1)) * BODY_LENGTH;
        return (
          <mesh key={i} position={[x, 0, 0]} castShadow>
            <torusGeometry args={[BODY_RADIUS + 0.015, FIN_TUBE_RADIUS, 12, 48]} />
            <meshStandardMaterial color={DETALHE} roughness={0.5} metalness={0.35} />
          </mesh>
        );
      })}
    </>
  );
}

function TerminalBox() {
  return (
    <mesh position={[0, BODY_RADIUS + TERMINAL_BOX_H / 2, 0]} castShadow>
      <boxGeometry args={[TERMINAL_BOX_W, TERMINAL_BOX_H, TERMINAL_BOX_D]} />
      <meshStandardMaterial color={DETALHE} roughness={0.45} metalness={0.35} />
    </mesh>
  );
}

function EndCap({ side }: { side: "front" | "back" }) {
  const x = side === "front" ? -BODY_LENGTH / 2 : BODY_LENGTH / 2;
  return (
    <mesh position={[x, 0, 0]} rotation={[0, Math.PI / 2, 0]} castShadow>
      <circleGeometry args={[BODY_RADIUS, 48]} />
      <meshStandardMaterial
        color={TAMPA}
        roughness={0.45}
        metalness={0.35}
        side={THREE.DoubleSide}
      />
    </mesh>
  );
}

/** Base/pes — so na planta, onde a maquina se apoia no chao. */
function MotorFeet() {
  return (
    <mesh position={[0, -(BODY_RADIUS + 0.05), 0]} castShadow receiveShadow>
      <boxGeometry args={[BODY_LENGTH * 1.05, 0.1, BODY_RADIUS * 1.9]} />
      <meshStandardMaterial color="#475569" roughness={0.7} metalness={0.25} />
    </mesh>
  );
}

/**
 * O motor completo, centrado na origem, eixo ao longo de X.
 *
 * `withFeet` acrescenta a base de apoio (usada na planta isometrica; a pagina
 * do ativo mostra a peca flutuando para o giro livre da camera).
 */
export function MotorMesh({ withFeet = false }: { withFeet?: boolean }) {
  return (
    <group>
      <MotorBody />
      <CoolingFins />
      <MotorShaft />
      <TerminalBox />
      <EndCap side="front" />
      <EndCap side="back" />
      {withFeet && <MotorFeet />}
    </group>
  );
}
