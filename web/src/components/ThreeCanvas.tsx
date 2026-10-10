"use client";

import { useEffect, useRef } from "react";
import * as THREE from "three";

export default function ThreeCanvas() {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const width = container.clientWidth || window.innerWidth;
    const height = container.clientHeight || window.innerHeight;

    // 1. Scene & Camera Setup
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(60, width / height, 1, 1000);
    camera.position.z = 65;

    // 2. WebGL Renderer
    const renderer = new THREE.WebGLRenderer({
      alpha: true,
      antialias: true,
      powerPreference: "high-performance",
    });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setClearColor(0x000000, 0);
    container.appendChild(renderer.domElement);

    // 3. Node Constellation Configuration
    const NODE_COUNT = 160;
    const BOUNDS = { x: 50, y: 35, z: 40 };
    const MAX_DISTANCE = 14;
    const MAX_CONNECTIONS = 600;

    const positions = new Float32Array(NODE_COUNT * 3);
    const velocities = new Float32Array(NODE_COUNT * 3);

    for (let i = 0; i < NODE_COUNT; i++) {
      const i3 = i * 3;
      positions[i3] = (Math.random() - 0.5) * BOUNDS.x * 2;
      positions[i3 + 1] = (Math.random() - 0.5) * BOUNDS.y * 2;
      positions[i3 + 2] = (Math.random() - 0.5) * BOUNDS.z * 2;

      velocities[i3] = (Math.random() - 0.5) * 0.04;
      velocities[i3 + 1] = (Math.random() - 0.5) * 0.04;
      velocities[i3 + 2] = (Math.random() - 0.5) * 0.04;
    }

    // Points
    const pointsGeometry = new THREE.BufferGeometry();
    pointsGeometry.setAttribute(
      "position",
      new THREE.BufferAttribute(positions, 3)
    );

    const pointsMaterial = new THREE.PointsMaterial({
      color: 0x06b6d4, // Cyan-500
      size: 1.8,
      transparent: true,
      opacity: 0.65,
      blending: THREE.AdditiveBlending,
    });

    const pointCloud = new THREE.Points(pointsGeometry, pointsMaterial);
    scene.add(pointCloud);

    // Proximity Lines
    const linePositions = new Float32Array(MAX_CONNECTIONS * 2 * 3);
    const linesGeometry = new THREE.BufferGeometry();
    linesGeometry.setAttribute(
      "position",
      new THREE.BufferAttribute(linePositions, 3)
    );

    const linesMaterial = new THREE.LineBasicMaterial({
      color: 0x38bdf8, // Sky-400
      transparent: true,
      opacity: 0.16,
      blending: THREE.AdditiveBlending,
    });

    const lineSegments = new THREE.LineSegments(linesGeometry, linesMaterial);
    scene.add(lineSegments);

    // 4. Parallax State & Mouse Tracking
    let targetRotX = 0;
    let targetRotY = 0;
    let currentRotX = 0;
    let currentRotY = 0;

    const handleMouseMove = (e: MouseEvent) => {
      const normX = (e.clientX / window.innerWidth) * 2 - 1;
      const normY = (e.clientY / window.innerHeight) * 2 - 1;
      targetRotY = normX * 0.25;
      targetRotX = normY * 0.2;
    };

    window.addEventListener("mousemove", handleMouseMove, { passive: true });

    // 5. Resize Handling via ResizeObserver
    const resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width: newW, height: newH } = entry.contentRect;
        if (newW > 0 && newH > 0) {
          camera.aspect = newW / newH;
          camera.updateProjectionMatrix();
          renderer.setSize(newW, newH);
        }
      }
    });
    resizeObserver.observe(container);

    // 6. Animation Loop
    let animationFrameId: number;

    const animate = () => {
      animationFrameId = requestAnimationFrame(animate);

      // Smooth mouse parallax lerp
      currentRotX += (targetRotX - currentRotX) * 0.05;
      currentRotY += (targetRotY - currentRotY) * 0.05;

      scene.rotation.x = currentRotX;
      scene.rotation.y = currentRotY;

      // Subtle base rotation
      scene.rotation.y += 0.0006;

      // Update node positions with boundary bounce
      for (let i = 0; i < NODE_COUNT; i++) {
        const i3 = i * 3;
        positions[i3] += velocities[i3];
        positions[i3 + 1] += velocities[i3 + 1];
        positions[i3 + 2] += velocities[i3 + 2];

        if (Math.abs(positions[i3]) > BOUNDS.x) velocities[i3] *= -1;
        if (Math.abs(positions[i3 + 1]) > BOUNDS.y) velocities[i3 + 1] *= -1;
        if (Math.abs(positions[i3 + 2]) > BOUNDS.z) velocities[i3 + 2] *= -1;
      }
      pointsGeometry.attributes.position.needsUpdate = true;

      // Compute dynamic proximity links
      let lineIndex = 0;
      for (let i = 0; i < NODE_COUNT; i++) {
        const i3 = i * 3;
        const x1 = positions[i3];
        const y1 = positions[i3 + 1];
        const z1 = positions[i3 + 2];

        for (let j = i + 1; j < NODE_COUNT; j++) {
          const j3 = j * 3;
          const dx = x1 - positions[j3];
          const dy = y1 - positions[j3 + 1];
          const dz = z1 - positions[j3 + 2];
          const distSq = dx * dx + dy * dy + dz * dz;

          if (distSq < MAX_DISTANCE * MAX_DISTANCE) {
            if (lineIndex < MAX_CONNECTIONS) {
              const baseIdx = lineIndex * 6;
              linePositions[baseIdx] = x1;
              linePositions[baseIdx + 1] = y1;
              linePositions[baseIdx + 2] = z1;

              linePositions[baseIdx + 3] = positions[j3];
              linePositions[baseIdx + 4] = positions[j3 + 1];
              linePositions[baseIdx + 5] = positions[j3 + 2];
              lineIndex++;
            }
          }
        }
      }

      linesGeometry.setDrawRange(0, lineIndex * 2);
      linesGeometry.attributes.position.needsUpdate = true;

      renderer.render(scene, camera);
    };

    animate();

    // 7. Cleanup on Unmount
    return () => {
      cancelAnimationFrame(animationFrameId);
      window.removeEventListener("mousemove", handleMouseMove);
      resizeObserver.disconnect();

      pointsGeometry.dispose();
      pointsMaterial.dispose();
      linesGeometry.dispose();
      linesMaterial.dispose();
      renderer.dispose();

      if (container.contains(renderer.domElement)) {
        container.removeChild(renderer.domElement);
      }
    };
  }, []);

  return (
    <div
      ref={containerRef}
      className="pointer-events-none fixed inset-0 -z-10 overflow-hidden select-none"
      aria-hidden="true"
    />
  );
}
