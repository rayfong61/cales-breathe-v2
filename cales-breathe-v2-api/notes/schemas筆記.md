# Pydantic Schemas 重點筆記

對應專案檔案：`app/schemas.py`

---

## 1. `@field_validator` 用法

**用途**：欄位通過型別檢查後，再對單一或多個欄位做自訂邏輯（清洗、業務規則等）。

**本專案範例**（`BookingCreate.service_ids` 不可為空清單）：

```python
@field_validator("service_ids")
@classmethod
def service_ids_not_empty(cls, v: list[int]) -> list[int]:
    if not v:
        raise ValueError("至少需選擇一項服務")
    return v
```

**重點**：

- 裝飾器內寫欄位名，可多個：`@field_validator("a", "b")`。
- 驗證函式須為 **`@classmethod`**，參數為 `cls` 與該欄位值 `v`。
- **回傳值**會成為該欄位最終寫入模型的值（可做 strip、正規化等）。
- 規則不符時丟 **`ValueError`**，Pydantic 會轉成驗證錯誤（例如 FastAPI 回傳 422）。

**與 `Field(...)` 的取捨**：長度、範圍等可用 `Field` 宣告式處理；需要程式邏輯時用 `field_validator`。

**多欄一起驗證**：Pydantic v2 使用 **`model_validator`**；單欄規則用 `field_validator` 即可。

---

## 2. `class Config: from_attributes = True`

**用途**：允許從「有屬性的物件」（例如 SQLAlchemy ORM 實例）建立 model，而不只接受 `dict`。Pydantic 會用**屬性名**對應欄位名。

**本專案**：`ServiceRead`、`UserRead`、`BookingRead` 皆設定：

```python
class Config:
    from_attributes = True
```

**為什麼 API 常用**：路由中若將 ORM 物件轉成回應 schema（例如 `Model.model_validate(db_obj)`），資料來自 `obj.id`、`obj.name` 等屬性，必須開啟 `from_attributes`（舊版 Pydantic v1 對應為 `orm_mode = True`）。

**Pydantic v2 另一寫法**（與上面等價，擇一即可）：

```python
from pydantic import ConfigDict

model_config = ConfigDict(from_attributes=True)
```

---

## 3. Pydantic 在本專案中的角色

**Pydantic**：用 Python **型別標註** 描述資料結構，並負責 **驗證、預設值、轉型、序列化**（含 `datetime`、巢狀 model）。

**搭配 FastAPI 時**：

| 用途 | 說明 |
|------|------|
| Request body | 如 `BookingCreate`，自動驗證 JSON，失敗回 422 |
| Response model | 如 `ServiceRead`，限制輸出欄位與型別，產生 JSON / OpenAPI |
| 與 ORM 分離 | DB 模型在 `models.py`，對外契約在 `schemas.py`，可避免直接暴露內部欄位 |

**本專案命名慣例**：

- **`XxxBase`**：共用欄位。
- **`XxxCreate`**：建立資源時的 body。
- **`XxxRead`**：讀取回傳（含 `id`、`created_at` 等），並設 `from_attributes` 以利從 ORM 轉換。

---

## 參考

- Pydantic v2：`field_validator`、`model_validate`、`ConfigDict`
- 官方文件：<https://docs.pydantic.dev/>
