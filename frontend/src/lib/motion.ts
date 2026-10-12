import { useReducedMotion } from "framer-motion";

export const duration = {
  fast: 0.15,
  base: 0.25,
  slow: 0.4,
} as const;

export const ease = {
  out: [0.22, 1, 0.36, 1] as [number, number, number, number],
} as const;

export const spring = {
  soft: {
    type: "spring" as const,
    stiffness: 220,
    damping: 26,
  },
  snappy: {
    type: "spring" as const,
    stiffness: 400,
    damping: 30,
  },
} as const;

export const stagger = 0.04;

/**
 * Returns motion transitions adapted for user reduced-motion preferences.
 */
export function useMotionPreset() {
  const shouldReduceMotion = useReducedMotion();

  return {
    shouldReduceMotion,
    fadeIn: {
      initial: { opacity: 0 },
      animate: { opacity: 1 },
      exit: { opacity: 0 },
      transition: { duration: duration.fast },
    },
    slideFade: {
      initial: { opacity: 0, y: shouldReduceMotion ? 0 : 8 },
      animate: { opacity: 1, y: 0 },
      exit: { opacity: 0, y: shouldReduceMotion ? 0 : -8 },
      transition: shouldReduceMotion
        ? { duration: duration.fast }
        : { duration: duration.base, ease: ease.out },
    },
    cardHover: shouldReduceMotion
      ? {}
      : {
          whileHover: { y: -2, transition: spring.snappy },
        },
    modal: {
      initial: { opacity: 0, scale: shouldReduceMotion ? 1 : 0.95, y: shouldReduceMotion ? 0 : 8 },
      animate: { opacity: 1, scale: 1, y: 0 },
      exit: { opacity: 0, scale: shouldReduceMotion ? 1 : 0.95, y: shouldReduceMotion ? 0 : 8 },
      transition: shouldReduceMotion
        ? { duration: duration.fast }
        : { duration: duration.base, ease: ease.out },
    },
  };
}
