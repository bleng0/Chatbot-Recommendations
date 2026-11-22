export default function Home() {
  return (
    <main className="page">
      <section className="card">
        <p className="eyebrow">Next.js + TypeScript</p>
        <h1>Pome is ready</h1>
        <p className="lede">
          A minimal starting point for a web app, with development and production
          container setups included.
        </p>
        <div className="actions">
          <code>npm run dev</code>
          <span>or</span>
          <code>docker compose -f compose.dev.yaml up --build</code>
        </div>
      </section>
    </main>
  );
}
