import { useEffect, useState } from "react";
import { LoaderCircle } from "lucide-react";
import Auth, { Brand } from "./components/Auth";
import Workspace from "./components/Workspace";
import { getToken, setToken, request } from "./lib/api";
import type { User } from "./lib/types";
import "./App.css";

export default function App() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(!!getToken());
  useEffect(() => {
    if (getToken())
      request<User>("/auth/me")
        .then(setUser)
        .catch(() => setToken(""))
        .finally(() => setLoading(false));
    const expired = () => {
      setToken("");
      setUser(null);
    };
    window.addEventListener("convene-session-expired", expired);
    return () => window.removeEventListener("convene-session-expired", expired);
  }, []);
  if (loading)
    return (
      <div className="loading-page">
        <Brand />
        <LoaderCircle className="spin" />
      </div>
    );
  return user ? (
    <Workspace
      user={user}
      logout={() => {
        setToken("");
        setUser(null);
      }}
    />
  ) : (
    <Auth onLogin={setUser} />
  );
}
