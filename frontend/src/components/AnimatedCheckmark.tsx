import React from "react";
import { motion } from "framer-motion";
import { useMotionPreset, ease } from "@/lib/motion";

interface AnimatedCheckmarkProps {
  className?: string;
  size?: number;
}

export const AnimatedCheckmark: React.FC<AnimatedCheckmarkProps> = ({
  className = "w-3.5 h-3.5",
  size = 16,
}) => {
  const { shouldReduceMotion } = useMotionPreset();

  if (shouldReduceMotion) {
    return (
      <svg
        width={size}
        height={size}
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        className={className}
        data-testid="animated-checkmark"
        aria-hidden="true"
      >
        <circle cx="12" cy="12" r="10" />
        <path d="m9 12 2 2 4-4" />
      </svg>
    );
  }

  return (
    <motion.svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      data-testid="animated-checkmark"
      aria-hidden="true"
      initial={{ scale: 0.8, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      transition={{ duration: 0.2, ease: ease.out }}
    >
      {/* Outer circle draws smoothly */}
      <motion.circle
        cx="12"
        cy="12"
        r="10"
        initial={{ pathLength: 0, opacity: 0 }}
        animate={{ pathLength: 1, opacity: 1 }}
        transition={{ duration: 0.35, ease: ease.out }}
      />
      {/* Checkmark path draws itself */}
      <motion.path
        d="m9 12 2 2 4-4"
        initial={{ pathLength: 0, opacity: 0 }}
        animate={{ pathLength: 1, opacity: 1 }}
        transition={{ duration: 0.3, delay: 0.15, ease: ease.out }}
      />
    </motion.svg>
  );
};
