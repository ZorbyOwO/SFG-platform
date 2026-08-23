import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../app/AuthContext";
import { services } from "../services";

type ProfileData = Awaited<ReturnType<typeof services.profile.getProfile>>;

export function Profile() {
  const [profile, setProfile] = useState<ProfileData | null>(null); const [error, setError] = useState(""); const auth = useAuth(); const navigate = useNavigate();
  useEffect(() => { services.profile.getProfile().then(setProfile).catch((reason) => setError(reason instanceof Error ? reason.message : "Unable to load profile.")); }, []);
  const logout = async () => { await auth.signOut(); navigate("/"); };
  return <div className="page-wrap narrow-page"><header className="page-header compact-header"><div><p className="eyebrow">Account</p><h1>Profile and security</h1><p>Review your account status and security actions.</p></div></header>{error && <div className="form-error">{error}</div>}<section className="card profile-card">{!profile ? <div className="skeleton-card" /> : <><div className="profile-identity"><div className="member-avatar large">{profile.citizen_display_name.split(" ").map((part) => part[0]).slice(0, 2).join("")}</div><div><h2>{profile.citizen_display_name}</h2><p>{profile.ic_number_masked}</p></div></div><div className="review-list"><div><span>Account status</span><strong>{profile.account_status.toUpperCase()}</strong></div><div><span>Face enrolment</span><strong>{profile.enrolment_status.replaceAll("_", " ")}</strong></div></div></>}</section><section className="card security-actions"><h2>Security</h2><button className="settings-row">Change password<span>Available through the API</span></button><button className="settings-row">Change PIN<span>PIN is never stored in this browser</span></button><button className="settings-row">Re-enrol face<span>Revokes existing development templates</span></button><button className="button secondary full" onClick={logout}>Log out</button></section></div>;
}
