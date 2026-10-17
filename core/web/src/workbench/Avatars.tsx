/**
 * Analyst portraits (AW-16). Gemini-generated, one per business domain plus the Context Layer mascot; the
 * choice is stored server-side per subject (workbench_profiles), never in the browser. Ids mirror AVATARS in
 * core/src/workbench.ts. There is no letter avatar: until a choice is made the service returns a
 * deterministic default portrait for the subject.
 */
import React from "react";
import { useLocale } from "./Locale";
import core from "./assets/avatars/analyst-core.jpg";
import analyst from "./assets/avatars/analyst-analyst.jpg";
import strategist from "./assets/avatars/analyst-strategist.jpg";
import retail from "./assets/avatars/analyst-retail.jpg";
import banking from "./assets/avatars/analyst-banking.jpg";
import automotive from "./assets/avatars/analyst-automotive.jpg";
import energy from "./assets/avatars/analyst-energy.jpg";
import telecom from "./assets/avatars/analyst-telecom.jpg";
import logistics from "./assets/avatars/analyst-logistics.jpg";
import health from "./assets/avatars/analyst-health.jpg";
import mascotHanging from "./assets/mascot/mascot-hanging.png";
import mascotReading from "./assets/mascot/mascot-reading.png";
import mascotWaving from "./assets/mascot/mascot-waving.png";
import mascotSearching from "./assets/mascot/mascot-searching.png";

/** One-word names; the domain is carried by the portrait itself (outfit and pin). */
export const AVATARS: { id: string; src: string; tr: string; en: string }[] = [
  { id: "analyst-core", src: core, tr: "Kontekst", en: "Context" },
  { id: "analyst-analyst", src: analyst, tr: "Analist", en: "Analyst" },
  { id: "analyst-strategist", src: strategist, tr: "Stratejist", en: "Strategist" },
  { id: "analyst-retail", src: retail, tr: "Perakendeci", en: "Retailer" },
  { id: "analyst-banking", src: banking, tr: "Bankacı", en: "Banker" },
  { id: "analyst-automotive", src: automotive, tr: "Otomov", en: "Mechanic" },
  { id: "analyst-energy", src: energy, tr: "Enerjik", en: "Sparky" },
  { id: "analyst-telecom", src: telecom, tr: "Telekomcu", en: "Operator" },
  { id: "analyst-logistics", src: logistics, tr: "Kargocu", en: "Courier" },
  { id: "analyst-health", src: health, tr: "Sağlıkçı", en: "Medic" },
];

export function avatarById(id: string | null | undefined) {
  return AVATARS.find((a) => a.id === id) ?? AVATARS[0]!;
}

/**
 * The Context Layer mascot in four poses (AW-16): the same Gemini character as the "Kontekst" portrait, generated
 * in the same conversation on a flat key colour and cut out to transparent PNGs at twice their display size.
 * hanging: sidebar brand · reading: Chart Studio · waving: sign-in and getting started · searching: empty states.
 */
export const MASCOT = { hanging: mascotHanging, reading: mascotReading, waving: mascotWaving, searching: mascotSearching };

export function Mascot({ pose, size, className = "" }: { pose: keyof typeof MASCOT; size: number; className?: string }) {
  return (
    <img
      className={`wb-mascot wb-mascot-${pose} ${className}`.trim()}
      src={MASCOT[pose]}
      alt=""
      width={size}
      height={size}
      decoding="async"
      draggable={false}
    />
  );
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

/** Portrait picker: a radio group of ten 80px options in two rows of five, each with its one-word name. */
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
              <img src={a.src} alt="" width={80} height={80} decoding="async" />
              <span>{locale === "en" ? a.en : a.tr}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
