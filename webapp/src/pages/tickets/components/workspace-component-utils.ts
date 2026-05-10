export function toneClasses(tone: string) {
  switch (tone) {
    case "danger":
      return "border-red-400/50 bg-red-500/10 text-red-200";
    case "warning":
      return "border-amber-400/50 bg-amber-500/10 text-amber-100";
    case "success":
      return "border-emerald-400/40 bg-emerald-500/10 text-emerald-100";
    case "brand":
    case "info":
      return "border-blue-400/40 bg-blue-500/10 text-blue-100";
    default:
      return "border-white/10 bg-white/[0.04] text-slate-300";
  }
}
