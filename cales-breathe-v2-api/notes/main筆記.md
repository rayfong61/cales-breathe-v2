# FastAPI `main` 重點筆記

對應專案檔案：`app/main.py`  
相關檔案：`app/database.py`（`get_db`、`init_db`、`SessionLocal`）、`app/models.py`、`app/schemas.py`

---

## 1. 檔案角色（一句話）

`main.py` 是 **API 入口**：註冊路由、啟動時建表與種子資料、實作預約業務規則（分類 X 選 1、時段衝突、取消權限），並用 Pydantic `response_model` 與依賴注入 `Depends(get_db)` 串接資料庫。

---

## 2. `lifespan`（取代 `@app.on_event("startup")`）

**為何用 lifespan**：FastAPI 建議用 **`lifespan` 上下文** 管理應用程式啟動／關閉；舊的 `on_event` 已標為 deprecated。

**本專案啟動時做什麼**（`yield` 之前）：

1. `init_db()`：依 ORM 建立資料表。
2. `SessionLocal()` 開 session，`services` 若筆數為 0，則寫入 `SEED_SERVICES` 並 `commit`。
3. `finally` 裡 **`db.close()`**，避免 session 未關閉。
4. **`yield`**：之後應用程式開始接請求；若要關閉時釋放資源，可寫在 `yield` 之後。

```python
app = FastAPI(..., lifespan=lifespan)
```

---

## 3. `CATEGORY_ORDER` 與 `_category_sort_key`

- **`CATEGORY_ORDER`**：選單／分類的**顯示順序**（字串列表）。
- **`_category_sort_key(category)`**：回傳該分類在 `CATEGORY_ORDER` 的**索引**；若分類不在清單內，回傳 `99` 讓未知分類通常排在最後。

`list_services` 用 `services.sort(key=lambda s: (_category_sort_key(s.category), s.sort_order))` 排序。

---

## 4. `SEED_SERVICES` 種子資料

啟動時若 `services` 表為空，會依此列表建立 `Service` 列。每筆為 `dict`，欄位對應 model（如 `name`、`category`、`price`、`duration_minutes`、`sort_order`）。

---

## 5. 路由一覽

| 方法 | 路徑 | 說明 |
|------|------|------|
| GET | `/health` | 健康檢查 |
| GET | `/services` | 全部服務（依分類選單順序 + `sort_order`） |
| GET | `/services/by-category` | 依分類分組（給 LINE Bot／前端選單） |
| POST | `/users` | 建立使用者（`role` 可為 `customer` / `owner`） |
| POST | `/bookings` | 建立預約（多服務、X 選 1、時段衝突檢查） |
| GET | `/bookings` | 查詢預約（僅 `confirmed`）；查詢參數 `date` 可篩當日 |
| GET | `/bookings/{booking_id}` | 單一預約（不限狀態） |
| POST | `/bookings/{booking_id}/cancel` | 取消預約（軟刪除）；body 需 `user_id`（本人或 owner） |

---

## 6. `Counter` 與「同一分類最多一項」（X 選 1）

**`_validate_category_max_one(services)`**：

- 用 `collections.Counter` 統計各 `category` 出現次數。
- 若某分類出現超過 1 次，丟 **`HTTPException(400)`**。

---

## 7. 建立預約 `create_booking`

1. 依 `service_ids` 查 `Service`；數量不符則 **404**。
2. 呼叫 `_validate_category_max_one`。
3. 加總時長與金額；`end = booking_date + timedelta(minutes=total_duration)`。
4. **時段衝突**：只與 `status == "confirmed"` 的預約比對；區間重疊條件為 `start < b_end and b.booking_date < end`，衝突則 **409**。
5. 建立 `Booking` 並指定 `booking.services` 關聯，commit 後回傳 `_booking_to_read`。

---

## 8. 輔助函式

| 函式 | 用途 |
|------|------|
| `_booking_to_read` | 將 ORM `Booking` 轉成 `BookingRead`（含 `services` 列表）。 |
| `_assert_can_cancel_booking` | 僅當 `actor.role == "owner"` 或 `actor.id == booking.user_id` 時允許取消，否則 **403**。 |

---

## 9. 取消預約 `cancel_booking`

1. 依 body `user_id` 找操作者；不存在則 **404**「使用者不存在」。
2. 載入預約；不存在則 **404**「預約不存在」。
3. `_assert_can_cancel_booking`。
4. 若已是 **`cancelled`**：直接回傳（冪等）。
5. 若狀態不是 **`confirmed`**：**400**（例如已完成）。
6. 否則將 `status` 設為 **`cancelled`**（軟刪除，不 `db.delete`），commit 後回傳。

**為何軟刪除**：保留紀錄、與「只把 `confirmed` 當佔時段」的邏輯一致；詳見先前討論。

---

## 10. `list_bookings` 與 `joinedload`

- 預設只列出 **`confirmed`**。
- 可選查詢參數 **`date`**（別名）：篩選該曆日內的 `booking_date`（以當日 00:00 至次日 00:00）。
- **`joinedload(Booking.services)`**：避免 N+1 查詢，一次載入關聯服務。

---

## 11. 依賴注入 `Depends(get_db)`

每個需要資料庫的路由透過 `db: Session = Depends(get_db)` 取得 Session；請求結束後由 `get_db` 負責關閉（見 `database.py`）。**lifespan 裡的 `SessionLocal()`** 僅用於啟動種子，與請求內的 `get_db` 分開。
