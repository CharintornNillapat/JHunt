"use client";

import React, { useRef, useState, useCallback } from "react";
import { cn } from "@/lib/utils";

interface SpotlightCardProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
  className?: string;
  spotlightColor?: string;
}

export default function SpotlightCard({
  children,
  className,
  spotlightColor = "rgba(6, 182, 212, 0.12)",
  ...props
}: SpotlightCardProps) {
  const cardRef = useRef<HTMLDivElement>(null);
  const [mousePos, setMousePos] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [isHovered, setIsHovered] = useState(false);

  const handleMouseMove = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    if (!cardRef.current) return;
    const rect = cardRef.current.getBoundingClientRect();
    setMousePos({
      x: e.clientX - rect.left,
      y: e.clientY - rect.top,
    });
  }, []);

  return (
    <div
      ref={cardRef}
      onMouseMove={handleMouseMove}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      className={cn(
        "relative rounded-xl border border-white/[0.07] bg-[#0d0e12] overflow-hidden transition-all duration-200 ease-out group",
        "hover:border-white/[0.14] hover:-translate-y-0.5 hover:shadow-xl hover:shadow-cyan-950/20 active:translate-y-0",
        "motion-reduce:hover:translate-y-0 motion-reduce:transition-none",
        className
      )}
      {...props}
    >
      {/* Radial Spotlight Glow */}
      <div
        className="pointer-events-none absolute -inset-px transition-opacity duration-300 z-0"
        style={{
          opacity: isHovered ? 1 : 0,
          background: `radial-gradient(160px circle at ${mousePos.x}px ${mousePos.y}px, ${spotlightColor}, transparent 80%), radial-gradient(420px circle at ${mousePos.x}px ${mousePos.y}px, rgba(6, 182, 212, 0.04), transparent 80%)`,
        }}
        aria-hidden="true"
      />
      {/* Subtle border sheen */}
      <div
        className="pointer-events-none absolute inset-0 rounded-xl transition-opacity duration-300 z-0"
        style={{
          opacity: isHovered ? 0.8 : 0,
          boxShadow: "inset 0 0 0 1px rgba(255, 255, 255, 0.12)",
        }}
        aria-hidden="true"
      />
      {/* Card Content Container */}
      <div className="relative z-10 w-full h-full flex flex-col">{children}</div>
    </div>
  );
}
