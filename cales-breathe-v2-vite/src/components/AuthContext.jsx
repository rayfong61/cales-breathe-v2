import { createContext, useEffect, useState, useContext } from "react";

const AuthContext = createContext();

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
  const api = import.meta.env.VITE_API_BASE;

  const fetchUser = async () => {
    try {
      const res = await fetch(`${api}/me`, {
        credentials: "include",
      });

      if (!res.ok) {
        setUser(null);
        setLoading(false);
        return;
      }

      const data = await res.json();
      setUser(data.user || null);
    } catch (error) {
      console.error("無法取得使用者資料", error);
      setUser(null);
    } finally {
      setLoading(false);
    }
  };

  fetchUser();
}, []);

  return (
    <AuthContext.Provider value={{ user, setUser, loading }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);

