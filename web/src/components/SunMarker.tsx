// The Sun at the origin, drawn at a constant size on screen: a sphere of fixed
// scene radius grows without bound as the camera zooms in and, on the 1.25 kpc
// maps, ends up covering its neighbours. The label sits a fixed few pixels above.
import { useRef } from "react";
import { useFrame } from "@react-three/fiber";
import { Html } from "@react-three/drei";
import * as THREE from "three";

/** Screen radius of the Sun's disc, px. */
const SUN_PX = 4;

export function SunMarker({ depthTest = true }: { depthTest?: boolean }) {
  const mesh = useRef<THREE.Mesh>(null);
  useFrame(({ camera, size }) => {
    if (!mesh.current) return;
    const cam = camera as THREE.PerspectiveCamera;
    // Scene units per pixel at the Sun's depth.
    const perPx =
      (2 * cam.position.length() * Math.tan(THREE.MathUtils.degToRad(cam.fov / 2))) /
      size.height;
    mesh.current.scale.setScalar(SUN_PX * perPx);
  });
  return (
    <>
      <mesh ref={mesh} renderOrder={2}>
        <sphereGeometry args={[1, 16, 16]} />
        <meshBasicMaterial color="#fff4cc" depthTest={depthTest} />
      </mesh>
      <Html position={[0, 0, 0]} center>
        <div className="star-label sun-label">Sun</div>
      </Html>
    </>
  );
}
