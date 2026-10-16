// Phase 4 replaces the earlier adviSU quota-style adaptation with actual request state.
import React from "react";
import { useLocale } from "./Locale";
export function UsageMeter({ count }: { count: number }) {
  const { t } = useLocale();
  return (
    <span className="wb-request-state" role="status" aria-live="polite">
      {count ? t("Hesaplanıyor…", "Computing…") : t("Hazır", "Ready")}
    </span>
  );
}
