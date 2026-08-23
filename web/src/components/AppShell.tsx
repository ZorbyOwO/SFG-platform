import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../app/AuthContext";
import { Icon } from "./Icon";

const links = [
  { to: "/dashboard", label: "Home", icon: "home" as const },
  { to: "/transactions", label: "History", icon: "history" as const },
  { to: "/family", label: "Family", icon: "family" as const },
  { to: "/profile", label: "Profile", icon: "profile" as const },
];

export function AppShell() {
  const auth = useAuth();
  const navigate = useNavigate();
  const logout = async () => { await auth.signOut(); navigate("/"); };
  return <div className="app-shell">
    <aside className="desktop-sidebar">
      <a className="brand" href="/dashboard" aria-label="Sarawak Facial Gateway home"><span className="brand-mark">SFG</span><span>Sarawak<br />Facial Gateway</span></a>
      <nav aria-label="Main navigation">{links.map((link) => <NavLink key={link.to} to={link.to}><Icon name={link.icon} /><span>{link.label}</span></NavLink>)}</nav>
      <button className="text-button sidebar-logout" onClick={logout}>Log out</button>
    </aside>
    <main className="app-content"><Outlet /></main>
    <nav className="mobile-nav" aria-label="Main navigation">{links.map((link) => <NavLink key={link.to} to={link.to}><Icon name={link.icon} /><span>{link.label}</span></NavLink>)}</nav>
  </div>;
}
