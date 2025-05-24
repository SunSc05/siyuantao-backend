# 思源淘 - 项目开发 TODO 列表

---

## 项目总览
本文档旨在提供【思源淘】项目的开发任务总览，按照技术层级进行划分，并细化到具体的功能模块和文件路径。请各位开发者根据分配的模块，及时更新相关任务的状态。

## 团队分工（示例，请根据实际情况填写）
* **开发者 A:** 主要负责：用户模块 (SQL, DAL, Service, API, Frontend)
* **开发者 B:** 主要负责：商品浏览与收藏 (SQL, DAL, Service, API, Frontend)
* **开发者 C:** 主要负责：商品操作与交易评价 (SQL, DAL, Service, API, Frontend)
* **开发者 D:** 主要负责：实时通讯与退货 (SQL, DAL, Service, API, Frontend)
* **开发者 E:** 主要负责：通知、举报及通用基础设施 (SQL, DAL, Service, API, Frontend, Common)

## 约定
* **状态标记:**
    * `[x] DONE:`：任务已完成。
    * `[ ] TODO:`：任务待完成。
    * `[!] OPTIONAL:`：可选任务或未来优化项。
    * `[#] PENDING:`: 任务暂停/等待依赖。
* **更新频率:** 每日站会前更新个人负责的任务状态。
* **Git Commit:** 提交代码时，在 commit message 中引用相关 TODO 项（例如：`feat(user): implements user registration API (TODO: #Backend-API-User-1)`）。

---

## 1. SQL 数据库层

**概述:** 本层负责所有数据库表结构、存储过程、函数和触发器的设计与实现。

### 1.1 用户模块
* **文件:** `backend/sql/01_create_tables.sql`
    * [x] **DONE:** `CREATE TABLE [User]`: 用户基础信息表，包含 `UserID`, `UserName`, `Password` (哈希), `Email`, `Major`, `IsVerified`, `VerificationToken`, `TokenExpireTime`, `Status`, `Credit`, `IsStaff`, `JoinTime`, `AvatarUrl`, `Bio`, `PhoneNumber` 等字段。
        * **备注:** 确认所有字段类型、长度和约束符合要求。
        * **Major 字段备注:** 考虑到表数量限制，Major 字段将在前端进行硬编码下拉列表，数据库层面保留 NVARCHAR(100) 类型。
* **文件:** `backend/sql/01_user_procedures.sql`
    * [x] **DONE:** `sp_GetUserProfileById (@userId)`: 根据用户ID获取用户公开信息，用于展示个人主页等。
    * [x] **DONE:** `sp_GetUserByUsernameWithPassword (@username)`: 根据用户名获取用户（包含密码哈希），用于登录验证。
    * [x] **DONE:** `sp_CreateUser (@username, @passwordHash, @email)`: 创建新用户，检查用户名和邮箱唯一性，设置初始状态和信用分。
    * [x] **DONE:** `sp_UpdateUserProfile (@userId, ...)`: 更新用户个人信息（专业、头像、简介、手机号），检查手机号唯一性。
    * [x] **DONE:** `sp_GetUserPasswordHashById (@userId)`: 根据用户ID获取密码哈希，用于密码修改等场景。
    * [x] **DONE:** `sp_UpdateUserPassword (@userId, @newPasswordHash)`: 更新用户密码。
    * [x] **DONE:** `sp_RequestMagicLink (@email)`: 用户请求魔术链接，用于无密码登录或注册。查找用户，如果是新用户则创建，老用户则更新 token。
    * [x] **DONE:** `sp_VerifyMagicLink (@token)`: 验证魔术链接，完成用户邮箱认证（`IsVerified = 1`），清除 token。
    * [x] **DONE:** `sp_GetSystemNotificationsByUserId (@userId)`: 获取某个用户的系统通知列表。
    * [x] **DONE:** `sp_MarkNotificationAsRead (@notificationId, @userId)`: 将指定系统通知标记为已读，验证操作者是通知接收者。
    * [!] **OPTIONAL:** `sp_GetUserByEmail (email)`: 用于注册时检查邮箱重复，或找回密码。
* **文件:** `backend/sql/05_admin_procedures.sql` (管理员用户管理部分)
    * [x] **DONE:** `sp_ChangeUserStatus (@userId, @newStatus, @adminId)`: 管理员禁用/启用用户账户。
    * [x] **DONE:** `sp_AdjustUserCredit (@userId, @creditAdjustment, @adminId, @reason)`: 管理员手动调整用户信用分。
    * [x] **DONE:** `sp_GetAllUsers (@adminId)`: 管理员获取所有用户列表。
* **文件:** `backend/sql/07_chat_procedures.sql` (ChatMessage 逻辑删除部分)
    * [x] **DONE:** `sp_SetChatMessageVisibility (@messageId, @userId, @visibleTo, @isVisible)`: 设置消息对发送者或接收者的可见性（逻辑删除）。
* **文件:** `backend/sql/drop_all.sql`
    * [x] **DONE:** 包含所有用户模块相关对象的删除语句。

### 1.2 商品模块
* **文件:** `backend/sql/02_create_tables.sql`
    * [ ] **TODO:** `CREATE TABLE [Product]`: 商品信息表。
    * [ ] **TODO:** `CREATE TABLE [ProductImage]`: 商品图片表。
    * [ ] **TODO:** `CREATE TABLE [UserFavorite]`: 用户收藏表。
* **文件:** `backend/sql/02_product_procedures.sql`
    * [ ] **TODO:** `sp_CreateProduct`, `sp_UpdateProduct`, `sp_DeleteProduct`, `sp_ActivateProduct`, `sp_WithdrawProduct`。
    * [ ] **TODO:** `sp_GetProductList`, `sp_GetProductById`, `sp_GetImagesByProduct`。
    * [ ] **TODO:** `sp_AddUserFavorite`, `sp_RemoveUserFavorite`, `sp_GetUserFavoriteProducts`。
* ...（继续列出商品模块的SQL任务）

### 1.3 评价模块
* **文件:** `backend/sql/03_create_tables.sql`
    * [ ] **TODO:** `CREATE TABLE [Evaluation]`: 交易评价表。
* **文件:** `backend/sql/03_evaluation_procedures.sql`
    * [ ] **TODO:** `sp_CreateEvaluation`, `sp_GetEvaluationsBySeller`。
* **文件:** `backend/sql/03_evaluation_triggers.sql`
    * [ ] **TODO:** `tr_Evaluation_AfterInsert_UpdateSellerCredit`: 评价后更新卖家信用分。
* ...（继续列出评价模块的SQL任务）

### 1.4 交易模块
* **文件:** `backend/sql/04_create_tables.sql`
    * [ ] **TODO:** `CREATE TABLE [Order]`: 订单表。
* **文件:** `backend/sql/04_order_procedures.sql`
    * [ ] **TODO:** `sp_CreateOrder`, `sp_ConfirmOrder`, `sp_CompleteOrder`, `sp_CancelOrder`。
    * [ ] **TODO:** `sp_GetOrdersByUser` (买家/卖家订单列表)。
* **文件:** `backend/sql/04_order_triggers.sql`
    * [ ] **TODO:** `tr_Order_AfterCancel_RestoreQuantity`: 订单取消时恢复商品库存。
* ...（继续列出交易模块的SQL任务）

### 1.5 消息与退货模块
* **文件:** `backend/sql/05_create_tables.sql`
    * [ ] **TODO:** `CREATE TABLE [ChatMessage]`: 聊天消息表。
    * [ ] **TODO:** `CREATE TABLE [ReturnRequest]`: 退货请求表。
* **文件:** `backend/sql/05_chat_procedures.sql`
    * [ ] **TODO:** `sp_SendMessage`, `sp_GetUserConversations`, `sp_GetChatMessagesByProductAndUsers`。
    * [ ] **TODO:** `sp_MarkMessageAsRead`, `sp_HideConversation`。
* **文件:** `backend/sql/05_return_procedures.sql`
    * [ ] **TODO:** `sp_CreateReturnRequest`, `sp_HandleReturnRequest`, `sp_BuyerRequestIntervention`。
* ...（继续列出消息与退货模块的SQL任务）

### 1.6 通知与举报模块
* **文件:** `backend/sql/06_create_tables.sql`
    * [ ] **TODO:** `CREATE TABLE [SystemNotification]`: 系统通知表。
    * [ ] **TODO:** `CREATE TABLE [Report]`: 举报表。
* **文件:** `backend/sql/06_notification_procedures.sql`
    * [ ] **TODO:** `sp_SendSystemNotification`, `sp_GetUserNotifications`, `sp_MarkNotificationAsRead`, `sp_DeleteNotification`。
    * [ ] **TODO:** `sp_CreateReport`, `sp_GetReportList` (管理员), `sp_HandleReport` (管理员)。
* ...（继续列出通知与举报模块的SQL任务）

---

## 2. 后端 DAL 层 (Python)

**概述:** 本层负责封装所有直接的数据库操作，通过调用存储过程与数据库交互。

### 2.1 用户模块
* **文件:** `backend/src/modules/user/dal/user_dal.py`
    * [x] **DONE:** `UserDAL` 类定义，注入数据库连接池。
    * [x] **DONE:** `create_user(...)`: 封装 `sp_RegisterUser`。
    * [x] **DONE:** `get_user_by_username_with_password(...)`: 封装 `sp_GetUserByUsernameWithPassword`。
    * [x] **DONE:** `get_user_by_id(...)`: 封装 `sp_GetUserProfileById`。
    * [x] **DONE:** `update_user_profile(...)`: 封装 `sp_UpdateUserProfile`。
    * [x] **DONE:** `update_user_password(...)`: 封装 `sp_UpdateUserPassword`。
    * [x] **DONE:** `get_user_password_hash_by_id(...)`: 封装 `sp_GetUserPasswordHashById`。
    * [x] **DONE:** `delete_user(...)`: 封装 `sp_DeleteUser`。
    * [x] **DONE:** `request_verification_link(...)`: 封装 `sp_RequestMagicLink`。
    * [x] **DONE:** `verify_email(...)`: 封装 `sp_VerifyMagicLink`。
    * [x] **DONE:** `get_system_notifications_by_user_id(...)`: 封装 `sp_GetSystemNotificationsByUserId`。
    * [x] **DONE:** `mark_notification_as_read(...)`: 封装 `sp_MarkNotificationAsRead`。
    * [x] **DONE:** `set_chat_message_visibility(...)`: 封装 `sp_SetChatMessageVisibility`。
    * [x] **DONE:** `change_user_status(...)`: 封装 `sp_ChangeUserStatus`。
    * [x] **DONE:** `adjust_user_credit(...)`: 封装 `sp_AdjustUserCredit`。
    * [x] **DONE:** `get_all_users(...)`: 封装 `sp_GetAllUsers`。
    * [!] **OPTIONAL:** `get_user_by_email(...)`: 封装 `sp_GetUserByEmail`。
* **文件:** `backend/tests/modules/user/test_user_dal.py`
    * [x] **DONE:** 编写 `UserDAL` 中所有方法的单元测试，使用 Mocking (如 `pytest-mock`) 模拟数据库交互。

### 2.2 商品模块
* **文件:** `backend/src/modules/product/dal/product_dal.py`
    * [ ] **TODO:** `ProductDAL` 类定义。
    * [ ] **TODO:** 实现商品创建、修改、删除、上下架、查询列表、查询详情等方法。
* **文件:** `backend/src/modules/product/dal/product_image_dal.py`
    * [ ] **TODO:** `ProductImageDAL` 类定义。
    * [ ] **TODO:** 实现图片上传（关联商品）、查询、删除等方法。
* **文件:** `backend/src/modules/product/dal/user_favorite_dal.py`
    * [ ] **TODO:** `UserFavoriteDAL` 类定义。
    * [ ] **TODO:** 实现收藏添加、移除、查询用户收藏列表等方法。
* **文件:** `backend/tests/modules/product/test_product_dal.py`
    * [ ] **TODO:** 编写 `ProductDAL`、`ProductImageDAL`、`UserFavoriteDAL` 的单元测试。
* ...（继续列出其他模块的 DAL 任务及测试）

---

## 3. 后端 Service 层 (Python)

**概述:** 本层包含核心业务逻辑、数据转换、以及协调 DAL 和其他外部服务（如邮件、支付）。

### 3.1 用户模块
* **文件:** `backend/src/modules/user/services/user_service.py`
    * [x] **DONE:** `UserService` 类定义，注入 `UserDAL`。
    * [x] **DONE:** `create_user(...)`: 业务逻辑（检查重复、密码哈希、调用 DAL 创建用户、生成Token、发送邮件）。
    * [x] **DONE:** `authenticate_user_and_create_token(...)`: 业务逻辑（验证密码、检查用户状态、生成 JWT）。
    * [x] **DONE:** `get_user_profile_by_id(...)`: 获取用户详情（可能进行数据转换）。
    * [x] **DONE:** `update_user_profile(...)`: 业务逻辑（调用 DAL 更新、处理头像URL等）。
    * [x] **DONE:** `update_user_password(...)`: 业务逻辑（验证旧密码、哈希新密码、调用 DAL 更新）。
    * [x] **DONE:** `delete_user(...)`: 业务逻辑（调用 DAL 删除）。
    * [x] **DONE:** `request_verification_email(...)`: 业务逻辑（调用 DAL 生成Token、发送邮件）。
    * [x] **DONE:** `verify_email(...)`: 业务逻辑（验证Token有效期、更新 DAL 状态）。
    * [x] **DONE:** `get_system_notifications(...)`: 调用 DAL 获取系统通知。
    * [x] **DONE:** `mark_system_notification_as_read(...)`: 调用 DAL 标记通知已读。
    * [x] **DONE:** `change_user_status(...)`: 调用 DAL 更改用户状态（管理员）。
    * [x] **DONE:** `adjust_user_credit(...)`: 调用 DAL 调整用户信用分（管理员）。
    * [x] **DONE:** `get_all_users(...)`: 调用 DAL 获取所有用户列表（管理员）。
* **文件:** `backend/tests/modules/user/test_user_service.py`
    * [ ] **TODO:** 编写 `UserService` 中所有业务方法的单元测试，使用 Mocking 模拟 `UserDAL` 及其他外部服务。

### 3.2 商品模块
* **文件:** `backend/src/modules/product/services/product_service.py`
    * [ ] **TODO:** `ProductService` 类定义。
    * [ ] **TODO:** 实现商品发布、编辑、删除、上下架（包含图片处理逻辑、库存检查等）。
    * [ ] **TODO:** 实现商品浏览、搜索、筛选（调用 DAL 进行数据查询和分页）。
    * [ ] **TODO:** 实现商品收藏（添加/移除）。
* **文件:** `backend/tests/modules/product/test_product_service.py`
    * [ ] **TODO:** 编写 `ProductService` 的单元测试。
* ...（继续列出其他模块的 Service 任务及测试）

---

## 4. 后端 API 层 (Python)

**概述:** 本层负责接收 HTTP 请求，进行请求数据验证，调用 Service 层，并返回 HTTP 响应。

### 4.1 用户认证与账户管理
* **文件:** `backend/src/modules/user/api/auth_routes.py`
    * [x] **DONE:** `APIRouter` 定义。
    * [x] **DONE:** `POST /api/v1/auth/register`: 调用 `UserService.create_user`。
    * [x] **DONE:** `POST /api/v1/auth/login`: 调用 `UserService.authenticate_user_and_create_token`。
    * [x] **DONE:** `POST /api/v1/auth/request-verification-email`: 调用 `UserService.request_verification_email`。
    * [x] **DONE:** `POST /api/v1/auth/verify-email`: 调用 `UserService.verify_email`。
    * [!] **OPTIONAL:** `POST /api/v1/auth/resend-verification-email`: 调用 `UserService.resend_verification_email` (如果实现)。
* **文件:** `backend/src/modules/user/api/user_profile_routes.py` (当前是 `app/routers/users.py`)
    * [x] **DONE:** `GET /api/v1/users/me`: 获取当前用户资料 (依赖 `get_current_user` 认证)。
    * [x] **DONE:** `PUT /api/v1/users/me`: 更新当前用户资料 (依赖 `get_current_user` 认证)。
    * [x] **DONE:** `PUT /api/v1/users/me/password`: 更新当前用户密码 (依赖 `get_current_user` 认证)。
    * [x] **DONE:** `GET /api/v1/users/{user_id}`: 管理员获取用户资料 (依赖 `get_current_active_admin_user` 认证)。
    * [x] **DONE:** `PUT /api/v1/users/{user_id}`: 管理员更新用户资料 (依赖 `get_current_active_admin_user` 认证)。
    * [x] **DONE:** `DELETE /api/v1/users/{user_id}`: 管理员删除用户 (依赖 `get_current_active_admin_user` 认证)。
    * [x] **DONE:** `PUT /api/v1/users/{user_id}/status`: 管理员更改用户状态 (依赖 `get_current_active_admin_user` 认证)。
    * [x] **DONE:** `PUT /api/v1/users/{user_id}/credit`: 管理员调整用户信用分 (依赖 `get_current_active_admin_user` 认证)。
    * [x] **DONE:** `GET /api/v1/users/`: 管理员获取所有用户列表 (依赖 `get_current_active_admin_user` 认证)。
    * [ ] **TODO:** `POST /api/v1/users/me/avatar`: 上传用户头像 (文件上传处理)。
* **文件:** `backend/tests/modules/user/test_user_api.py` (当前是 `tests/test_users_api.py`)
    * [x] **DONE:** 编写 API 接口的集成测试，使用 `httpx.AsyncClient`，可以 Mock `UserService`。
    * [ ] **TODO:** `/api/v1/users/{user_id}/status`: 测试无效状态值。
    * [x] **DONE:** `/api/v1/users/{user_id}/credit`: 测试缺少 `reason` 字段。
    * [x] **DONE:** `/api/v1/users/{user_id}/credit`: 测试信用分调整超出限制（已测试超过最大值和低于最小值）。
    * [x] **DONE:** 编写管理员获取所有用户列表 `/api/v1/users/` 的测试。

### 4.2 商品接口
* **文件:** `backend/src/modules/product/api/product_routes.py`
    * [ ] **TODO:** `POST /api/v1/products`: 发布商品。
    * [ ] **TODO:** `PUT /api/v1/products/{product_id}`: 编辑商品。
    * [ ] **TODO:** `DELETE /api/v1/products/{product_id}`: 删除商品。
    * [ ] **TODO:** `GET /api/v1/products`: 获取商品列表（带分页、筛选、搜索）。
    * [ ] **TODO:** `GET /api/v1/products/{product_id}`: 获取商品详情。
* **文件:** `backend/src/modules/product/api/favorite_routes.py`
    * [ ] **TODO:** `POST /api/v1/favorites/{product_id}`: 添加收藏。
    * [ ] **TODO:** `DELETE /api/v1/favorites/{product_id}`: 移除收藏。
    * [ ] **TODO:** `GET /api/v1/favorites`: 获取用户收藏列表。
* ...（继续列出其他模块的 API 任务及测试）

---

## 5. 后端通用组件与配置 (Python)

**概述:** 存放跨模块使用的工具、辅助函数、全局配置和依赖注入。

* **文件:** `backend/src/config/settings.py` (当前是 `app/config.py`)
    * [x] **DONE:** JWT 密钥和算法配置。
    * [ ] **TODO:** 数据库连接字符串配置（通常通过环境变量注入，但配置文件中应有读取逻辑）。
    * [ ] **TODO:** 邮件发送服务配置。
* **文件:** `backend/src/common/security.py` (当前是 `app/utils/auth.py`)
    * [x] **DONE:** 密码哈希 (Bcrypt)。
    * [x] **DONE:** JWT token 生成与验证。
* **文件:** `backend/src/common/exceptions.py` (当前是 `app/exceptions.py`)
    * [x] **DONE:** 自定义 HTTP 异常类定义 (`NotFoundError`, `IntegrityError`, `DALError`, `AuthenticationError`, `ForbiddenError`)。
* **文件:** `backend/src/common/email_sender.py`
    * [!] **OPTIONAL:** 邮件发送服务封装（待实现）。
* **文件:** `backend/src/dependencies.py`
    * [x] **DONE:** `get_db_connection`: 数据库连接依赖注入（基于 pyodbc）。
    * [x] **DONE:** `get_user_dal`: DAL 依赖注入。
    * [x] **DONE:** `get_user_service`: Service 依赖注入。
    * [x] **DONE:** `get_current_user`: JWT 认证和当前用户解析依赖注入。
    * [x] **DONE:** `get_current_active_admin_user`: JWT 认证和当前活跃管理员用户解析依赖注入。
* **文件:** `backend/src/main.py` (当前是 `app/main.py`)
    * [x] **DONE:** FastAPI 应用实例化。
    * [x] **DONE:** 注册所有 `APIRouter` (目前包含用户和认证)。
    * [x] **DONE:** 添加 CORS 中间件。
    * [x] **DONE:** 添加全局异常处理中间件。

---

## 6. 前端 (Vue.js)

**概述:** 负责用户界面、状态管理、路由和与后端 API 的交互。

### 6.1 通用部分
* **文件:** `frontend/src/api/client.js`
    * [ ] **TODO:** Axios 客户端封装：设置 `baseURL`、请求拦截器（添加 JWT Token）、响应拦截器（统一错误处理、Token 过期刷新/重定向）。
* **文件:** `frontend/src/router/index.js`
    * [ ] **TODO:** 配置全局路由守卫（例如登录状态检查）。
* **文件:** `frontend/src/utils/auth.js` (或 `src/utils/token.js`)
    * [ ] **TODO:** JWT Token 的本地存储 (`localStorage`)、读取、清除方法。
* **文件:** `frontend/src/locales/`
    * [ ] **TODO:** 国际化配置 (vue-i18n) 初始化。

### 6.2 用户模块
* **文件:** `frontend/src/store/modules/user.js`
    * [ ] **TODO:** Vuex `state`: `isLoggedIn`, `userInfo`, `authLoading`。
    * [ ] **TODO:** Vuex `mutations`: `SET_LOGIN_STATUS`, `SET_USER_INFO`。
    * [ ] **TODO:** Vuex `actions`: `login`, `register`, `logout`, `WorkspaceUserInfo`, `updateUserProfile`, `verifyEmail`, `resendVerificationEmail`。
* **文件:** `frontend/src/views/auth/LoginView.vue`
    * [ ] **TODO:** 实现登录表单及交互。
* **文件:** `frontend/src/views/auth/RegisterView.vue`
    * [ ] **TODO:** 实现注册表单及交互。
* **文件:** `frontend/src/views/user/ProfileView.vue`
    * [ ] **TODO:** 显示用户个人信息，跳转编辑页面。
* **文件:** `frontend/src/views/user/ProfileEditView.vue`
    * [ ] **TODO:** 实现个人信息编辑表单及头像上传。

---

## 7. 其他待办事项

*   [ ] **TODO:** 完成 `sql_scripts/TODO.md` 中剩余的数据库层待办事项。
*   [ ] **TODO:** 完成商品、评价、交易、消息与退货、通知与举报模块的 DAL、Service 和 API 实现。
*   [ ] **TODO:** 为所有 Service 和 API 方法编写单元测试。
*   [ ] **TODO:** 实现文件上传服务。
*   [ ] **TODO:** 实现邮件发送服务。
*   [ ] **TODO:** 实现 WebSocket 实时通讯。
*   [ ] **TODO:** 实现管理员后台界面。
*   [ ] **TODO:** 编写前后端集成文档。
*   [ ] **TODO:** 完善部署指南和 API 文档。

---

### **如何使用这个 TODO 文档：**

1.  **初始填充:** 团队领导或架构师最初填充好所有已知任务、文件路径和预期的层级职责。
2.  **团队认领:** 团队成员根据分配的模块或技能特长，在相应任务后添加自己的姓名/缩写，表示认领。
3.  **每日更新:** 每位开发者在完成任务、开始新任务或遇到阻塞时，更新对应的 TODO 项状态（`[ ]` 到 `[x] DONE:`，或者 `[!] OPTIONAL:`，`[#] PENDING:`）。
4.  **定期评审:** 在每周的项目会议中，团队可以过一遍这个文档，了解整体进度，讨论阻塞点，并重新分配任务。
5.  **Git 版本控制:** 将这个 `TODO.md` 文件纳入 Git 版本控制，确保所有成员都在同一个最新版本上工作。每次更新后提交。

这种详细的 TODO 文档结构，将为你们的"思源淘"项目提供卓越的可见性和协作效率。祝你们项目顺利！ 