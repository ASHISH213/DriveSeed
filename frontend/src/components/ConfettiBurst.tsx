import React, { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { useMotionPreset } from "@/lib/motion";

interface ConfettiParticle {
  id: number;
  x: number;
  y: number;
  rotation: number;
  size: number;
  color: string;
}

const COLORS = [
  "var(--accent-1)",
  "var(--accent-2)",
  "var(--success)",
  "var(--warning)",
];

export const ConfettiBurst: React.FC<{ onComplete?: () => void }> = ({
  onComplete,
}) => {
  const { shouldReduceMotion } = useMotionPreset();
  const [particles] = useState<ConfettiParticle[]>(() => {
    const list: ConfettiParticle[] = [];
    const count = 32; // strictly <= 40 particles
    for (let i = 0; i < count; i++) {
      const angle = (i / count) * 2 * Math.PI + (Math.random() - 0.5) * 0.5;
      const distance = 24 + Math.random() * 40;
      list.push({
        id: i,
        x: Math.cos(angle) * distance,
        y: Math.sin(angle) * distance,
        rotation: Math.random() * 360,
        size: 3 + Math.random() * 3,
        color: COLORS[i % COLORS.length],
      });
    }
    return list;
  });

  useEffect(() => {
    const timer = setTimeout(() => {
      onComplete?.();
    }, 600); // strictly <= 600ms
    return () => clearTimeout(timer);
  }, [onComplete]);

  if (shouldReduceMotion) return null;

  return (
    <div
      className="absolute inset-0 pointer-events-none overflow-visible flex items-center justify-center z-20"
      data-testid="confetti-burst"
      aria-hidden="true"
    >
      {particles.map((p) => (
        <motion.span
          key={p.id}
          initial={{
            x: 0,
            y: 0,
            scale: 0,
            opacity: 1,
            rotate: 0,
          }}
          animate={{
            x: p.x,
            y: p.y,
            scale: [0, 1.2, 0.8],
            opacity: [1, 1, 0],
            rotate: p.rotation,
          }}
          transition={{
            duration: 0.55,
            ease: [0.22, 1, 0.36, 1],
          }}
          style={{
            position: "absolute",
            width: p.size,
            height: p.size,
            borderRadius: p.id % 2 === 0 ? "50%" : "1px",
            backgroundColor: p.color,
          }}
        />
      ))}
    </div>
  );
};
