/**
 * Analyst portraits (AW-16). Gemini-generated, one per business domain plus the Context Layer mascot; the
 * choice is stored server-side per subject (workbench_profiles), never in the browser. Ids mirror AVATARS in
 * core/src/workbench.ts. There is no letter avatar: until a choice is made the service returns a
 * deterministic default portrait for the subject.
 */
import React from "react";
import { useLocale } from "./Locale";
import core from "./assets/avatars/analyst-core.jpg";
import retail from "./assets/avatars/analyst-retail.jpg";
import banking from "./assets/avatars/analyst-banking.jpg";
import automotive from "./assets/avatars/analyst-automotive.jpg";
import energy from "./assets/avatars/analyst-energy.jpg";
import telecom from "./assets/avatars/analyst-telecom.jpg";
import logistics from "./assets/avatars/analyst-logistics.jpg";
import health from "./assets/avatars/analyst-health.jpg";

export const AVATARS: { id: string; src: string; tr: string; en: string }[] = [
  { id: "analyst-core", src: core, tr: "Analitik çekirdek", en: "Core analytics" },
  { id: "analyst-retail", src: retail, tr: "Perakende", en: "Retail" },
  { id: "analyst-banking", src: banking, tr: "Bankacılık ve finans", en: "Banking and finance" },
  { id: "analyst-automotive", src: automotive, tr: "Otomotiv", en: "Automotive" },
  { id: "analyst-energy", src: energy, tr: "Enerji", en: "Energy" },
  { id: "analyst-telecom", src: telecom, tr: "Telekom ve ağ", en: "Telecom and network" },
  { id: "analyst-logistics", src: logistics, tr: "Lojistik", en: "Logistics" },
  { id: "analyst-health", src: health, tr: "Sağlık", en: "Healthcare" },
];

export function avatarById(id: string | null | undefined) {
  return AVATARS.find((a) => a.id === id) ?? AVATARS[0]!;
}

/** Decorative portrait: the analyst's name is always printed next to it, so alt stays empty. */
export function AnalystAvatar({ id, size = 32, className = "" }: { id: string; size?: number; className?: string }) {
  return (
    <img
      className={"wb-portrait " + className}
      src={avatarById(id).src}
      alt=""
      width={size}
      height={size}
      decoding="async"
    />
  );
}

/** Portrait picker: a radio group of eight 96px options with visible domain names (Fitts, recognition over recall). */
export function AvatarPicker({
  value,
  saving,
  onChoose,
}: {
  value: string;
  saving: boolean;
  onChoose: (id: string) => void;
}) {
  const { t, locale } = useLocale();
  return (
    <div>
      <p className="wb-avatar-intro">
        {t(
          "Çalışma alanında adınızın yanında görünür. Seçiminiz bu hesap için saklanır.",
          "Shown next to your name in the workspace. Your choice is kept for this account.",
        )}
      </p>
      <div className="wb-avatar-grid" role="radiogroup" aria-label={t("Profil görseli", "Profile portrait")}>
        {AVATARS.map((a) => {
          const selected = a.id === value;
          return (
            <button
              key={a.id}
              type="button"
              role="radio"
              aria-checked={selected}
              className={"wb-avatar-option" + (selected ? " is-selected" : "")}
              disabled={saving}
              onClick={() => onChoose(a.id)}
            >
              <img src={a.src} alt="" width={96} height={96} decoding="async" />
              <span>{locale === "en" ? a.en : a.tr}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
