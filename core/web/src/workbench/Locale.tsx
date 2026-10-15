// Adapted from adviSU LocaleContext: one typed context and translation boundary.
import { createContext, useContext } from "react";
import type { Locale } from "./types";
const Ctx = createContext<Locale>("tr");
export const LocaleProvider = Ctx.Provider;
export function useLocale() {
  const locale = useContext(Ctx);
  return { locale, t: (tr: string, en: string) => (locale === "tr" ? tr : en) };
}
