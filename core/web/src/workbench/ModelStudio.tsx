import React, { useEffect, useState } from "react";
import {
  FlaskConical,
  Loader2,
  Download,
  Upload,
  ArrowRight,
  FolderOpen,
} from "lucide-react";
import { api } from "../api";
import { useLocale } from "./Locale";
import type { DataProfile } from "./Preparation";
const BASE = "/v1/dashboard/workbench";
type Metrics = {
  macro_f1?: number;
  balanced_accuracy?: number;
  accuracy?: number;
  mae?: number;
  rmse?: number;
  r2?: number | null;
  rmsle?: number | null;
  confusion_matrix?: number[][];
  per_class?: { label: string; support: number; recall: number | null }[];
};
type ModelCard = {
  experiment_id: string;
  title: string;
  version: string;
  selected_model: string;
  selection_metric: string;
  sha256: string;
  duration_ms: number;
  recipe: {
    target: string;
    task: string;
    features: string[];
    split: string;
    split_key: string;
    decision_context: string;
    source_sha256: string;
  };
  split: {
    train_rows: number;
    holdout_rows: number;
    cv_folds: number;
    sha256: string;
  };
  holdout: Metrics;
  baseline: Metrics;
  candidates: { model: string; mean: number; std: number }[];
  warnings: string[];
  schema: { numeric: string[]; categorical: string[]; signed_log: string[] };
  source?: { title: string; url: string; description: string };
};
type Saved = {
  experiment_id: string;
  title: string;
  created_at: string;
  model: string;
  task: string;
};
const names: Record<string, [string, string]> = {
  dummy: ["Sabit başlangıç modeli", "Constant baseline"],
  random_forest: ["Rastgele orman", "Random forest"],
  logistic: ["Lojistik regresyon", "Logistic regression"],
  ridge: ["Ridge regresyon", "Ridge regression"],
  smote_forest: ["SMOTE + orman", "SMOTE + forest"],
};
export function ModelStudio({
  csrf,
  busy,
  activity,
}: {
  csrf: string | null;
  busy: boolean;
  activity: (n: number) => void;
}) {
  const { t, locale } = useLocale();
  const [text, setText] = useState(""),
    [name, setName] = useState(""),
    [profile, setProfile] = useState<DataProfile | null>(null);
  const [target, setTarget] = useState(""),
    [features, setFeatures] = useState<string[]>([]),
    [task, setTask] = useState("classification"),
    [split, setSplit] = useState("random"),
    [splitKey, setSplitKey] = useState(""),
    [smote, setSmote] = useState(false),
    [context, setContext] = useState(""),
    [confirmed, setConfirmed] = useState(false);
  const [loading, setLoading] = useState(false),
    [error, setError] = useState(""),
    [card, setCard] = useState<ModelCard | null>(null),
    [saved, setSaved] = useState<Saved[]>([]);
  const locked = busy || loading;
  const fmt = (v: number | null | undefined) =>
    v == null
      ? "—"
      : v.toLocaleString(locale === "tr" ? "tr-TR" : "en-GB", {
          maximumFractionDigits: 3,
        });
  const modelName = (v: string) => (names[v] ? t(...names[v]) : v);
  async function history() {
    const r = await api.get<{ experiments: Saved[] }>(BASE + "/ml");
    if (r.ok) setSaved(r.data.experiments);
    else setError(r.error.detail);
  }
  useEffect(() => {
    void history();
  }, []);
  async function inspect(csv: string, file: string) {
    setText(csv);
    setName(file);
    setProfile(null);
    setCard(null);
    setTarget("");
    setFeatures([]);
    setConfirmed(false);
    setError("");
    const r = await api.post<DataProfile>(BASE + "/prepare", { csv }, csrf);
    if (r.ok) setProfile(r.data);
    else setError(r.error.detail);
  }
  async function sample(kind: string) {
    if (locked) return;
    setLoading(true);
    activity(1);
    setError("");
    try {
      const r = await fetch(BASE + "/ml-sample/" + kind + ".csv", {
        credentials: "same-origin",
      });
      if (!r.ok)
        throw new Error(t("Örnek veri açılamadı.", "Could not open sample."));
      await inspect(await r.text(), kind + ".csv");
      setTask(kind === "wine" ? "classification" : "regression");
      setContext(
        kind === "wine"
          ? t(
              "Bir gözlem bir şarap örneğidir. Kimyasal ölçümlerle çeşit sınıfını tahmin edeceğim.",
              "One observation is one wine sample. Predict cultivar from available chemical measurements.",
            )
          : t(
              "Bir gözlem veri setindeki bir kayıttır. Başlangıç ölçümleriyle bir yıl sonraki progression hedefini karşılaştıracağım.",
              "One observation is one dataset record. Compare one-year progression using baseline measurements.",
            ),
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
      activity(-1);
    }
  }
  async function train() {
    if (locked) return;
    setLoading(true);
    activity(1);
    setError("");
    try {
      const r = await api.post<ModelCard>(
        BASE + "/ml",
        {
          csv: text,
          title: name.replace(/\.csv$/i, "") + " · " + target,
          target,
          features,
          task,
          split,
          split_key: splitKey,
          smote,
          decision_context: context,
          features_available: confirmed,
        },
        csrf,
      );
      if (r.ok) {
        setCard(r.data);
        void history();
      } else setError(r.error.detail);
    } finally {
      setLoading(false);
      activity(-1);
    }
  }
  function download() {
    if (!card) return;
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(card, null, 2)], { type: "application/json" }),
    );
    const a = document.createElement("a");
    a.href = url;
    a.download = "model-card-" + card.experiment_id + ".json";
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  return (
    <div className="wb-model-studio">
      {card ? (
        <>
          <div className="wb-model-result-head">
            <span className="wb-badge blue">
              {t("Bağımsız test sonucu", "Held-out test result")}
            </span>
            <h3>{card.title}</h3>
            <p>
              {modelName(card.selected_model)} · {card.split.train_rows}{" "}
              {t("eğitim", "development")} / {card.split.holdout_rows}{" "}
              {t("test gözlemi", "holdout observations")}
            </p>
          </div>
          <div className="wb-table-wrap">
            <table>
              <caption>
                {t(
                  "Aday yalnız eğitimdeki 3 fold sonucuyla seçildi. Test kümesi çoğaltılmadı.",
                  "Selected using 3 training folds only. The test set was not resampled.",
                )}
              </caption>
              <thead>
                <tr>
                  <th>{t("Ölçüm", "Metric")}</th>
                  <th>{t("Başlangıç", "Baseline")}</th>
                  <th>{t("Seçilen model", "Selected model")}</th>
                </tr>
              </thead>
              <tbody>
                {(card.recipe.task === "classification"
                  ? [
                      ["macro_f1", "Macro F1"],
                      [
                        "balanced_accuracy",
                        t("Dengeli doğruluk", "Balanced accuracy"),
                      ],
                      ["accuracy", t("Doğruluk", "Accuracy")],
                    ]
                  : [
                      ["mae", "MAE"],
                      ["rmse", "RMSE"],
                      ["r2", "R²"],
                      ["rmsle", "RMSLE"],
                    ]
                ).map(([key, label]) => (
                  <tr key={key}>
                    <th scope="row">{label}</th>
                    <td>
                      {fmt(
                        card.baseline[key as keyof Metrics] as number | null,
                      )}
                    </td>
                    <td>
                      <strong>
                        {fmt(
                          card.holdout[key as keyof Metrics] as number | null,
                        )}
                      </strong>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="wb-muted">
            {card.recipe.task === "classification"
              ? t(
                  "F1 ve doğruluk 0–1 arasındadır; yüksek daha iyidir. Sınıf desteğini ve hata dağılımını birlikte inceleyin.",
                  "F1 and accuracy range from 0 to 1; higher is better. Inspect class support and errors together.",
                )
              : t(
                  "MAE/RMSE hedefin özgün birimindedir; düşük daha iyidir. RMSLE negatif hedef/tahmin olduğunda gösterilmez.",
                  "MAE/RMSE use original target units; lower is better. RMSLE is unavailable for negative targets/predictions.",
                )}
          </p>
          <details className="wb-prep-details">
            <summary>
              {t("Adaylar ve hata dağılımı", "Candidates and error breakdown")}
            </summary>
            <div className="wb-table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>{t("Aday", "Candidate")}</th>
                    <th>{card.selection_metric}</th>
                    <th>{t("Fold sapması", "Fold deviation")}</th>
                  </tr>
                </thead>
                <tbody>
                  {card.candidates.map((c) => (
                    <tr key={c.model}>
                      <th scope="row">{modelName(c.model)}</th>
                      <td>{fmt(c.mean)}</td>
                      <td>{fmt(c.std)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {card.holdout.per_class && (
              <div className="wb-table-wrap">
                <table>
                  <caption>
                    {t("Sınıf bazında bağımsız test", "Holdout by class")}
                  </caption>
                  <thead>
                    <tr>
                      <th>{t("Sınıf", "Class")}</th>
                      <th>{t("Gözlem", "Support")}</th>
                      <th>Recall</th>
                    </tr>
                  </thead>
                  <tbody>
                    {card.holdout.per_class.map((c) => (
                      <tr key={c.label}>
                        <th scope="row">{c.label}</th>
                        <td>{c.support}</td>
                        <td>{fmt(c.recall)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            {card.holdout.confusion_matrix && (
              <pre aria-label={t("Karışıklık matrisi", "Confusion matrix")}>
                {t(
                  "Satır: gerçek / sütun: tahmin; sınıf sırası yukarıdakiyle aynı.",
                  "Row: actual / column: predicted; class order matches the table above.",
                )}
                \n
                {card.holdout.confusion_matrix
                  .map((r) => r.join("  "))
                  .join("\n")}
              </pre>
            )}
          </details>
          {card.source && (
            <p className="wb-muted">
              <a href={card.source.url} target="_blank" rel="noreferrer">
                {card.source.title}
              </a>{" "}
              · {card.source.description}
            </p>
          )}
          <details className="wb-prep-details">
            <summary>
              {t("Yöntem, kapsam ve kanıt", "Method, scope and evidence")}
            </summary>
            <p>{card.recipe.decision_context}</p>
            <p>
              {t("Ayrım", "Split")}: {card.recipe.split} {card.recipe.split_key}{" "}
              · {fmt(card.duration_ms / 1000)} s
            </p>
            <p>
              {t("Özellikler", "Features")}: {card.recipe.features.join(", ")}
            </p>
            <p>
              {t(
                "Eğitimden seçilen signed-log dönüşümleri",
                "Signed-log transforms selected on training",
              )}
              : {card.schema.signed_log.join(", ") || "—"}
            </p>
            <ul>
              {card.warnings.map((w) => (
                <li key={w}>{w}</li>
              ))}
            </ul>
            <code>{card.sha256}</code>
          </details>
          <div className="wb-prep-actions">
            <button
              className="wb-btn"
              disabled={locked}
              onClick={() => setCard(null)}
            >
              {t("Yeni deney", "New experiment")}
            </button>
            <button className="wb-btn wb-primary" onClick={download}>
              <Download size={16} />
              {t("Model kartını indir", "Download model card")}
            </button>
          </div>
        </>
      ) : (
        <>
          <p>
            {t(
              "Bir hedef seçin, basit modelleri karşılaştırın ve ayrılmış test verisinde ne kadar işe yaradıklarını görün.",
              "Choose a target, compare simple models, and evaluate them on held-out observations.",
            )}
          </p>
          <div className="wb-model-examples">
            <button
              className="wb-btn"
              disabled={locked}
              onClick={() => void sample("wine")}
            >
              {t("Wine · sınıflama örneği", "Wine · classification sample")}
            </button>
            <button
              className="wb-btn"
              disabled={locked}
              onClick={() => void sample("diabetes")}
            >
              {t("Diabetes · regresyon örneği", "Diabetes · regression sample")}
            </button>
          </div>
          <label className="wb-upload">
            <Upload size={23} />
            <strong>
              {name || t("Kendi CSV dosyanızı seçin", "Choose your CSV")}
            </strong>
            <span>
              {t(
                "100–3.000 satır · en çok 30 özellik · bu makinede işlenir",
                "100–3,000 rows · up to 30 features · processed locally",
              )}
            </span>
            <input
              type="file"
              accept=".csv,text/csv"
              disabled={locked}
              onChange={async (e) => {
                const file = e.target.files?.[0];
                if (!file) return;
                if (file.size > 2_000_000) {
                  setError(t("CSV sınırı 2 MB.", "CSV limit is 2 MB."));
                  return;
                }
                setLoading(true);
                activity(1);
                try {
                  await inspect(
                    new TextDecoder("utf-8", { fatal: true }).decode(
                      await file.arrayBuffer(),
                    ),
                    file.name,
                  );
                } catch {
                  setError(t("UTF-8 CSV kullanın.", "Use UTF-8 CSV."));
                } finally {
                  setLoading(false);
                  activity(-1);
                }
              }}
            />
          </label>
          {profile && (
            <>
              <div className="wb-prep-summary">
                <span>
                  <b>{profile.profile.rows}</b> {t("gözlem", "observations")}
                </span>
                <span>
                  <b>{profile.profile.columns.length}</b>{" "}
                  {t("sütun", "columns")}
                </span>
                <span>
                  <b>{profile.profile.duplicate_rows}</b>{" "}
                  {t("tam tekrar", "exact duplicates")}
                </span>
              </div>
              <div className="wb-prep-mapping">
                <label className="wb-field">
                  {t("Görev", "Task")}
                  <select
                    value={task}
                    disabled={locked}
                    onChange={(e) => {
                      setTask(e.target.value);
                      setSmote(false);
                    }}
                  >
                    <option value="classification">
                      {t("Sınıflama · kategori", "Classification · category")}
                    </option>
                    <option value="regression">
                      {t("Regresyon · sayı", "Regression · number")}
                    </option>
                  </select>
                </label>
                <label className="wb-field">
                  {t("Hedef sütun", "Target column")}
                  <select
                    value={target}
                    disabled={locked}
                    onChange={(e) => {
                      setTarget(e.target.value);
                      setFeatures((f) => f.filter((c) => c !== e.target.value));
                    }}
                  >
                    <option value="">
                      {t("Hedef seçin", "Choose target")}
                    </option>
                    {profile.profile.columns.map((c) => (
                      <option key={c.name}>{c.name}</option>
                    ))}
                  </select>
                </label>
              </div>
              <fieldset className="wb-model-features">
                <legend>
                  {t(
                    "Hedef bilinmeden önce mevcut özellikler",
                    "Features available before the outcome",
                  )}
                </legend>
                <button
                  className="wb-text-btn"
                  disabled={!target || locked}
                  onClick={() =>
                    setFeatures(
                      profile.profile.columns
                        .filter(
                          (c) =>
                            c.name !== target &&
                            c.name !== splitKey &&
                            ["integer", "number"].includes(c.type),
                        )
                        .slice(0, 30)
                        .map((c) => c.name),
                    )
                  }
                >
                  {t("Sayısal alanları seç", "Select numeric fields")}
                </button>
                <div>
                  {profile.profile.columns
                    .filter((c) => c.name !== target && c.name !== splitKey)
                    .map((c) => (
                      <label key={c.name}>
                        <input
                          type="checkbox"
                          disabled={locked}
                          checked={features.includes(c.name)}
                          onChange={(e) =>
                            setFeatures((f) =>
                              e.target.checked
                                ? [...f, c.name]
                                : f.filter((v) => v !== c.name),
                            )
                          }
                        />
                        <span>{c.name}</span>
                      </label>
                    ))}
                </div>
                <small>
                  {features.length} / 30{" "}
                  {t(
                    "seçili. Kimlik, gelecek bilgi ve hedeften türeyen sütunları çıkartın.",
                    "selected. Exclude identifiers, future information and target-derived columns.",
                  )}
                </small>
              </fieldset>
              <div className="wb-prep-mapping">
                <label className="wb-field">
                  {t("Veri ayrımı", "Data split")}
                  <select
                    value={split}
                    disabled={locked}
                    onChange={(e) => {
                      setSplit(e.target.value);
                      setSplitKey("");
                    }}
                  >
                    <option value="random">
                      {t(
                        "Bağımsız gözlemler · rastgele",
                        "Independent observations · random",
                      )}
                    </option>
                    <option value="group">
                      {t(
                        "Aynı kişi/kurum ayrı kalmasın · grup",
                        "Keep entities together · group",
                      )}
                    </option>
                    <option value="time">
                      {t(
                        "Geleceği geçmişle tahmin et · zaman",
                        "Predict future from past · time",
                      )}
                    </option>
                  </select>
                </label>
                {split !== "random" && (
                  <label className="wb-field">
                    {t("Ayrım sütunu", "Split column")}
                    <select
                      disabled={locked}
                      value={splitKey}
                      onChange={(e) => {
                        setSplitKey(e.target.value);
                        setFeatures((f) =>
                          f.filter((c) => c !== e.target.value),
                        );
                      }}
                    >
                      <option value="">
                        {t("Sütun seçin", "Choose column")}
                      </option>
                      {profile.profile.columns
                        .filter((c) => c.name !== target)
                        .map((c) => (
                          <option key={c.name}>{c.name}</option>
                        ))}
                    </select>
                  </label>
                )}
              </div>
              <label className="wb-field">
                {t(
                  "Karar anı ve gözlem birimi",
                  "Decision time and observation unit",
                )}
                <textarea
                  rows={3}
                  maxLength={500}
                  value={context}
                  disabled={locked}
                  onChange={(e) => setContext(e.target.value)}
                  placeholder={t(
                    "Bir satır neyi temsil ediyor? Bu tahmin ne zaman kullanılacak?",
                    "What does one row represent? When will the prediction be used?",
                  )}
                />
              </label>
              <div className="wb-prep-options">
                {task === "classification" && (
                  <label>
                    <input
                      type="checkbox"
                      checked={smote}
                      disabled={locked}
                      onChange={(e) => setSmote(e.target.checked)}
                    />
                    {t(
                      "Sayısal veride SMOTE adayını da karşılaştır",
                      "Also compare a SMOTE candidate for numeric data",
                    )}
                  </label>
                )}
                <label>
                  <input
                    type="checkbox"
                    checked={confirmed}
                    disabled={locked}
                    onChange={(e) => setConfirmed(e.target.checked)}
                  />
                  {t(
                    "Seçtiğim özellikler hedef sonucu bilmeden önce mevcuttur.",
                    "The selected features are available before the target outcome is known.",
                  )}
                </label>
              </div>
              <p className="wb-muted">
                {t(
                  "%20 test verisi ayrılır; seçim yalnız eğitimde 3 fold ile yapılır. Tekrarlanan deneyler keşif amaçlıdır. Eğitilmiş model ve ham dosya saklanmaz; sonuç kartınız hesabınızda kalır.",
                  "20% is held out; selection uses 3 training folds only. Repeated experiments are exploratory. The fitted model and raw file are not stored; your result card stays in your account.",
                )}
              </p>
              <button
                className="wb-btn wb-primary"
                disabled={
                  locked ||
                  !target ||
                  !features.length ||
                  features.length > 30 ||
                  !confirmed ||
                  context.trim().length < 12 ||
                  (split !== "random" && !splitKey)
                }
                onClick={() => void train()}
              >
                {loading ? (
                  <Loader2 className="spin" size={16} />
                ) : (
                  <FlaskConical size={16} />
                )}{" "}
                {t("Modelleri karşılaştır", "Compare models")}
              </button>
            </>
          )}
          {saved.length > 0 && (
            <details className="wb-prep-details">
              <summary>
                {t("Kaydedilmiş deneylerim", "My saved experiments")} ·{" "}
                {saved.length}
              </summary>
              <div className="wb-model-history">
                {saved.map((s) => (
                  <button
                    key={s.experiment_id}
                    className="wb-btn"
                    disabled={locked}
                    onClick={async () => {
                      const r = await api.get<ModelCard>(
                        BASE + "/ml/" + s.experiment_id,
                      );
                      if (r.ok) setCard(r.data);
                      else setError(r.error.detail);
                    }}
                  >
                    <FolderOpen size={15} />
                    <span>{s.title}</span>
                    <ArrowRight size={15} />
                  </button>
                ))}
              </div>
            </details>
          )}
        </>
      )}
      {loading && (
        <p role="status" className="wb-muted">
          {t("Veri ve model işlemi sürüyor…", "Processing data and models…")}
        </p>
      )}
      {error && (
        <p role="alert" className="wb-error-text">
          {error}
        </p>
      )}
    </div>
  );
}
