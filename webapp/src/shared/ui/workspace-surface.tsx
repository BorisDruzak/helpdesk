type WorkspaceSurfaceProps = {
  eyebrow: string;
  title: string;
  description: string;
  featureList: string[];
};


export function WorkspaceSurface({
  eyebrow,
  title,
  description,
  featureList,
}: WorkspaceSurfaceProps) {
  return (
    <section className="workspace-surface">
      <header className="workspace-surface__header">
        <span className="workspace-surface__eyebrow">{eyebrow}</span>
        <h1>{title}</h1>
        <p>{description}</p>
      </header>
      <ul className="workspace-surface__list">
        {featureList.map((feature) => (
          <li key={feature}>{feature}</li>
        ))}
      </ul>
    </section>
  );
}
