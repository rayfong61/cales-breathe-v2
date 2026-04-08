import axios from "axios";
import { useState, useEffect } from "react";
import { useAuth } from "../components/AuthContext"; 

function Orders() {
  const api = import.meta.env.VITE_API_BASE;
  const CANCELLED_META_KEY = "cancelled_orders_meta_v1";
  const THIRTY_DAYS_MS = 30 * 24 * 60 * 60 * 1000;
  const { user } = useAuth();
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState("");
  const [cancelledMeta, setCancelledMeta] = useState(() => {
    try {
      const raw = localStorage.getItem(CANCELLED_META_KEY);
      return raw ? JSON.parse(raw) : {};
    } catch {
      return {};
    }
  });

  const handleCancel = async (id) => {
    if (!window.confirm("確定要取消這筆預約嗎？")) return;
  
    try {
      await axios.put(`${api}/orders/cancel/${id}`, {}, { withCredentials: true });
      const cancelledAt = new Date().toISOString();
      // 不直接移除，改為標記已取消，保留歷史紀錄更符合帳務/預約情境
      setOrders((prev) =>
        prev.map((order) =>
          order.id === id ? { ...order, is_cancelled: true } : order
        )
      );
      setCancelledMeta((prev) => {
        const next = { ...prev, [id]: cancelledAt };
        localStorage.setItem(CANCELLED_META_KEY, JSON.stringify(next));
        return next;
      });
      alert("預約已取消");
    } catch (err) {
      console.error("取消失敗", err);
      const message =
        err?.response?.data?.detail ||
        err?.response?.data?.message ||
        "取消預約失敗";
      alert(message);
    }
  };
  
  

  useEffect(() => {
    if (!user?.id) return;

    const fetchOrders = async () => {
      try {
        const endpoint = user?.role === "owner" ? `${api}/owner/orders` : `${api}/orders`;
        const reqConfig = user?.role === "owner"
          ? { withCredentials: true }
          : { params: { client_id: user.id }, withCredentials: true };
        const res = await axios.get(endpoint, reqConfig);
        setOrders(res.data);
        // console.log(res.data);
      } catch (err) {
        setErrorMsg("無法取得預約紀錄");
        console.error(err);
      } finally {
        setLoading(false);
      }
      
    };

    fetchOrders();
  }, [user]);

  if (loading) return <p>載入中...</p>;
  if (errorMsg) return <p>{errorMsg}</p>;

  const nowMs = Date.now();
  const visibleOrders = orders
    .filter((order) => {
      if (!order.is_cancelled) return true;
      const cancelledAt = cancelledMeta[order.id];
      if (!cancelledAt) return true; // 舊資料無取消時間時先保留顯示
      return nowMs - new Date(cancelledAt).getTime() < THIRTY_DAYS_MS;
    })
    .sort((a, b) => {
      if (a.is_cancelled !== b.is_cancelled) {
        return a.is_cancelled ? 1 : -1; // 已取消永遠排在最下方
      }
      const aMs = new Date(`${a.booking_date}T${a.booking_time}`).getTime();
      const bMs = new Date(`${b.booking_date}T${b.booking_time}`).getTime();
      return bMs - aMs;
    });
  

  return (
    <div>
      
      {visibleOrders.length === 0 ? (
        <p>目前沒有預約紀錄</p>
      ) : (
        <ul>
          {visibleOrders.map((order) => {
            
            const date = new Date(order.booking_date);
            const formattedDate = date.toLocaleDateString("zh-TW", {
                year: "numeric",
                month: "2-digit",
                day: "2-digit"
            });
            const detail = order.booking_detail;
            const bookingDateTime = new Date(`${order.booking_date}T${order.booking_time}`);
            const canCancel = user?.role === "owner"
              ? !order.is_cancelled
              : bookingDateTime >= new Date() && !order.is_cancelled;

            const statusMap = {
              pending:   { label: "確認中", cls: "bg-yellow-100 text-yellow-700 border border-yellow-300" },
              confirmed: { label: "已確認", cls: "bg-green-100 text-green-700 border border-green-300" },
              completed: { label: "已完成", cls: "bg-gray-100 text-gray-500 border border-gray-300" },
              cancelled: { label: "已取消", cls: "bg-red-100 text-red-400 border border-red-300" },
            };
            const statusInfo = statusMap[order.status] ?? { label: order.status, cls: "bg-gray-100 text-gray-500" };

            return (
              <li key={order.id} className="mb-4 border-b border-gray-300 pb-4">
                <div className="flex items-center justify-between mb-1">
                  <p className="text-sm text-gray-400">訂單編號：#{order.id}</p>
                  <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${statusInfo.cls}`}>
                    {statusInfo.label}
                  </span>
                </div>
                <div className="space-y-1">
                  {user?.role === "owner" && (
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                    {order.customer_photo && (
                      <img
                        src={order.customer_photo}
                        alt={order.customer_name || "客人"}
                        className="w-8 h-8 rounded-full object-cover"
                      />
                    )}
                    <p>
                      <strong>客人：</strong>
                      {order.customer_name || "訪客"}
                      {order.customer_id ? ` (ID: ${order.customer_id})` : ""}
                    </p>
                      </div>
                      {order.customer_phone && (
                        <p>
                        <strong>手機：</strong>
                        {order.customer_phone}
                        </p>
                      )}
                    </div>
                  )}
                  <p><strong>預約日期：</strong>{formattedDate}</p>
                  <p><strong>時間：</strong>{order.booking_time.slice(0,5)}</p>   
                  <p><strong>服務內容：</strong>{detail.services?.join("、")}</p>
                  <p><strong>加購項目：</strong>{detail.addons?.join("、") || "無"}</p>
                  <p><strong>總價格：</strong>${order.total_price}</p>
                  <p><strong>總時長：</strong>{order.total_duration} 分鐘</p>
                  <p><strong>備註：</strong>{order.booking_note} </p>
                </div>
                {canCancel && (
                  <button
                    type="button"
                    onClick={() => handleCancel(order.id)}
                    className="mt-3 px-5 py-1 bg-red-400 text-white rounded hover:bg-red-500 cursor-pointer"
                  >
                    取消預約
                  </button>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

export default Orders;

// 👉     style={{ marginBottom: "1rem", borderBottom: "1px solid #ccc", paddingBottom: "1rem" }}
// 等同 >> className="mb-4 border-b border-gray-300 pb-4"

// 👉 order.booking_time.slice(0, 5)     
// 從 order.booking_time 字串中，擷取前五個字元（從索引 0 開始，到索引 5 結束，但不包含 5）。
// "17:00:00" -> "17:00"
// 因為時間資料通常是 "HH:MM:SS" 格式，但在畫面上我們只需要顯示到「分鐘」，所以只取 "HH:MM"。

// 👉 {detail.services?.join("、")} 
// ?. 是 ES2020 的語法，意思是：
// 如果 detail.services 存在，就呼叫 join()；如果是 undefined 或 null，就不做任何事，避免程式報錯。

// join("、")
// join() 是陣列的方法，會把陣列中的每一個元素，用指定的分隔符（這裡是「、」）組合成一個字串。

// 假設 detail.services = ["A", "B", "C"]，畫面會顯示： A、B、C