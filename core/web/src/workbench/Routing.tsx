import React from "react";
import { Verified } from "./BrandIcons";
import { useLocale } from "./Locale";
import type { RoutingReceipt } from "./types";

// v3 G6: no "use the model" checkbox. The routing table (held-out measurements) chooses the local method or the
// language model per task; this badge says which one ran and why, and what left the machine when the model ran.

const TASKS: Record<string, [string, string]> = {
  chart_plan: ["grafik planı", "chart planning"],
  question_route: ["soru yönlendirme", "question routing"],
  studio_route: ["stüdyo seçimi", "studio choice"],
  decision_focus: ["odak seçimi", "focus selection"],
  decision_narrative: ["karar anlatısı", "decision narrative"],
};
const UNAVAILABLE: Record<string, [string, string]> = {
  not_configured: ["sağlayıcı yapılandırılmamış", "no provider configured"],
  policy_local_only: ["yönetici yalnız yerel çalışmayı seçmiş", "the administrator keeps everything local"],
  daily_budget: ["günlük model bütçesi doldu", "the daily model budget is used up"],
};

const pct = (v?: number | null) => (v == null ? "—" : `%${Math.round(v * 100)}`);

export function RoutingBadge({
  routing,
  providerLabel,
  prefix,
}: {
  routing?: RoutingReceipt | null;
  providerLabel?: string | null;
  /** Names the task when one result carries several badges, e.g. "Focus" and "Narrative". */
  prefix?: string;
}) {
  const { t, locale } = useLocale();
  if (!routing) return null;
  const model = routing.used === "model";
  const task = TASKS[routing.task] ?? [routing.task, routing.task];
  const unmeasured = routing.local_accuracy == null && routing.model_accuracy == null && routing.method === "local";
  const rule = unmeasured
    ? t("bu iş için ölçüm kaydı yok; yerel yöntem kullanılıyor", "no measurement on record for this task; the local method is used")
    : routing.method === "model"
      ? t("bu işte model daha iyi ölçüldü", "the model measured better at this task")
      : routing.method === "local_then_model"
        ? t("önce yerel yöntem; çözemezse model", "local method first; the model when it cannot plan")
        : t("bu işte yerel yöntem daha iyi veya eşit ölçüldü", "the local method measured better or equal at this task");
  const measured =
    routing.local_accuracy != null || routing.model_accuracy != null
      ? t(
          `${routing.n ?? "?"} bağımsız vakada yerel ${pct(routing.local_accuracy)}, model ${pct(routing.model_accuracy)}`,
          `${routing.n ?? "?"} held-out cases: local ${pct(routing.local_accuracy)}, model ${pct(routing.model_accuracy)}`,
        )
      : "";
  const extra = routing.unavailable
    ? t(`Model kullanılmadı: ${UNAVAILABLE[routing.unavailable]?.[0] ?? routing.unavailable}.`, `Model not used: ${UNAVAILABLE[routing.unavailable]?.[1] ?? routing.unavailable}.`)
    : routing.fallback
      ? t("Model yanıtı doğrulamayı geçemedi veya alınamadı; yerel sonuç gösteriliyor.", "The model's reply failed validation or did not arrive; the local result is shown.")
      : "";
  return (
    <details className={"wb-routing" + (model ? " is-model" : "")}>
      <summary>
        <Verified size={16} />
        {prefix ? `${prefix} · ` : ""}
        {model
          ? t(`Planlayan: dil modeli${providerLabel ? ` (${providerLabel})` : ""}`, `Planned by: language model${providerLabel ? ` (${providerLabel})` : ""}`)
          : t("Planlayan: yerel yöntem", "Planned by: local method")}
      </summary>
      <div lang={locale}>
        <p>
          {t(`Seçim otomatik (${task[0]}): ${rule}.`, `Chosen automatically (${task[1]}): ${rule}.`)} {measured && `${measured}.`}
        </p>
        {extra && <p>{extra}</p>}
        <p className="wb-small">
          {model
            ? t(
                "İstek metni sağlayıcıya gitti; veri satırları ve tutarlar gitmedi. Plan doğrulandı, sayılar yerelde hesaplandı.",
                "The request text went to the provider; data rows and amounts did not. The plan was validated and the numbers computed locally.",
              )
            : t("Bu sonuç için hiçbir şey makine dışına gönderilmedi.", "Nothing left the machine for this result.")}
        </p>
      </div>
    </details>
  );
}
