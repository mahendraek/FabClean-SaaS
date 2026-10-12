import { createContext, useContext, useEffect, useState } from "react";
import { usePathname } from "expo-router";
// Keep a link's token in memory while replacing the route; never persist it.
const TokenContext = createContext<{ token: string; setToken: (token: string) => void }>({ token: "", setToken: () => {} });
export function InvitationTokenProvider({ children }: { children: React.ReactNode }) {
  const [token, setToken] = useState("");
  const pathname = usePathname();
  useEffect(() => { if (pathname !== "/accept-invite") setToken(""); }, [pathname]);
  return <TokenContext.Provider value={{ token, setToken }}>{children}</TokenContext.Provider>;
}
export function useInvitationToken() { return useContext(TokenContext); }
