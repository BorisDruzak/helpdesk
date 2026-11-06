export function catalogDescription(title: string, description?: string | null): string {
  const normalize = (value: string) => value.toLocaleLowerCase("ru").replace(/[\s\p{P}]+/gu, " ").trim();
  return description && normalize(title) !== normalize(description) ? description : "";
}
