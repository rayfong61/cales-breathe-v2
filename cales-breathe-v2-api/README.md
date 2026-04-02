# Cale's Breathe API v2

LINE 熱蠟工作室預約系統後端（最小 MVP：FastAPI + SQLite）

## 快速開始

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

- API 文件：http://127.0.0.1:8000/docs
- 健康檢查：http://127.0.0.1:8000/health

## 專案說明

- 背景與需求：[NOTES.md](./NOTES.md)
- **開發規格書（階段驗收、API 現況）**：[docs/SPECIFICATION.md](./docs/SPECIFICATION.md)
- **面試目標規格書（MVP、商業規則決策、Demo）**：[docs/SPEC_INTERVIEW_V1.md](./docs/SPEC_INTERVIEW_V1.md)
- **文件清單與 Git 版本控制建議**：[docs/PROJECT_DOCS_AND_GIT.md](./docs/PROJECT_DOCS_AND_GIT.md)
