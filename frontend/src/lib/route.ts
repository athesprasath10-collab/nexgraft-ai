import { useEffect, useState } from "react";

export type Route =
  | { name: "home" }
  | { name: "workspace"; agent: string }
  | { name: "knowledge" }
  | { name: "system" };

export function parseHash(hash: string): Route {
  const path = hash.replace(/^#\/?/, "");
  const [head, arg] = path.split("/");
  if (head === "w" && arg) return { name: "workspace", agent: arg };
  if (head === "knowledge") return { name: "knowledge" };
  if (head === "system") return { name: "system" };
  return { name: "home" };
}

export const hrefFor = (r: Route) =>
  r.name === "workspace" ? `#/w/${r.agent}` : r.name === "home" ? "#/" : `#/${r.name}`;

export function navigate(r: Route) {
  window.location.hash = hrefFor(r);
}

export function useRoute(): Route {
  const [route, setRoute] = useState<Route>(() => parseHash(window.location.hash));
  useEffect(() => {
    const onChange = () => setRoute(parseHash(window.location.hash));
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);
  return route;
}
