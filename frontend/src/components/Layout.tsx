import { NavLink, Outlet } from "react-router-dom";

const links = [
  { to: "/", label: "Dashboard" },
  { to: "/summaries", label: "Summaries" },
  { to: "/digests", label: "Digests" },
  { to: "/items", label: "Items" },
  { to: "/exposures", label: "Exposures" },
  { to: "/runs", label: "Runs" },
];

export default function Layout() {
  return (
    <div className="min-h-screen flex flex-col">
      <nav className="bg-gray-900 text-gray-100">
        <div className="max-w-6xl mx-auto px-4 flex items-center h-14 gap-6">
          <span className="font-semibold tracking-wide text-lg">
            Worldlines
          </span>
          {links.map((l) => (
            <NavLink
              key={l.to}
              to={l.to}
              end={l.to === "/"}
              className={({ isActive }) =>
                `text-sm hover:text-white ${isActive ? "text-white underline underline-offset-4" : "text-gray-400"}`
              }
            >
              {l.label}
            </NavLink>
          ))}
        </div>
      </nav>
      <main className="flex-1 max-w-6xl mx-auto w-full px-4 py-6">
        <Outlet />
      </main>
    </div>
  );
}
