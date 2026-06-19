/**
 * Conservative SVG sanitizer for the `svg` node. The markup may originate from
 * the DB / an LLM, so it's injected via dangerouslySetInnerHTML only after
 * stripping script vectors. This is a denylist stopgap — swap in DOMPurify
 * (with the SVG profile) before accepting untrusted third-party markup.
 */
export function sanitizeSvg(markup: string): string {
  return markup
    .replace(/<script[\s\S]*?<\/script>/gi, "")
    .replace(/<foreignObject[\s\S]*?<\/foreignObject>/gi, "")
    // strip inline event handlers (onload=, onclick=, …)
    .replace(/\son\w+\s*=\s*("[^"]*"|'[^']*'|[^\s>]+)/gi, "")
    // neutralise javascript: in href / xlink:href
    .replace(/(href|xlink:href)\s*=\s*("\s*javascript:[^"]*"|'\s*javascript:[^']*')/gi, 'href=""');
}
