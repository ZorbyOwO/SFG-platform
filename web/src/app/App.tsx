import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./AuthContext";
import { AppShell } from "../components/AppShell";
import { Dashboard } from "../routes/Dashboard";
import { Family } from "../routes/Family";
import { Login } from "../routes/Login";
import { Profile } from "../routes/Profile";
import { Register } from "../routes/Register";
import { TransactionDetails, Transactions } from "../routes/Transactions";
import { Welcome } from "../routes/Welcome";

function ProtectedShell() {
  const { authenticated } = useAuth();
  return authenticated ? <AppShell /> : <Navigate to="/login" replace state={{ reason: "Sign in to continue." }} />;
}

export function App() {
  return <Routes>
    <Route path="/" element={<Welcome />} />
    <Route path="/login" element={<Login />} />
    <Route path="/register/*" element={<Register />} />
    <Route element={<ProtectedShell />}>
      <Route path="/dashboard" element={<Dashboard />} />
      <Route path="/transactions" element={<Transactions />} />
      <Route path="/transactions/:id" element={<TransactionDetails />} />
      <Route path="/family/*" element={<Family />} />
      <Route path="/profile" element={<Profile />} />
    </Route>
    <Route path="*" element={<Navigate to="/" replace />} />
  </Routes>;
}
