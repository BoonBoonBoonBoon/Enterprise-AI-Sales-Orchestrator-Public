// Saved idea: CSS-variable parallax (Experimental-4)
// Attach to your left-panel container ref; it updates CSS vars --mx/--my.

import { useEffect } from "react";

export function useCssVarParallax(
  ref: React.RefObject<HTMLElement>,
  options?: { disableOnReducedMotion?: boolean }
) {
  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    const disableOnReducedMotion = options?.disableOnReducedMotion ?? true;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (disableOnReducedMotion && reduced) return;

    const handleMouseMove = (e: MouseEvent) => {
      const rect = el.getBoundingClientRect();
      const x = (e.clientX - rect.left) / rect.width - 0.5;
      const y = (e.clientY - rect.top) / rect.height - 0.5;

      el.style.setProperty("--mx", x.toFixed(3));
      el.style.setProperty("--my", y.toFixed(3));
    };

    const handleMouseLeave = () => {
      el.style.setProperty("--mx", "0");
      el.style.setProperty("--my", "0");
    };

    el.addEventListener("mousemove", handleMouseMove);
    el.addEventListener("mouseleave", handleMouseLeave);

    return () => {
      el.removeEventListener("mousemove", handleMouseMove);
      el.removeEventListener("mouseleave", handleMouseLeave);
    };
  }, [ref, options?.disableOnReducedMotion]);
}
