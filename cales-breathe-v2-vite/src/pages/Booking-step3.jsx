import axios from "axios";
import { useState, useEffect } from "react";
import { useAuth } from "../components/AuthContext";
import { useNavigate } from "react-router-dom";

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
  // 業主代客預約：客人選擇相關 state
  const [customerQuery, setCustomerQuery] = useState("");
  const [customerResults, setCustomerResults] = useState([]);
  const [selectedCustomer, setSelectedCustomer] = useState(null);
  const [guestName, setGuestName] = useState("");
  const [customerError, setCustomerError] = useState("");

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

  // 送出成功後自動回到頁面上方，避免使用者需要手動往上捲才看到成功提示。
  useEffect(() => {
    if (!isSubmitted) return;
    window.scrollTo({ top: 0, behavior: "smooth" });
  }, [isSubmitted]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!formData) return;
    setInputError("");
    setMobileError("");
    setMessage("");
    setCustomerError("");

    if (!name.trim() || !mobile.trim()) {
      setInputError("姓名與手機為必填欄位");
      return;
    }

    // 若為 owner，需檢查是否有選擇會員或輸入訪客姓名（擇一）
    let payload = { ...formData };
    const trimmedName = name.trim();
    const trimmedMobile = mobile.trim();
    if (user?.role === "owner") {
      const trimmedGuest = guestName.trim();
      if (!selectedCustomer && !trimmedGuest) {
        setCustomerError("請選擇已註冊客人，或填寫訪客姓名");
        return;
      }
      if (selectedCustomer) {
        payload.client_id = selectedCustomer.id;
        payload.guest_name = null;
        payload.customer_name = trimmedName;
        payload.customer_mobile = trimmedMobile;
      } else {
        payload.client_id = null;
        payload.guest_name = trimmedGuest;
        payload.customer_name = trimmedName;
        payload.customer_mobile = trimmedMobile;
      }
    }

    try {
      // 1. 非 owner 情境才更新當前登入者資料。
      // owner 代客預約（會員/訪客）避免誤改到業主自己的姓名/手機。
      if (user?.role !== "owner") {
        await axios.put(`${api}/account/update2`, {
          client_name: trimmedName,
          contact_mobile: trimmedMobile,
        }, { withCredentials: true });
      }

      // 2. 提交預約資料
      const res = await axios.post(`${api}/orders`, {
        ...payload,
        booking_detail: JSON.stringify(payload.booking_detail),
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

  // -------------------------------
  // 業主代客預約：客人搜尋與選擇
  // -------------------------------
  const handleSearchCustomers = async () => {
    setCustomerError("");
    const q = customerQuery.trim();
    if (!q) {
      setCustomerResults([]);
      return;
    }
    try {
      const res = await axios.get(`${api}/customers/search`, {
        params: { q },
        withCredentials: true,
      });
      setCustomerResults(res.data || []);
    } catch (err) {
      console.error("搜尋客人失敗", err);
      setCustomerError(err?.response?.data?.detail || "搜尋客人失敗");
    }
  };

  // 整頁導向 OAuth（與 Login.jsx 相同）：避免 Android / LINE 上 window.open、
  // opener 斷線導致 postMessage 失敗、登入 cookie 與父頁不同步。
  const handleGoogleLogin = () => {
    const fo = encodeURIComponent(window.location.origin);
    window.location.href = `${api}/auth/google?redirect=/booking-step3&frontend_origin=${fo}`;
  };

  const handleLineLogin = () => {
    const fo = encodeURIComponent(window.location.origin);
    window.location.href = `${api}/auth/line?redirect=/booking-step3&frontend_origin=${fo}`;
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
        
        <h2 className="text-xl font-bold mb-2">
          {user?.role === "owner" ? "代客預約已送出！" : "預約已送出！"}
        </h2>
        {user?.role !== "owner" && (
          <p className="text-gray-500 text-lg mb-6">
            預約審核中，業主確認後將透過 LINE 或電話通知您。
          </p>
        )}

        {user?.role !== "owner" && lineAddFriendUrl && !user?.line_user_id && (
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
      <h2 className="text-xl font-bold mb-4">
        {user?.role === "owner" ? "請確認以下代客預約內容是否正確:" : "請確認以下內容是否正確:"}
      </h2>
      
      <form onSubmit={handleSubmit} className="px-2 ">

        {/* 業主代客預約：客人選擇區塊 */}
        {user?.role === "owner" && (
          <div className="mb-4 border border-dashed border-rose-300 rounded-lg p-3 bg-rose-50">
            <h3 className="font-semibold mb-2">代客預約 - 選擇客人</h3>

            <label className="block text-sm mb-1">搜尋已註冊客人（姓名關鍵字）</label>
            <div className="flex gap-2 mb-2">
              <input
                type="text"
                value={customerQuery}
                onChange={(e) => setCustomerQuery(e.target.value)}
                className="border p-2 rounded flex-1"
                placeholder="例如：小美"
              />
              <button
                type="button"
                onClick={handleSearchCustomers}
                className="px-3 py-2 bg-rose-400 hover:bg-rose-300 text-white rounded cursor-pointer"
              >
                搜尋
              </button>
            </div>

            {customerResults.length > 0 && (
              <ul className="max-h-40 overflow-y-auto mb-2 border rounded">
                {customerResults.map((c) => (
                  <li
                    key={c.id}
                    className={`flex items-center gap-2 px-2 py-1 cursor-pointer hover:bg-rose-100 ${
                      selectedCustomer?.id === c.id ? "bg-rose-100" : ""
                    }`}
                    onClick={() => {
                      setSelectedCustomer(c);
                      setGuestName("");
                      setCustomerError("");
                      setName(c.name || "");
                      setMobile(c.phone || "");
                    }}
                  >
                    {c.photo && (
                      <img
                        src={c.photo}
                        alt={c.name}
                        className="w-6 h-6 rounded-full object-cover"
                      />
                    )}
                    <span className="text-sm">
                      {c.name}（ID: {c.id}）
                    </span>
                  </li>
                ))}
              </ul>
            )}

            {selectedCustomer && (
              <p className="text-sm text-rose-700 mb-2">
                已選擇客人：{selectedCustomer.name}（ID: {selectedCustomer.id}）
              </p>
            )}

            <div className="mt-2">
              <label className="block text-sm mb-1">或改為輸入訪客姓名</label>
              <input
                type="text"
                value={guestName}
                onChange={(e) => {
                  setGuestName(e.target.value);
                  if (e.target.value.trim()) {
                    setSelectedCustomer(null);
                  }
                  setCustomerError("");
                }}
                className="border p-2 rounded w-full"
                placeholder="訪客姓名（無會員帳號時使用）"
              />
            </div>

            {customerError && (
              <p className="text-red-500 text-sm mt-1">{customerError}</p>
            )}
          </div>
        )}

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
          {user?.role === "owner" ? "送出代客預約" : "送出預約"}
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