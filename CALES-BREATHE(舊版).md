# Cale's Breathe 熱蠟美肌預約系統
#### Demo:  <https://cales-breathe-5vk9.vercel.app/>
#### Video Demo:  <https://youtu.be/NNO4vuKKK4U>
[ 測試用帳號: tester1@gmail.com / 密碼:000000 ]

一個為熱蠟工作室設計的客製化預約平台，結合前台預約、用戶帳戶管理與客戶評價展示，專為提升預約效率與品牌形象而打造。

## 功能特色
### 首頁: 形象影片/店家介紹/顧客回饋
![Demo](frontend/src/assets/home.gif)
### 服務項目: 服務介紹/照片/價目表/預約按鈕
![Demo](frontend/src/assets/services.gif)
### 線上預約
![Demo](frontend/src/assets/booking.gif)
### 會員: 註冊 / 登入（支援 LINE、Google OAuth）/ 查看個人預約紀錄 / 編輯帳戶資料 / 上傳大頭貼
![Demo](frontend/src/assets/account.gif)
### 響應式設計，支援手機與桌機
 ![Demo](frontend/src/assets/home-mobile.gif)
 ![Demo](frontend/src/assets/services-mobile.gif)
 ![Demo](frontend/src/assets/booking-mobile.gif)
 ![Demo](frontend/src/assets/account-mobile.gif)

## 技術

- 前端 : React + Vite, Tailwind CSS, React Router
- 後端 : Node + Express / RESTful API / bcrypt / Session / OAuth
- 資料庫 : PostgreSQL
- 第三方登入 : Google OAuth 2.0, LINE Login
- 狀態管理 : React Context (useAuth) + localStorage
- 部署 : Vercel（前端）、Render（後端 + DB）
- 資料庫管理 : pgAdmin

##  未來計畫
- 業者後台:月曆視圖檢視與編輯所有預約
- 業者後台:客戶名單與聯絡資料總覽
- 預約後發e-mail通知

## 作者

### Ray Lu
rayfong61@gmail.com


##  License

本專案為學習用途，未授權商業使用。如需合作請來信洽談。
