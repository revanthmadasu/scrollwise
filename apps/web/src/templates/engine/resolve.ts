/** Binding + guard resolution for the template engine. */
import type { Binding, Guard, Value } from "./spec";

/** A render scope: the inputs plus any repeat-item aliases and the loop index. */
export type Scope = Record<string, unknown> & { $index?: number };

function isBinding(v: unknown): v is Binding {
  return typeof v === "object" && v !== null && "$bind" in v;
}

/** Walk a dotted path (supports numeric array indices): "images.0.url". */
export function getByPath(root: unknown, path: string): unknown {
  let cur: unknown = root;
  for (const seg of path.split(".")) {
    if (cur == null) return undefined;
    if (Array.isArray(cur)) {
      const i = Number(seg);
      cur = Number.isInteger(i) ? cur[i] : undefined;
    } else if (typeof cur === "object") {
      cur = (cur as Record<string, unknown>)[seg];
    } else {
      return undefined;
    }
  }
  return cur;
}

/** Resolve a literal-or-binding value against the scope. */
export function resolveValue<T>(value: Value<T>, scope: Scope): T | undefined {
  if (isBinding(value)) return getByPath(scope, value.$bind) as T | undefined;
  return value;
}

/** Truthiness used by `when`/`unless`: non-empty string, non-empty array, present object. */
export function isTruthy(guard: Guard, scope: Scope): boolean {
  const path = typeof guard === "string" ? guard : guard.$bind;
  const v = getByPath(scope, path);
  if (v == null) return false;
  if (typeof v === "string") return v.trim().length > 0;
  if (Array.isArray(v)) return v.length > 0;
  return true;
}
