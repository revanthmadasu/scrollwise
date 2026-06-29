/**
 * The generic, data-driven template renderer. Walks a TemplateDoc's `layout`
 * node tree, binding values from `inputs` per the doc's field-spec. One engine
 * replaces the per-template React components — adding a template within the node
 * vocabulary is a data change, not a code change.
 */
import { createContext, useContext } from "react";
import type { CSSProperties, JSX } from "react";
import Lottie from "lottie-react";
import { useTheme } from "../../theme/ThemeContext";
import { Deco } from "../Deco";
import type { LayoutNode, TemplateDoc, TemplateInputs } from "./spec";
import { ENGINE_VERSION } from "./spec";
import { getByPath, isTruthy, resolveValue } from "./resolve";
import type { Scope } from "./resolve";
import { compileStyle } from "./style";
import { validateInputs } from "./validate";
import { sanitizeSvg } from "./sanitize";

function cx(...parts: Array<string | undefined>): string {
  return parts.filter(Boolean).join(" ");
}

/** Per-render context shared by every node (resolved accent + cycle palette). */
const EngineCtx = createContext<{ accent: string; accents?: string[] }>({ accent: "var(--accent)" });

interface NodeProps {
  node: LayoutNode;
  scope: Scope;
}

function Node({ node, scope }: NodeProps): JSX.Element | null {
  const ctx = useContext(EngineCtx);
  if (node.when != null && !isTruthy(node.when, scope)) return null;
  if (node.unless != null && isTruthy(node.unless, scope)) return null;

  const { className, style } = compileStyle(node.style, {
    accents: ctx.accents,
    index: scope.$index ?? 0,
  });

  switch (node.type) {
    case "box": {
      const Tag = (node.as ?? "div") as "div";
      return (
        <Tag className={cx("te-box", className)} style={style}>
          {node.children?.map((child, i) => <Node key={i} node={child} scope={scope} />)}
        </Tag>
      );
    }
    case "text": {
      const v = resolveValue(node.value, scope);
      if (v == null || v === "") return null;
      const Tag = (node.as ?? "span") as "span";
      return <Tag className={cx("te-text", className)} style={style}>{String(v)}</Tag>;
    }
    case "image": {
      const src = resolveValue(node.src, scope);
      if (!src) return null;
      const alt = resolveValue(node.alt, scope);
      return <img className={cx("te-image", className)} style={style} src={String(src)} alt={alt ? String(alt) : ""} />;
    }
    case "svg": {
      const markup = resolveValue(node.markup, scope);
      if (!markup) return null;
      return (
        <div
          className={cx("te-svg", className)}
          style={style}
          dangerouslySetInnerHTML={{ __html: sanitizeSvg(String(markup)) }}
        />
      );
    }
    case "lottie": {
      const src = resolveValue(node.src, scope);
      if (!src) return null;
      return (
        <div className={cx("te-lottie", className)} style={style}>
          <Lottie animationData={typeof src === "string" ? undefined : src} loop={node.loop ?? true} />
        </div>
      );
    }
    case "deco":
      return <Deco variant={node.variant} accent={ctx.accent} seedKey={resolveValue(node.seed, scope) ?? "scrollwise"} />;
    case "repeat": {
      const arr = getByPath(scope, node.over);
      if (!Array.isArray(arr) || arr.length === 0) return null;
      const wrap = compileStyle(node.wrap?.style, { accents: ctx.accents });
      const WrapTag = (node.wrap?.as ?? "div") as "div";
      return (
        <WrapTag className={cx("te-repeat", wrap.className)} style={wrap.style}>
          {arr.map((item, i) => (
            <Node key={i} node={node.child} scope={{ ...scope, [node.as]: item, $index: i }} />
          ))}
        </WrapTag>
      );
    }
    default:
      return null;
  }
}

interface Props {
  doc: TemplateDoc;
  inputs: TemplateInputs;
  className?: string;
}

/** Render a template document against a set of inputs. Fails safe on bad data. */
export function TemplateEngine({ doc, inputs, className }: Props): JSX.Element {
  const { resolved } = useTheme();
  const pal = doc.palette[resolved];
  const accent = (typeof inputs.accentColor === "string" && inputs.accentColor) || pal.accent;

  // Defensive: clamp inputs, and refuse a doc the renderer is too old to support.
  const { inputs: safe } = validateInputs(doc.fields, inputs);
  const unsupported = doc.engine > ENGINE_VERSION;

  const rootStyle = {
    "--accent": accent,
    "--bg": pal.bg,
    "--surface": pal.surface,
    "--text": pal.text,
  } as CSSProperties;

  return (
    <div className={cx("tmpl-engine", className)} style={rootStyle}>
      {unsupported ? (
        <div className="tmpl-fallback">
          <h2>{String(safe.title ?? doc.name)}</h2>
          {safe.body != null && <p>{String(safe.body)}</p>}
        </div>
      ) : (
        <EngineCtx.Provider value={{ accent, accents: doc.accents }}>
          <Node node={doc.layout} scope={{ ...safe, $index: 0 }} />
        </EngineCtx.Provider>
      )}
    </div>
  );
}
