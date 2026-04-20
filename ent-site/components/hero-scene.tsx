"use client";

import { Canvas } from "@react-three/fiber";
import { Float, MeshDistortMaterial, OrbitControls } from "@react-three/drei";
import { useMemo } from "react";

function FloatingOrbs() {
  const positions = useMemo(
    () => [
      [-2.4, 1.2, -1.5],
      [2.1, -0.5, -2.2],
      [-0.2, -1.6, -1.8],
      [1.4, 1.1, -2.8],
    ],
    [],
  );

  return (
    <>
      {positions.map((position, index) => (
        <Float key={index} speed={1 + index * 0.2} rotationIntensity={0.8} floatIntensity={1.5}>
          <mesh position={position as [number, number, number]}>
            <icosahedronGeometry args={[0.8, 6]} />
            <MeshDistortMaterial
              color={index % 2 === 0 ? "#38bdf8" : "#f97316"}
              roughness={0.15}
              metalness={0.55}
              distort={0.4}
              speed={1.8}
            />
          </mesh>
        </Float>
      ))}
    </>
  );
}

export function HeroScene() {
  return (
    <div className="hero-scene" aria-hidden>
      <Canvas camera={{ position: [0, 0, 7], fov: 56 }}>
        <ambientLight intensity={0.55} />
        <pointLight intensity={40} position={[0, 1.5, 2]} color="#38bdf8" />
        <pointLight intensity={30} position={[2, -2, 1]} color="#f97316" />
        <FloatingOrbs />
        <OrbitControls enablePan={false} enableZoom={false} autoRotate autoRotateSpeed={0.45} />
      </Canvas>
    </div>
  );
}
