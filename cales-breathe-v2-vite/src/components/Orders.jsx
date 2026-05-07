import { useState, useEffect } from "react";
import { useAuth } from "../components/AuthContext"; 
import { api } from "../api/client";

function Orders() {
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

  const formatBookingDate = (bookingDateIso) => {
    const dt = new Date(bookingDateIso);
    return dt.toLocaleDateString("zh-TW", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    });
  };

  const formatBookingTime = (bookingDateIso) => {
    const dt = new Date(bookingDateIso);
    return dt.toTimeString().slice(0, 5);
  };

  const toLegacyLikeOrder = (b) => {
    const services = (b.services || []).filter((s) => !String(s.category).startsWith("addon-"));
    const addons = (b.services || []).filter((s) => String(s.category).startsWith("addon-"));
    return {
      id: b.id,
      user_id: b.user_id,
      booking_date: b.booking_date,
      booking_time: formatBookingTime(b.booking_date),
      total_price: b.total_price,
      total_duration: b.total_duration_minutes,
      booking_note: b.notes,
      is_cancelled: b.status === "cancelled",
      status: b.status,
      booking_detail: {
        services: services.map((s) => s.name),
        addons: addons.map((s) => s.name),
      },
      guest_name: b.guest_name,
      customer_name: b.customer_name || b.guest_name || `會員 #${b.user_id ?? "-"}`,
      customer_phone: b.customer_phone || b.guest_phone,
      customer_photo: b.customer_photo || null,
    };
  };

  const handleCancel = async (id) => {
    if (!window.confirm("確定要取消這筆預約嗎？")) return;
  
    try {
      await api.post(`/bookings/${id}/cancel`, {});
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
        const res = await api.get("/bookings");
        setOrders((res.data || []).map(toLegacyLikeOrder));
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
      const aMs = new Date(a.booking_date).getTime();
      const bMs = new Date(b.booking_date).getTime();
      return bMs - aMs;
    });
  

  return (
    <div>
      
      {visibleOrders.length === 0 ? (
        <p>目前沒有預約紀錄</p>
      ) : (
        <ul>
          {visibleOrders.map((order) => {
            
            const formattedDate = formatBookingDate(order.booking_date);
            const detail = order.booking_detail;
            const bookingDateTime = new Date(order.booking_date);
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
                    <div className="my-4 rounded-full bg-gray-100 px-3 py-2.5 flex items-center gap-3">
                      {order.customer_photo ? (
                        <img
                          src={order.customer_photo}
                          alt=""
                          className="w-10 h-10 rounded-full object-cover shrink-0"
                        />
                      ) : (
                        <div
                          className="w-10 h-10 rounded-full bg-gray-200 shrink-0 flex items-center justify-center text-sm font-medium text-gray-600"
                          aria-hidden
                        >
                          {(order.customer_name || "訪").slice(0, 1)}
                        </div>
                      )}
                      <div className="min-w-0 flex-1">
                        <p className="text-lg font-semibold text-gray-900 leading-tight truncate">
                          {order.customer_name || "訪客"}
                        </p>
                        {order.user_id != null && (
                          <p className="text-xs text-gray-500 mt-0.5">
                            客人 · ID：{order.user_id}
                          </p>
                        )}
                      </div>
                      {order.customer_phone ? (
                        <a
                          href={`tel:${String(order.customer_phone).replace(/[^\d+]/g, "")}`}
                          className="shrink-0 text-gray-600 hover:text-gray-900 p-1 -mr-1 rounded-full focus:outline-none focus-visible:ring-2 focus-visible:ring-gray-400"
                          aria-label={`撥打 ${order.customer_phone}`}
                          title={order.customer_phone}
                        >
                          <svg
                            xmlns="http://www.w3.org/2000/svg"
                            className="w-6 h-6"
                            fill="none"
                            viewBox="0 0 24 24"
                            stroke="currentColor"
                            strokeWidth={2}
                            aria-hidden
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z"
                            />
                          </svg>
                        </a>
                      ) : null}
                    </div>
                  )}
                  {user?.role === "owner" && order.customer_phone && (
                    <p>
                      <strong>手機：</strong>
                      {order.customer_phone}
                    </p>
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