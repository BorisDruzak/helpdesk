

export function SettingsField({
  children,
  label,
}: {
  children: React.ReactNode;
  label: string;
}) {
  return (
    <label className="flex min-w-0 flex-col gap-2 text-sm font-medium text-slate-800">
      <span>{label}</span>
      {children}
    </label>
  );
}

export function PermissionNotice({ text }: { text: string | null }) {
  if (!text) {
    return null;
  }
  return (
    <div className="rounded-[1rem] border border-amber-200 bg-amber-50 px-4 py-3 text-sm font-medium text-amber-900">
      {text}
    </div>
  );
}
