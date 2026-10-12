import React from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useMotionPreset, duration, ease } from "@/lib/motion";

interface AnimatedTickerProps {
  value: string;
  className?: string;
}

export const AnimatedTicker: React.FC<AnimatedTickerProps> = ({
  value,
  className = "",
}) => {
  const { shouldReduceMotion } = useMotionPreset();

  if (shouldReduceMotion) {
    return (
      <span
        className={`font-mono tabular-nums inline-block ${className}`}
        data-testid="animated-ticker"
      >
        {value}
      </span>
    );
  }

  return (
    <span
      className={`font-mono tabular-nums inline-block overflow-hidden ${className}`}
      data-testid="animated-ticker"
    >
      <AnimatePresence mode="popLayout" initial={false}>
        <motion.span
          key={value}
          initial={{ y: "35%", opacity: 0 }}
          animate={{ y: "0%", opacity: 1 }}
          exit={{ y: "-35%", opacity: 0 }}
          transition={{
            duration: duration.fast,
            ease: ease.out,
          }}
          className="inline-block"
        >
          {value}
        </motion.span>
      </AnimatePresence>
    </span>
  );
};
