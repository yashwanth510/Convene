/** Recognize complete Mermaid declaration lines, even in a mislabeled code fence. */
export function isMermaidSource(source: string): boolean {
  const firstLine = source.trimStart().split(/\r?\n/, 1)[0].trim();
  return /^(?:(?:flowchart|graph)\s+(?:TB|TD|BT|RL|LR)|sequenceDiagram|classDiagram|stateDiagram(?:-v2)?|erDiagram|journey|gantt|pie|mindmap|timeline)\s*;?$/.test(
    firstLine,
  );
}

/** Quote plain rectangular flowchart labels without changing nodes or connections. */
export function quoteFlowchartLabels(source: string): string {
  if (!/^\s*(?:flowchart|graph)\s+/.test(source)) return source;
  return source.replace(
    /(\b[A-Za-z_][\w-]*\s*)\[([^\]\n]*)\]/g,
    (match, id: string, label: string) => {
      // Leave quoted labels, nested shapes and database/stadium syntax intact.
      if (!label.trim() || /^[\s]*["'[({]/.test(label)) return match;
      return `${id}["${label.replace(/"/g, "#quot;")}"]`;
    },
  );
}
