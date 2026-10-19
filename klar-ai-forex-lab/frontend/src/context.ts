import { createContext, useContext } from "react";
import type { Dataset } from "./api";

export interface LabContext {
  dark: boolean;
  datasets: Dataset[];
  active: Dataset | null;
  setActiveId: (id: number) => void;
  reloadDatasets: () => void;
}

export const Lab = createContext<LabContext | null>(null);

export function useLab(): LabContext {
  const ctx = useContext(Lab);
  if (!ctx) throw new Error("useLab måste användas inom <Lab.Provider>");
  return ctx;
}
