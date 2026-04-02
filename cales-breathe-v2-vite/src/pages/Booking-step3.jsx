import axios from "axios";
import { useState, useEffect } from "react";
import { useAuth } from "../components/AuthContext";
import { useNavigate, useLocation } from "react-router-dom";

const isLineWebview = /Line\//i.test(navigator.userAgent);

function BookingClientContent() {
  const api = import.meta.env.VITE_API_BASE;
  const navigate = useNavigate();
  const { user, setUser, loading } = useAuth();
  const [bookingData, setBookingData] = useState(null);
  const [formData, setFormData] = useState(null);
  const [message, setMessage] = useState("");
  const [inputError, setInputError] = useState("");
  const [mobileError, setMobileError] = useState("");
  const [isSubmitted, setIsSubmitted] = useState(false);
  const [name, setName] = useState(user?.client_name || "");
  const [mobile, setMobile] = useState(user?.contact_mobile || "");
  const [note, setNote] = useState("");
  const [contactMail, setContactMail] = useState("");
  const [password, setPassword] = useState("");

  // 取得 localStorage 的預約資料
  useEffect(() => {
    const storedData = localStorage.getItem("bookingData");
    if (storedData) {
      const parsed = JSON.parse(storedData);
      setBookingData(parsed);
    }
  }, []);

  // 等 user 和 bookingData 都有值後，再建立 formData
  const addonMap = {
    "add-toes": "腳趾加購",
    "add-armpit": "腋下加購",
    "add-fingers": "手指加購",
    "add-lip": "上唇加購",
    // 可以依實際情況補上
  };

  // useEffect(() => {
  //   if (user) {
  //     setName(user.client_name || "");
  //     setMobile(user.contact_mobile || "");
  //   }
  // }, [user]);

  useEffect(() => {
    if (user && bookingData) {
      const services = bookingData.selectedServices.map(s => s.name);
      const addons = bookingData.selectedAddons.map(id => addonMap[id] || id);
      setName(user.client_name || "");
      setMobile(user.contact_mobile || "");
  
      setFormData({
        client_id: user.id,
        booking_detail: {
          services,
          addons
        },
        total_price: bookingData.total,
        total_duration: bookingData.totalDuration,
        booking_date: bookingData.date,
        booking_time: bookingData.time
      });
    }
  }, [user, bookingData]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!formData) return;
    setInputError("");
    setMobileError("");
    setMessage("");

    if (!name.trim() || !mobile.trim()) {
      setInputError("姓名與手機為必填欄位");
      return;
    }

    try {
      // 1. 更新使用者資料
      await axios.put(`${api}/account/update2`, {
        client_name: name.trim(),
        contact_mobile: mobile.trim(),
      }, { withCredentials: true });

      // 2. 提交預約資料
      const res = await axios.post(`${api}/orders`, {
        ...formData,
        booking_detail: JSON.stringify(formData.booking_detail),
        booking_note: note.trim() || null
      }, { withCredentials: true });

      setIsSubmitted(true);
      localStorage.removeItem("bookingData");
      
    } catch (err) {
      const status = err?.response?.status;
      const detail = err?.response?.data?.detail;
      if (status === 409 && String(detail || "").includes("手機")) {
        setMobileError("此手機已被其他會員使用，請改填其他號碼。");
        setMessage("預約失敗");
        return;
      }
      if (status === 400 && String(detail || "").includes("手機")) {
        setMobileError(String(detail));
        setMessage("預約失敗");
        return;
      }
      if (status === 400 && String(detail || "").includes("重複")) {
        setMessage(`預約失敗：${detail}`);
        return;
      }
      setMessage(detail || err.response?.data?.message || "預約失敗");
      console.error(err);
    }
  };

  const handleGoogleLogin = () => {
    const fo = encodeURIComponent(window.location.origin);
    const loginWindow = window.open(
      `${api}/auth/google?redirect=/booking-step3&frontend_origin=${fo}`,
      "_blank",
      "width=500,height=600"
    );

    const receiveMessage = (event) => {
      // OAuth callback 執行在後端 origin（onrender.com），不是 Vercel proxy origin
      // 只檢查訊息內容即可；login-success 為足夠具體的標記
      if (event.data === "login-success") {
        window.removeEventListener("message", receiveMessage);
        loginWindow?.close();
        window.location.reload();
      }
    };

    window.addEventListener("message", receiveMessage);
  };

  const handleLineLogin = () => {
    const fo = encodeURIComponent(window.location.origin);
    const loginWindow = window.open(
      `${api}/auth/line?redirect=/booking-step3&frontend_origin=${fo}`,
      "_blank",
      "width=500,height=600"
    );

    const receiveMessage = (event) => {
      if (event.data === "login-success") {
        window.removeEventListener("message", receiveMessage);
        loginWindow?.close();
        window.location.reload();
      }
    };

    window.addEventListener("message", receiveMessage);
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
      navigate("/booking-step3"); 
    } catch (err) {
      console.error("登入錯誤", err);
      alert("登入時發生錯誤");
    }
  };
  


  if (!user) {
    return (
      <div className="max-w-xl mx-auto p-6 my-6 bg-white rounded-xl shadow-md">
        <h2 className="text-xl font-bold mb-4">請先登入以繼續預約</h2>
        <form onSubmit={handleLogin}  className="max-w-4xl mx-auto flex flex-col items-center gap-5 text-base px-5 py-5">
                
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
                </form>
      </div>
    );
  }

  const lineAddFriendUrl = import.meta.env.VITE_LINE_ADD_FRIEND_URL;

  if (isSubmitted) {
    return (
      <div className="max-w-xl mx-auto p-20 my-10 bg-white rounded-xl shadow-md text-center">
        
        <h2 className="text-xl font-bold mb-2">預約已送出！</h2>
        <p className="text-gray-500 text-lg mb-6">
          預約審核中，業主確認後將透過 LINE 或電話通知您。
        </p>

        {lineAddFriendUrl && !user?.line_user_id && (
          <div className="bg-green-50 border border-green-200 rounded-xl p-4 mb-6">
            <p className="text-md text-green-800 font-medium mb-3">
              歡迎加入 LINE 好友，即時接收最新預約通知!
            </p>
            <a
              href={lineAddFriendUrl}
              target="_blank"
              rel="noopener noreferrer"
            >
              <img
                src="https://scdn.line-apps.com/n/line_add_friends/btn/zh-Hant.png"
                alt="加入LINE好友"
                className="mx-auto h-10"
              />
            </a>
          </div>
        )}

        <button
          onClick={() => { navigate("/account"); window.location.reload(); }}
          className="bg-rose-500 hover:bg-rose-600 text-white px-6 py-2 rounded-full cursor-pointer"
        >
          查看訂單紀錄
        </button>
      </div>
    );
  }

  if (!formData) return <p>載入中...</p>;

  return (
    <div className="max-w-xl mx-auto p-6 my-6 bg-white rounded-xl shadow-md">
      <h2 className="text-xl font-bold mb-4">請確認以下內容是否正確:</h2>
      
      <form onSubmit={handleSubmit} className="px-2 ">

        <h3 className="block my-2 font-semibold">聯絡資訊：</h3>

        <label className="block my-1">*姓名 : </label>
        <input
        type="text"
        value={name}
        onChange={(e) => setName(e.target.value)}
        required
        className="border p-2 rounded w-full"
        />
        <label className="block my-1">*手機 : </label>
        <input
        type="text"
        value={mobile}
        onChange={(e) => {
          setMobile(e.target.value);
          setMobileError("");
          setInputError("");
        }}
        required
        className={`border p-2 rounded w-full ${mobileError ? "border-red-500" : ""}`}
        />
        {mobileError && <p className="text-red-500 text-sm mt-1">{mobileError}</p>}
        {inputError && <p className="text-red-500 text-sm mt-1">{inputError}</p>}
        <label className="block my-1">備註事項 : </label>
        <textarea
        type="text"
        value={note}
        onChange={(e) => setNote(e.target.value)}
        className="border p-2 rounded w-full "
        placeholder="例如 : 懷孕第幾周? 第一次除毛等等"
        rows={2}
        />

    

        <h3 className="block my-2 font-semibold">預約內容：</h3>
        <p>預約項目：{formData.booking_detail.services.join(", ")}</p>
        <p>加購項目：{formData.booking_detail.addons.join(", ") || "無"}</p>
        <p>價格：{formData.total_price}</p>
        <p>時長：{formData.total_duration} 分鐘</p>
        <p>日期：{formData.booking_date}</p>
        <p>時間：{formData.booking_time}</p>

        <button type="submit"
                className="bg-rose-500 hover:bg-rose-600 text-white px-4 py-2 rounded w-30 cursor-pointer my-2 block mx-auto">
          送出預約
        </button>
        {message && <p className="text-rose-400 text-center text-xl font-bold py-3">{message}</p>}
      </form>
    </div>
  );
}

export default BookingClientContent;

            
 

// Note:
// 🔍 為什麼要用 trim()？  
// 移除字串開頭與結尾的空白字元(只影響「開頭與結尾」的空白，不會移除中間的空白)
// "王 小明".trim()  // => "王 小明"