import React from 'react'
import { useState , useEffect} from 'react';
import { useAuth } from "../components/AuthContext"; 
import { useNavigate } from "react-router";

const isLineWebview = /Line\//i.test(navigator.userAgent);

function Login() {
  const api = import.meta.env.VITE_API_BASE;
  const { user, setUser, loading } = useAuth();
  const [isLogin, setIsLogin] = useState(true);
  const toggleToRigster = () => setIsLogin(false);
  const toggleToLogin = () => setIsLogin(true);
  const [contactMail, setContactMail] = useState("");
  const [password, setPassword] = useState("");
  const navigate = useNavigate(); // 登入成功後導向我的帳號頁面
  const [formData, setFormData] = useState({
    client_name: "",
    contact_mail: "",
    password: "",
  });

  const [message, setMessage] = useState("");
  const [bindInfo, setBindInfo] = useState(null);

  useEffect(() => {
    const qs = new URLSearchParams(window.location.search);
    const oauthError = qs.get("oauth_error");
    if (oauthError) {
      alert(decodeURIComponent(oauthError));
      qs.delete("oauth_error");
      const next = qs.toString();
      window.history.replaceState({}, "", next ? `${window.location.pathname}?${next}` : window.location.pathname);
    }

    const needBind = qs.get("oauth_bind_required");
    const bindToken = qs.get("oauth_bind_token");
    if (needBind === "1" && bindToken) {
      setBindInfo({
        provider: qs.get("oauth_provider") || "google",
        email: qs.get("oauth_email") || "",
        token: bindToken,
      });
    }
  }, []);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  const handleRegister = async (e) => {
    e.preventDefault();

    try {
      const res = await fetch(`${api}/register`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        credentials: "include", // ✅ 保留 cookie（session）
        body: JSON.stringify(formData)
      });

      const data = await res.json();

      if (res.ok) {
        //  setMessage(`✅ 歡迎 ${data.user.client_name}！註冊並登入成功`);
        // 可選：導向 account 或 dashboard 頁面
        navigate("/account");
        window.location.reload();
      } else {
        setMessage(`❌ ${data.message}`);
      }

    } catch (error) {
      console.error("註冊請求失敗", error);
      setMessage("❌ 註冊失敗，請稍後再試");
    }
  };

  const handleLogin = async (e) => {
    e.preventDefault();
  
    try {
      const res = await fetch(`${api}/login`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        credentials: "include", // 保持 cookie/session
        body: JSON.stringify({ contact_mail: contactMail, password }),
      });
  
      if (!res.ok) {
        const data = await res.json();
        alert(data.message || "登入失敗");
        return;
      }
  
      const data = await res.json();
      setUser(data.user);         // 更新全域登入狀態
      navigate("/account", { replace: true });       // 導向帳號頁面 ,使用 replace: true （無法返回登入頁）
      
    } catch (err) {
      console.error("登入錯誤", err);
      alert("登入時發生錯誤");
    }
  };
  

  const handleGoogleLogin = () => {
    const fo = encodeURIComponent(window.location.origin);
    window.location.href = `${api}/auth/google?redirect=/account&frontend_origin=${fo}`;
  };

  const handleLineLogin = () => {
    const fo = encodeURIComponent(window.location.origin);
    window.location.href = `${api}/auth/line?redirect=/account&frontend_origin=${fo}`;
  }

  const handleConfirmBind = async () => {
    if (!bindInfo?.token) return;
    try {
      const res = await fetch(`${api}/auth/oauth-bind/confirm`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ token: bindInfo.token }),
      });
      const data = await res.json();
      if (!res.ok) {
        alert(data.detail || data.message || "綁定失敗");
        return;
      }
      alert("綁定成功，已登入");
      navigate("/account", { replace: true });
      window.location.reload();
    } catch (err) {
      alert("綁定失敗，請稍後再試");
    }
  };




  return (
    <div className="max-w-md mx-auto min-h-screen">
      <section className='my-10 mx-4'>
        <div className='text-xl mb-6 flex justify-center gap-2'>
          <div onClick={toggleToLogin} 
               className={` hover:bg-red-300 hover:underline cursor-pointer px-6 py-3 rounded-full ${isLogin ? 'bg-red-200' : ''}`}  >
            帳號登入
          </div>
          <div onClick={toggleToRigster}
               className={` hover:bg-red-300 hover:underline cursor-pointer px-6 py-3 rounded-full ${!isLogin ? 'bg-red-200' : ''}`} >
            新客註冊
          </div>
        </div>

        <div className='bg-white px-4 py-10 rounded-4xl'>
           
           {/* 登入表單  */}

            {isLogin &&
              <form onSubmit={handleLogin}  className="max-w-4xl mx-auto flex flex-col items-center gap-5 text-base px-5">
                
                          <input  type="email"
                                  name="email"
                                  value={contactMail}
                                  onChange={(e) => setContactMail(e.target.value)}
                                  placeholder="電子郵件地址"
                                  required 
                                  className="px-5 py-2 rounded-full border border-solid border-slate-900 w-full" 
                          />
                  
                          <input  type="password"
                                  name="password"
                                  value={password}
                                  onChange={(e) => setPassword(e.target.value)}
                                  placeholder="密碼"
                                  required 
                                  className=" px-5 py-2 rounded-full border border-solid border-slate-900 w-full"
                          />
                        
                        <button 
                        type="submit"
                        className="bg-rose-400 hover:bg-rose-300 active:bg-rose-200 text-white p-2 w-full  rounded-full border border-solid cursor-pointer">
                          登入</button>
                        
                      {!isLineWebview && (
                      <div 
                      onClick={handleGoogleLogin}
                      className="bg-rose-400 hover:bg-rose-300 active:bg-rose-200 text-white p-2 w-full  rounded-full border border-solid  flex justify-center gap-2 cursor-pointer" >
                        <img src="googleIcon2.png" alt="googleIcon" width="25" />
                        使用Google登入
                      </div>
                      )}

                      <div
                      onClick={handleLineLogin}
                      className="bg-rose-400 hover:bg-rose-300 active:bg-rose-200 text-white p-2 w-full  rounded-full border border-solid   flex justify-center gap-2 cursor-pointer">
                        <img src="lineIcon3.png" alt="googleIcon" width="25" />
                        使用Line登入
                      </div>

                      {bindInfo && (
                        <div className="w-full border border-rose-300 rounded-xl p-3 text-sm text-slate-700 bg-rose-50">
                          <p className="mb-2 font-semibold">偵測到同 Email 既有帳號，請確認是否綁定 Google</p>
                          <p className="mb-3 break-all">Email：{bindInfo.email || "(未提供)"}</p>
                          <button
                            type="button"
                            onClick={handleConfirmBind}
                            className="bg-rose-500 hover:bg-rose-600 text-white px-3 py-2 rounded cursor-pointer"
                          >
                            確認綁定並登入
                          </button>
                        </div>
                      )}
                </form>
            }
            
            {/* 註冊表單  */}
        

            {!isLogin && 
              <form onSubmit={handleRegister}  className="max-w-4xl mx-auto flex flex-col items-center gap-5 text-base px-5">
                
              <input  type="test"
                      name="client_name"
                      value={formData.client_name}
                      onChange={handleChange}
                      placeholder="姓名"
                      required 
                      className="px-5 py-2 rounded-full border border-solid border-slate-900 w-full" 
              />
              <input  type="email"
                      name="contact_mail"
                      value={formData.contact_mail}
                      onChange={handleChange}
                      placeholder="電子郵件地址"
                      required 
                      className="px-5 py-2 rounded-full border border-solid border-slate-900 w-full" 
              />
      
              <input  type="password"
                      name="password"
                      value={formData.password}
                      onChange={handleChange}
                      placeholder="密碼"
                      required 
                      minLength="6"
                      className=" px-5 py-2 rounded-full border border-solid border-slate-900 w-full"
              />
            
            <button 
            type="submit"
            className="bg-rose-400 hover:bg-rose-300 active:bg-rose-200 text-white p-2 w-full  rounded-full border border-solid cursor-pointer">
              註冊</button>
            
          {!isLineWebview && (
          <div 
          onClick={handleGoogleLogin}
          className="bg-rose-400 hover:bg-rose-300 active:bg-rose-200 text-white p-2 w-full  rounded-full border border-solid  flex justify-center gap-2 cursor-pointer" >
            <img src="googleIcon2.png" alt="googleIcon" width="25" />
            使用Google註冊
          </div>
          )}

          <div
          onClick={handleLineLogin}
          className="bg-rose-400 hover:bg-rose-300 active:bg-rose-200 text-white p-2 w-full  rounded-full border border-solid   flex justify-center gap-2 cursor-pointer">
            <img src="lineIcon3.png" alt="googleIcon" width="25" />
            使用Line註冊
          </div>
          {message && <p>{message}</p>}
    </form>
            }
            
        </div>

      </section>
    </div>
  )
}


export default Login;