# 專案文件清單與版本控制指南

本檔說明本儲存庫**需要與建議維護的文件**、彼此關係，以及 **Git / GitHub 工作流程與命名慣例**。  
工程細節與階段驗收仍以 [SPECIFICATION.md](./SPECIFICATION.md) 為準；**面試目標與決策摘要**見 [SPEC_INTERVIEW_V1.md](./SPEC_INTERVIEW_V1.md)；商業背景與故事見根目錄 [NOTES.md](../NOTES.md)。

---

## 1. 文件地圖（你現在在哪裡）

| 檔案 | 用途 | 維護時機 |
| --- | --- | --- |
| [README.md](../README.md) | 如何安裝、啟動、主要連結入口 | 指令變更、重要連結增刪 |
| [NOTES.md](../NOTES.md) | 產品構想、角色、舊專案關係、學習路線 | 需求或商業敘事變更 |
| [docs/SPECIFICATION.md](./SPECIFICATION.md) | **規格書**：API、商業規則、階段 A–J、環境變數 | API/規則/階段完成時更新 |
| [docs/SPEC_INTERVIEW_V1.md](./SPEC_INTERVIEW_V1.md) | **面試目標規格**：MVP、Demo、24h 取消等決策與驗收摘要 | 面試範圍或目標規則變更時 |
| `docs/PROJECT_DOCS_AND_GIT.md`（本檔） | 文件清單 + Git 慣例 | 協作方式或文件策略變更時 |
| `note/*.md` | 個人學習筆記（pytest、models 等） | 隨學習更新；**不必**與 release 綁定 |
| `.env.example`（建議補） | 環境變數範本（不含密鑰） | 新增整合（LINE、DB、Google）時 |
| `CONTRIBUTING.md`（選用） | 若對外開放貢獻，可將本檔「§3」摘過去 | 開源或多人協作時 |

---

## 2. 建議擁有的文件類型（檢查清單）

### 必備（面試／可重現執行）

- [x] **README**：一鍵指令、連到規格與健康檢查
- [x] **規格書**（`docs/SPECIFICATION.md`）：API 與商業規則、驗收基線
- [ ] **`.env.example`**：列出 `DATABASE_URL`、`LINE_*`、Google 憑證路徑等**鍵名**（值用占位符）
- [ ] **授權**（選用）：`LICENSE` 若公開 repo

### 建議（上線與整合）

- [ ] **部署說明**：可放在 README 一節或 `docs/DEPLOYMENT.md`（Render、Docker、環境變數）
- [ ] **架構圖或資料流**（一頁即可）：LINE → API → DB → Google Calendar；可放 `docs/` 或 README

### 選用（團隊變大時）

- [ ] **ADR**（Architecture Decision Records）：重大技術決策短文，放 `docs/adr/`
- [ ] **CHANGELOG.md**：若開始對外打 tag 發版，可搭配 [Keep a Changelog](https://keepachangelog.com/) 風格

---

## 3. 版本控制建議

### 3.1 分支策略：GitHub Flow（簡化）

- **主分支 `main`**：預設可部署、可 demo；穩定可合併目標。
- **功能／修復**：從 `main` 開**短命分支** → 開 **Pull Request** → CI 通過 → 合併回 `main`。
- 面試用單人專案**不必**採用完整 GitFlow（長期 `develop` / `release`），除非你真的需要平行發版。

### 3.2 分支命名

格式：**`類型/簡短說明-kebab-case`**（小寫、連字號、避免空白與中文）。

| 前綴 | 用途 | 範例 |
| --- | --- | --- |
| `feat/` | 新功能 | `feat/line-webhook` |
| `fix/` | 修 bug | `fix/booking-cancel-window` |
| `test/` | 測試 | `test/bookings-date-filter` |
| `chore/` | 工具、CI、依賴 | `chore/ci-pytest` |
| `docs/` | 僅文件 | `docs/readme-deploy` |

### 3.3 Commit 訊息（Conventional Commits）

格式：**`類型(可選範圍): 簡短說明`**

| 類型 | 用途 |
| --- | --- |
| `feat` | 新功能 |
| `fix` | 修 bug |
| `test` | 測試 |
| `docs` | 文件 |
| `chore` | 雜項 |
| `refactor` | 重構（行為不變） |
| `ci` | CI 設定 |

範例：`feat(line): add webhook signature verification`、`test(bookings): cover date query`。

### 3.4 Pull Request

- 一個 PR 對應**一個主題**；標題與分支意義一致。
- 合併策略擇一固定即可：**Squash merge**（歷史較乾淨）或 **Merge commit**。

### 3.5 版本標籤（Tag）

- 對外里程碑使用 **Semantic Versioning**：`主.次.修`（例如 `0.2.0`）。
- Git 標籤建議 **`v` 前綴**：`v0.1.0`、`v0.2.0`，與 Release 說明對齊。
- **Commit** 記錄開發過程；**Tag** 標記「可對外說的版本」（履歷、面試 demo）。

---

## 4. 文件與程式變更的對應（簡表）

| 你改了什麼 | 建議更新 |
| --- | --- |
| 新增或變更 HTTP API | `docs/SPECIFICATION.md`（§3）、必要時 README 連結 |
| 商業規則（預約、取消、權限） | `docs/SPECIFICATION.md`、`NOTES.md`（若影響產品敘事） |
| 環境變數或部署方式 | `.env.example`、README 或 `docs/DEPLOYMENT.md` |
| 僅內部重構、測試 | 可不動對外文件；重大可寫一句於 PR 說明 |

---

## 5. 相關連結

- [開發規格書（階段驗收、API）](./SPECIFICATION.md)
- [面試目標規格書](./SPEC_INTERVIEW_V1.md)
- [專案背景與需求長文](../NOTES.md)
- [README（快速開始）](../README.md)
