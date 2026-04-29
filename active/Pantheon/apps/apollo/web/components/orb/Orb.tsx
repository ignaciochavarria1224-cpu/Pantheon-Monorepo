"use client";

import { Canvas, useFrame } from "@react-three/fiber";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  AdditiveBlending,
  Color,
  IcosahedronGeometry,
  Mesh,
  ShaderMaterial,
} from "three";
import { useAppStore, ApolloState } from "@/lib/store";
import { orbVertex, orbFragment } from "@/components/orb/orb-shaders";

type StatePreset = {
  core: Color;
  rim: Color;
  intensity: number;
  fresnelPower: number;
};

const STATE_PRESETS: Record<ApolloState, StatePreset> = {
  idle: {
    core: new Color("#003a44"),
    rim: new Color("#00e5ff"),
    intensity: 0.25,
    fresnelPower: 2.6,
  },
  listening: {
    core: new Color("#0090a8"),
    rim: new Color("#5ef6ff"),
    intensity: 0.7,
    fresnelPower: 2.2,
  },
  thinking: {
    core: new Color("#a96d18"),
    rim: new Color("#ffb347"),
    intensity: 0.55,
    fresnelPower: 2.4,
  },
  speaking: {
    core: new Color("#ffb347"),
    rim: new Color("#ffd28a"),
    intensity: 0.85,
    fresnelPower: 2.0,
  },
  error: {
    core: new Color("#ff6868"),
    rim: new Color("#ff9a9a"),
    intensity: 0.9,
    fresnelPower: 1.8,
  },
};

function CoreMesh({ detail }: { detail: number }) {
  const meshRef = useRef<Mesh>(null);
  const haloRef = useRef<Mesh>(null);

  const apolloState = useAppStore((s) => s.apolloState);

  const geometry = useMemo(() => new IcosahedronGeometry(1, detail), [detail]);
  const haloGeometry = useMemo(
    () => new IcosahedronGeometry(1, Math.max(detail - 1, 1)),
    [detail],
  );

  const material = useMemo(
    () =>
      new ShaderMaterial({
        vertexShader: orbVertex,
        fragmentShader: orbFragment,
        transparent: true,
        depthWrite: false,
        blending: AdditiveBlending,
        uniforms: {
          uTime: { value: 0 },
          uAudio: { value: 0 },
          uIntensity: { value: STATE_PRESETS.idle.intensity },
          uColorCore: { value: STATE_PRESETS.idle.core.clone() },
          uColorRim: { value: STATE_PRESETS.idle.rim.clone() },
          uFresnelPower: { value: STATE_PRESETS.idle.fresnelPower },
        },
      }),
    [],
  );

  const haloMaterial = useMemo(
    () =>
      new ShaderMaterial({
        vertexShader: orbVertex,
        fragmentShader: orbFragment,
        transparent: true,
        depthWrite: false,
        blending: AdditiveBlending,
        uniforms: {
          uTime: { value: 0 },
          uAudio: { value: 0 },
          uIntensity: { value: 0.18 },
          uColorCore: { value: new Color("#00111a") },
          uColorRim: { value: STATE_PRESETS.idle.rim.clone() },
          uFresnelPower: { value: 1.6 },
        },
      }),
    [],
  );

  const targetIntensity = useRef(STATE_PRESETS.idle.intensity);
  const targetCore = useRef(STATE_PRESETS.idle.core.clone());
  const targetRim = useRef(STATE_PRESETS.idle.rim.clone());
  const targetFresnel = useRef(STATE_PRESETS.idle.fresnelPower);

  useEffect(() => {
    const preset = STATE_PRESETS[apolloState] ?? STATE_PRESETS.idle;
    targetIntensity.current = preset.intensity;
    targetCore.current.copy(preset.core);
    targetRim.current.copy(preset.rim);
    targetFresnel.current = preset.fresnelPower;
  }, [apolloState]);

  useFrame((_, delta) => {
    const audio = useAppStore.getState().audioLevel;
    const k = Math.min(1, delta * 3.2);

    material.uniforms.uTime.value += delta;
    material.uniforms.uAudio.value += (audio - material.uniforms.uAudio.value) * k * 1.6;
    material.uniforms.uIntensity.value +=
      (targetIntensity.current - material.uniforms.uIntensity.value) * k;
    material.uniforms.uFresnelPower.value +=
      (targetFresnel.current - material.uniforms.uFresnelPower.value) * k;
    (material.uniforms.uColorCore.value as Color).lerp(targetCore.current, k);
    (material.uniforms.uColorRim.value as Color).lerp(targetRim.current, k);

    haloMaterial.uniforms.uTime.value += delta;
    haloMaterial.uniforms.uAudio.value = material.uniforms.uAudio.value;
    haloMaterial.uniforms.uIntensity.value =
      0.15 + material.uniforms.uIntensity.value * 0.35;
    (haloMaterial.uniforms.uColorRim.value as Color).copy(targetRim.current);

    if (meshRef.current) {
      meshRef.current.rotation.y += delta * 0.18;
      meshRef.current.rotation.x += delta * 0.05;
      const breath = 1 + Math.sin(performance.now() * 0.0014) * 0.018 + audio * 0.10;
      meshRef.current.scale.setScalar(breath);
    }
    if (haloRef.current) {
      haloRef.current.rotation.y -= delta * 0.06;
      const haloBreath =
        1.55 + Math.sin(performance.now() * 0.0009) * 0.03 + audio * 0.32;
      haloRef.current.scale.setScalar(haloBreath);
    }
  });

  return (
    <group>
      <mesh ref={haloRef} geometry={haloGeometry} material={haloMaterial} />
      <mesh ref={meshRef} geometry={geometry} material={material} />
    </group>
  );
}

export function Orb({ className = "" }: { className?: string }) {
  const [detail, setDetail] = useState<number>(48);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const { getGPUTier } = await import("detect-gpu");
        const tier = await getGPUTier();
        if (cancelled) return;
        if (tier.tier <= 1) setDetail(16);
        else if (tier.tier === 2) setDetail(32);
        else setDetail(64);
      } catch {
        /* keep default */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className={`relative aspect-square w-full max-w-[460px] ${className}`}>
      <Canvas
        dpr={[1, 2]}
        camera={{ position: [0, 0, 4], fov: 45 }}
        gl={{ antialias: true, alpha: true, powerPreference: "high-performance" }}
      >
        <ambientLight intensity={0.32} />
        <pointLight position={[5, 5, 5]} intensity={1.4} color="#00e5ff" />
        <pointLight position={[-4, -2, -3]} intensity={0.7} color="#ffb347" />
        <CoreMesh detail={detail} />
      </Canvas>
    </div>
  );
}
