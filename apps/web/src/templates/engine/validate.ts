/**
 * Validate + clamp inputs against a field-spec. Returns a safe-to-render copy
 * plus a list of violations (so the generator/builder can flag a bad fit while
 * the client never renders a broken card). Replaces the old hand-coded
 * capacity clamp — limits now come from the field-spec, which is DB data.
 */
import type { Field, FieldSpec, TemplateInputs } from "./spec";

export interface InputViolation {
  field: string;
  issue: string;
}

function truncate(text: string, max: number): string {
  if (text.length <= max) return text;
  const slice = text.slice(0, max - 1);
  const lastSpace = slice.lastIndexOf(" ");
  return (lastSpace > max * 0.6 ? slice.slice(0, lastSpace) : slice).trimEnd() + "…";
}

function clampField(
  field: Field,
  value: unknown,
  path: string,
  violations: InputViolation[],
): unknown {
  if (value == null) {
    if (field.required) violations.push({ field: path, issue: "required, missing" });
    return value;
  }

  switch (field.type) {
    case "text":
    case "rich": {
      let s = String(value);
      if (field.max && s.length > field.max) {
        violations.push({ field: path, issue: `> ${field.max} chars` });
        s = truncate(s, field.max);
      }
      return s;
    }
    case "number": {
      let n = Number(value);
      if (Number.isNaN(n)) return undefined;
      if (field.min != null && n < field.min) n = field.min;
      if (field.max != null && n > field.max) n = field.max;
      return n;
    }
    case "list": {
      if (!Array.isArray(value)) return [];
      let arr = value;
      if (field.max != null && arr.length > field.max) {
        violations.push({ field: path, issue: `> ${field.max} items` });
        arr = arr.slice(0, field.max);
      }
      if (field.min != null && arr.length < field.min) {
        violations.push({ field: path, issue: `< ${field.min} items` });
      }
      return arr.map((item, i) => {
        if (field.of) {
          // list of objects
          const obj = (item ?? {}) as Record<string, unknown>;
          const out: Record<string, unknown> = { ...obj };
          for (const sub of field.of) {
            out[sub.name] = clampField(sub, obj[sub.name], `${path}.${i}.${sub.name}`, violations);
          }
          return out;
        }
        if (field.item) return clampField(field.item, item, `${path}.${i}`, violations);
        return item;
      });
    }
    case "enum": {
      const s = String(value);
      if (field.values && !field.values.includes(s)) {
        violations.push({ field: path, issue: `not in [${field.values.join(", ")}]` });
        return field.values[0];
      }
      return s;
    }
    // color + asset pass through (asset references / hex strings).
    default:
      return value;
  }
}

export function validateInputs(
  fields: FieldSpec,
  inputs: TemplateInputs,
): { inputs: TemplateInputs; violations: InputViolation[] } {
  const violations: InputViolation[] = [];
  const out: TemplateInputs = { ...inputs };
  for (const field of fields) {
    if (field.name in out || field.required) {
      out[field.name] = clampField(field, out[field.name], field.name, violations);
    }
  }
  return { inputs: out, violations };
}
