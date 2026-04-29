"use client";

import { Canvas, useFrame } from "@react-three/fiber";
import { Icosahedron, Sphere } from "@react-three/drei";
import { useRef } from "react";
import { Mesh, MeshStandardMaterial, Color } from "three";
import { useAppStore, ApolloState } from "@/lib/store";

const STATE_COLOR: Record<ApolloState, string> = {
  idle: "#00e5ff",
  listening: "#5ef6ff",
  thinking: "#ffb347",
  speaking: "#ffd28a",
  error: "#ff6868",
};

function CoreMesh() {
  const meshRef = useRef<Mesh>(null);
  const haloRef = useRef<Mesh>(null);
  const apolloState = useAppStore((s) => s.apolloState);
  const audioLevel = useAppStore((s) => s.audioLevel);

  useFrame((_, delta) => {
    const target = STATE_COLOR[apolloState];
    if (meshRef.current) {
      const mat = meshRef.current.material as MeshStandardMaterial;
      mat.emissive.lerp(new Color(target), 0.08);
      const pulseScale = 1 + Math.sin(performance.now() * 0.0014) * 0.015 + audioLevel * 0.18;
      meshRef.current.scale.setScalar(pulseScale);
      meshRef.current.rotation.y += delta * 0.18;
      meshRef.current.rotation.x += delta * 0.05;
    }
    if (haloRef.current) {
      const mat = haloRef.current.material as MeshStandardMaterial;
      mat.emissive.lerp(new Color(target), 0.05);
      const haloScale = 1.6 + Math.sin(performance.now() * 0.0009) * 0.04 + audioLevel * 0.32;
      haloRef.current.scale.setScalar(haloScale);
      haloRef.current.rotation.y -= delta * 0.07;
    }
  });

  return (
    <group>
      <Icosahedron ref={meshRef} args={[1, 2]}>
        <meshStandardMaterial
          color="#020a14"
          emissive="#00e5ff"
          emissiveIntensity={1.2}
          metalness={0.3}
          roughness={0.55}
          wireframe
        />
      </Icosahedron>
      <Sphere ref={haloRef} args={[1, 32, 32]}>
        <meshStandardMaterial
          color="#00111a"
          emissive="#00e5ff"
          emissiveIntensity={0.18}
          transparent
          opacity={0.18}
          metalness={0.1}
          roughness={1}
        />
      </Sphere>
    </group>
  );
}

export function Orb({ className = "" }: { className?: string }) {
  return (
    <div className={`relative aspect-square w-full max-w-[460px] ${className}`}>
      <Canvas
        dpr={[1, 2]}
        camera={{ position: [0, 0, 4], fov: 45 }}
        gl={{ antialias: true, alpha: true }}
      >
        <ambientLight intensity={0.32} />
        <pointLight position={[5, 5, 5]} intensity={1.4} color="#00e5ff" />
        <pointLight position={[-4, -2, -3]} intensity={0.7} color="#ffb347" />
        <CoreMesh />
      </Canvas>
    </div>
  );
}
