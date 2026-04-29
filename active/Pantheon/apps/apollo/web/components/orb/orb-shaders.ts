/**
 * GLSL for the Apollo orb.
 * Vertex: 3D simplex-noise FBM displacement modulated by audio level + state amplitude.
 * Fragment: Fresnel rim + radial core glow + state-driven cyan↔gold tint.
 *
 * Uniforms expected on the ShaderMaterial:
 *   uTime          float
 *   uAudio         float [0,1]
 *   uIntensity     float (state amplitude — drives displacement strength)
 *   uColorCore     vec3
 *   uColorRim      vec3
 *   uFresnelPower  float
 */

export const orbVertex = /* glsl */ `
uniform float uTime;
uniform float uAudio;
uniform float uIntensity;

varying vec3 vNormal;
varying vec3 vViewPosition;
varying float vDisplacement;

// Simplex noise 3D (Ashima)
vec4 permute(vec4 x){return mod(((x*34.0)+1.0)*x, 289.0);}
vec4 taylorInvSqrt(vec4 r){return 1.79284291400159 - 0.85373472095314 * r;}
float snoise(vec3 v){
  const vec2 C = vec2(1.0/6.0, 1.0/3.0);
  const vec4 D = vec4(0.0, 0.5, 1.0, 2.0);
  vec3 i  = floor(v + dot(v, C.yyy));
  vec3 x0 = v - i + dot(i, C.xxx);
  vec3 g = step(x0.yzx, x0.xyz);
  vec3 l = 1.0 - g;
  vec3 i1 = min(g.xyz, l.zxy);
  vec3 i2 = max(g.xyz, l.zxy);
  vec3 x1 = x0 - i1 + C.xxx;
  vec3 x2 = x0 - i2 + C.yyy;
  vec3 x3 = x0 - D.yyy;
  i = mod(i, 289.0);
  vec4 p = permute(permute(permute(
            i.z + vec4(0.0, i1.z, i2.z, 1.0))
          + i.y + vec4(0.0, i1.y, i2.y, 1.0))
          + i.x + vec4(0.0, i1.x, i2.x, 1.0));
  float n_ = 1.0/7.0;
  vec3 ns = n_ * D.wyz - D.xzx;
  vec4 j = p - 49.0 * floor(p * ns.z * ns.z);
  vec4 x_ = floor(j * ns.z);
  vec4 y_ = floor(j - 7.0 * x_);
  vec4 x = x_ * ns.x + ns.yyyy;
  vec4 y = y_ * ns.x + ns.yyyy;
  vec4 h = 1.0 - abs(x) - abs(y);
  vec4 b0 = vec4(x.xy, y.xy);
  vec4 b1 = vec4(x.zw, y.zw);
  vec4 s0 = floor(b0)*2.0 + 1.0;
  vec4 s1 = floor(b1)*2.0 + 1.0;
  vec4 sh = -step(h, vec4(0.0));
  vec4 a0 = b0.xzyw + s0.xzyw*sh.xxyy;
  vec4 a1 = b1.xzyw + s1.xzyw*sh.zzww;
  vec3 p0 = vec3(a0.xy, h.x);
  vec3 p1 = vec3(a0.zw, h.y);
  vec3 p2 = vec3(a1.xy, h.z);
  vec3 p3 = vec3(a1.zw, h.w);
  vec4 norm = taylorInvSqrt(vec4(dot(p0,p0), dot(p1,p1), dot(p2,p2), dot(p3,p3)));
  p0 *= norm.x; p1 *= norm.y; p2 *= norm.z; p3 *= norm.w;
  vec4 m = max(0.6 - vec4(dot(x0,x0), dot(x1,x1), dot(x2,x2), dot(x3,x3)), 0.0);
  m = m * m;
  return 42.0 * dot(m*m, vec4(dot(p0,x0), dot(p1,x1), dot(p2,x2), dot(p3,x3)));
}

// FBM — fractal Brownian motion of simplex noise
float fbm(vec3 p) {
  float total = 0.0;
  float amp   = 0.5;
  float freq  = 1.0;
  for (int i = 0; i < 4; i++) {
    total += snoise(p * freq) * amp;
    freq  *= 2.0;
    amp   *= 0.5;
  }
  return total;
}

void main() {
  vNormal = normalize(normalMatrix * normal);

  float t = uTime * 0.32;
  vec3 noisePos = position * 1.4 + vec3(t, t * 0.7, t * 0.4);

  float n = fbm(noisePos);
  float displacement = n * (0.10 + uIntensity * 0.18 + uAudio * 0.42);
  vDisplacement = displacement;

  vec3 displaced = position + normal * displacement;

  vec4 mvPosition = modelViewMatrix * vec4(displaced, 1.0);
  vViewPosition = -mvPosition.xyz;
  gl_Position = projectionMatrix * mvPosition;
}
`;

export const orbFragment = /* glsl */ `
uniform float uTime;
uniform float uAudio;
uniform float uIntensity;
uniform vec3  uColorCore;
uniform vec3  uColorRim;
uniform float uFresnelPower;

varying vec3 vNormal;
varying vec3 vViewPosition;
varying float vDisplacement;

void main() {
  vec3 viewDir = normalize(vViewPosition);
  vec3 normal  = normalize(vNormal);

  // Fresnel — strongest at glancing angles (rim)
  float fres = pow(1.0 - max(dot(normal, viewDir), 0.0), uFresnelPower);

  // Core pulse — bright at facing-forward, dimmer toward rim
  float core = pow(max(dot(normal, viewDir), 0.0), 1.4);

  // Slow breathing aura, accelerated by audio
  float pulse = 0.5 + 0.5 * sin(uTime * 1.2 + vDisplacement * 6.0);
  pulse = mix(pulse, 1.0, uAudio * 0.6);

  vec3 color = mix(uColorCore * core * (0.55 + pulse * 0.25),
                   uColorRim  * fres,
                   smoothstep(0.0, 1.0, fres));

  // Boost intensity with audio + state
  color *= (1.0 + uIntensity * 0.5 + uAudio * 0.85);

  // Slight purple-ish darkening in deep folds — adds depth
  color -= 0.05 * vec3(0.1, 0.05, 0.18) * (1.0 - fres);

  // Subtle alpha — translucent rim, opaque-ish core
  float alpha = clamp(fres * 0.95 + core * 0.7, 0.0, 1.0);

  gl_FragColor = vec4(color, alpha);
}
`;
