import { Layout } from "./components/Layout";
import { Notice, PageHeading } from "./components/ui";
import { Link, matchRoute, useRouter } from "./lib/router";
import { CollectorPage } from "./pages/CollectorPage";
import { ImpactPage } from "./pages/ImpactPage";
import { SchedulePage } from "./pages/SchedulePage";
import { TrackPage } from "./pages/TrackPage";

function NotFound() {
  return (
    <>
      <PageHeading title="Page not found" />
      <Notice
        tone="warn"
        action={
          <Link to="/" className="btn btn--secondary btn--small">
            Go home
          </Link>
        }
      >
        That page doesn't exist.
      </Notice>
    </>
  );
}

function Routes() {
  const { path } = useRouter();
  const track = matchRoute("/track/:id", path);

  if (path === "/") return <SchedulePage />;
  if (path === "/track") return <TrackPage />;
  if (track?.["id"]) return <TrackPage id={track["id"]} />;
  if (path === "/impact") return <ImpactPage />;
  if (path === "/collector") return <CollectorPage />;
  return <NotFound />;
}

export function App() {
  return (
    <Layout>
      <Routes />
    </Layout>
  );
}
