# Pytest 測試筆記

對應專案檔案：`tests/conftest.py`、`tests/test_health_and_services.py`、`tests/test_bookings.py`  
測試對象：`app/main.py`（FastAPI 路由與預約規則）

---

## 1. 測試架構重點

- 使用 `pytest` 搭配 FastAPI `TestClient` 做 API 整合測試。
- 每個測試透過 fixture `client` 取得乾淨的測試資料庫與 HTTP client。
- 以「建立使用者 -> 建立預約 -> 查詢/取消」流程覆蓋核心業務邏輯。

---

## 2. `conftest.py` fixture 設計

### `client` fixture 做了什麼

1. 用 `tmp_path` 建立臨時 SQLite 檔案（每次測試隔離）。
2. 建立測試專用 `engine`、`TestingSessionLocal`。
3. `Base.metadata.create_all` 建表。
4. 匯入 `SEED_SERVICES` 種子服務資料。
5. 覆寫 `get_db` 依賴，讓 API 使用測試資料庫 session。
6. 用 `monkeypatch` 避免 app startup 打到非測試 DB：
   - `init_db = lambda: None`
   - `SessionLocal = TestingSessionLocal`
7. `yield TestClient(app)` 執行測試。
8. 收尾：清除 dependency overrides、drop table、dispose engine。

### 這樣做的好處

- 測試可重複執行（deterministic）。
- 不污染正式資料庫。
- 每個案例互不影響，降低 flaky test。

---

## 3. `test_health_and_services.py` 測什麼

### `test_health`

- `GET /health` 應回 `200`
- body 應為 `{"status": "ok", "db": "sqlite"}`

### `test_list_services_sorted`

- `GET /services` 應回 `200`
- 回傳筆數要等於 `SEED_SERVICES`
- 驗證排序規則：先依 `CATEGORY_ORDER`，再依 `sort_order`

### `test_list_services_by_category_order`

- `GET /services/by-category` 應回 `200`
- 回傳 key 順序要符合 `CATEGORY_ORDER`（僅包含有資料的分類）
- 每個分類都至少有一筆服務

---

## 4. `test_bookings.py` 測什麼

### 測試輔助函式

- `_create_user`：建立使用者並回傳 `id`
- `_get_service_ids_by_category`：抓某分類 service id 清單
- `_create_booking`：共用建預約 payload 與 request

### 主要情境覆蓋

1. **成功流程**
   - 建立 user + booking 成功
   - 可列出預約與查詢單筆

2. **同分類多選被拒**
   - 同一分類選兩個 service -> `400`
   - 錯誤訊息含「同一分類只能選一項」

3. **服務不存在**
   - 傳不存在的 `service_id` -> `404`

4. **時段衝突**
   - 同使用者在重疊時間建立預約 -> `409`

5. **owner 代客預約權限**
   - owner 可代客建立預約（`200`）
   - 非 owner 代他人預約 -> `403`

6. **取消預約權限與不存在**
   - 非本人且非 owner 取消 -> `403`
   - owner 可取消 -> status 變 `cancelled`
   - 取消不存在預約 -> `404`

---

## 5. 這份測試驗證到的業務規則

- 服務清單排序一致性（分類順序 + 自訂排序）。
- 預約建立的資料正確性（關聯 service、狀態）。
- 分類 X 選 1 的限制。
- 預約時段衝突檢查。
- owner 與 customer 的權限邏輯。
- 取消預約流程與例外處理。

---

## 6. 後續可補強的測試建議

- `GET /bookings?date=...` 的日期過濾邏輯。
- 重複取消（idempotent）是否維持預期行為。
- 邊界時間案例（剛好接續不重疊、跨日預約）。
- 參數驗證錯誤（422）案例，如缺欄位、型別錯誤。
- 空資料情境（無服務、無預約）回傳格式檢查。
