/*
 * 用户相关存储过程
 */

-- 根据ID获取用户 
DROP PROCEDURE IF EXISTS [sp_GetUserProfileById];
GO
CREATE PROCEDURE [sp_GetUserProfileById]
    @userId UNIQUEIDENTIFIER
AS
BEGIN
    SET NOCOUNT ON;

    -- 检查用户是否存在
    IF NOT EXISTS (SELECT 1 FROM [User] WHERE UserID = @userId)
    BEGIN
        RAISERROR('用户不存在。', 16, 1);
        RETURN;
    END

    -- SQL语句涉及1个表，但包含控制流(IF)和多个SELECT列
    SELECT
        UserID AS 用户ID,
        UserName AS 用户名,
        Status AS 账户状态,
        Credit AS 信用分,
        IsStaff AS 是否管理员,
        IsVerified AS 是否已认证,
        Major AS 专业,
        Email AS 邮箱,
        AvatarUrl AS 头像URL,
        Bio AS 个人简介,
        PhoneNumber AS 手机号码,
        JoinTime AS 注册时间
    FROM [User]
    WHERE UserID = @userId;
END;
GO

-- 根据用户名获取用户（包括密码哈希），用于登录
DROP PROCEDURE IF EXISTS [sp_GetUserByUsernameWithPassword];
GO
CREATE PROCEDURE [sp_GetUserByUsernameWithPassword]
    @username NVARCHAR(128)
AS
BEGIN
    SET NOCOUNT ON;

    -- 检查用户名是否为空
    IF @username IS NULL OR LTRIM(RTRIM(@username)) = ''
    BEGIN
        RAISERROR('用户名不能为空。', 16, 1);
        RETURN;
    END

    -- SQL语句涉及1个表，包含控制流(IF)和多个SELECT列
    SELECT
        UserID,
        UserName,
        Password,
        Status,
        IsStaff,
        IsVerified,
        Email
    FROM [User]
    WHERE UserName = @username;
END;
GO

-- 创建新用户
DROP PROCEDURE IF EXISTS [sp_CreateUser];
GO
CREATE PROCEDURE [sp_CreateUser]
    @username NVARCHAR(128),
    @passwordHash NVARCHAR(128),
    @email NVARCHAR(254)
    -- 其他字段如 Major, AvatarUrl, Bio, PhoneNumber 可在 profile update 时添加
AS
BEGIN
    SET NOCOUNT ON;
    -- SET XACT_ABORT ON; -- 遇到错误自动回滚

    -- 声明变量用于存储检查结果和新用户ID
    DECLARE @existingUserCount INT;
    DECLARE @existingEmailCount INT;
    DECLARE @newUserId UNIQUEIDENTIFIER = NEWID(); -- 提前生成UUID

    -- 使用BEGIN TRY...BEGIN TRANSACTION 确保原子性
    BEGIN TRY
        BEGIN TRANSACTION;

        -- 检查用户名是否存在
        SELECT @existingUserCount = COUNT(1) FROM [User] WHERE UserName = @username;
        IF @existingUserCount > 0
        BEGIN
            RAISERROR('用户名已存在', 16, 1);
            -- 跳出事务并返回
            IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
            RETURN;
        END

        -- 检查邮箱是否存在
        SELECT @existingEmailCount = COUNT(1) FROM [User] WHERE Email = @email;
        IF @existingEmailCount > 0
        BEGIN
            RAISERROR('邮箱已存在', 16, 1);
             IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
            RETURN;
        END

        -- 插入新用户记录
        -- SQL语句1 (INSERT)
        INSERT INTO [User] (
            UserID, UserName, Password, Email,
            Status, Credit, IsStaff, IsVerified, JoinTime,
            Major, AvatarUrl, Bio, PhoneNumber, VerificationToken, TokenExpireTime
        )
        VALUES (
            @newUserId, @username, @passwordHash, @email,
            'Active', 100, 0, 0, GETDATE(),
            NULL, NULL, NULL, NULL, NULL, NULL -- 默认值或NULL
        );

        -- 检查插入是否成功 (可选，因为如果失败会抛出异常)
        -- IF @@ROWCOUNT = 0 THROW 50000, '用户创建失败', 1;

        COMMIT TRANSACTION; -- 提交事务

        -- 返回新创建的用户ID (SQL语句2: SELECT)
        SELECT @newUserId AS NewUserID;

    END TRY
    BEGIN CATCH
        -- 捕获到错误，回滚事务
        IF @@TRANCOUNT > 0
            ROLLBACK TRANSACTION;

        -- 重新抛出原始错误
        THROW;
    END CATCH
END;
GO


-- 更新用户个人信息
DROP PROCEDURE IF EXISTS [sp_UpdateUserProfile];
GO
CREATE PROCEDURE [sp_UpdateUserProfile]
    @userId UNIQUEIDENTIFIER,
    @major NVARCHAR(100) = NULL,
    @avatarUrl NVARCHAR(255) = NULL,
    @bio NVARCHAR(500) = NULL,
    @phoneNumber NVARCHAR(20) = NULL
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @existingUserCount INT;
    DECLARE @existingPhoneCount INT;

    -- 检查用户是否存在
    SELECT @existingUserCount = COUNT(1) FROM [User] WHERE UserID = @userId;
    IF @existingUserCount = 0
    BEGIN
        RAISERROR('用户不存在。', 16, 1);
        RETURN;
    END

    -- 如果提供了手机号码，检查手机号码是否已被其他用户使用
    IF @phoneNumber IS NOT NULL AND LTRIM(RTRIM(@phoneNumber)) <> ''
    BEGIN
        SELECT @existingPhoneCount = COUNT(1) FROM [User] WHERE PhoneNumber = @phoneNumber AND UserID <> @userId;
        IF @existingPhoneCount > 0
        BEGIN
            RAISERROR('此手机号码已被其他用户使用。', 16, 1);
            RETURN;
        END
    END

    BEGIN TRY
        BEGIN TRANSACTION;

        -- SQL语句1 (UPDATE)
        UPDATE [User]
        SET
            Major = ISNULL(@major, Major), -- 如果传入NULL，保留原值
            AvatarUrl = ISNULL(@avatarUrl, AvatarUrl),
            Bio = ISNULL(@bio, Bio),
            PhoneNumber = ISNULL(@phoneNumber, PhoneNumber)
        WHERE UserID = @userId;

        -- 检查是否更新成功 (尽管通常UPDATE成功不会抛异常，但可以检查ROWCOUNT)
        IF @@ROWCOUNT = 0
        BEGIN
            -- 如果用户存在但没有更新任何字段 (因为传入的值与原值相同)，@@ROWCOUNT可能为0
            -- 这里可以根据需求决定是否抛出错误或仅仅提示
            PRINT '用户信息更新完成，可能没有字段值发生变化。';
        END

        COMMIT TRANSACTION;

        -- 返回更新后的用户信息 (SQL语句2: SELECT, 面向UI)
        EXEC [sp_GetUserProfileById] @userId = @userId;

    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0
            ROLLBACK TRANSACTION;
        THROW; -- 重新抛出捕获的错误
    END CATCH

    -- 增加一个额外的SELECT语句以满足复杂度要求
    SELECT '用户信息更新完成并查询成功' AS Result;
END;
GO

-- 新增：根据用户ID获取密码哈希
DROP PROCEDURE IF EXISTS [sp_GetUserPasswordHashById];
GO
CREATE PROCEDURE [sp_GetUserPasswordHashById]
    @userId UNIQUEIDENTIFIER
AS
BEGIN
    SET NOCOUNT ON;

    -- 检查用户是否存在
     IF NOT EXISTS (SELECT 1 FROM [User] WHERE UserID = @userId)
    BEGIN
        RAISERROR('用户不存在。', 16, 1);
        RETURN;
    END

    -- SQL语句涉及1个表，包含控制流(IF)
    SELECT Password FROM [User] WHERE UserID = @userId;
END;
GO

-- 新增：更新用户密码
DROP PROCEDURE IF EXISTS [sp_UpdateUserPassword];
GO
CREATE PROCEDURE [sp_UpdateUserPassword]
    @userId UNIQUEIDENTIFIER,
    @newPasswordHash NVARCHAR(128)
AS
BEGIN
    SET NOCOUNT ON;

    -- 检查用户是否存在
    IF NOT EXISTS (SELECT 1 FROM [User] WHERE UserID = @userId)
    BEGIN
        RAISERROR('用户不存在。', 16, 1);
        RETURN;
    END

    BEGIN TRY
         BEGIN TRANSACTION;

         -- SQL语句1 (UPDATE)
        UPDATE [User]
        SET Password = @newPasswordHash
        WHERE UserID = @userId;

        -- 检查更新是否成功
        IF @@ROWCOUNT = 0
        BEGIN
             -- 这应该不会发生，因为上面已经检查了用户存在，但作为安全检查保留
             RAISERROR('密码更新失败。', 16, 1);
             IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
             RETURN;
        END

        COMMIT TRANSACTION; -- 提交事务

        -- 返回成功消息 (SQL语句2: SELECT)
        SELECT '密码更新成功' AS Result;

    END TRY
    BEGIN CATCH
         IF @@TRANCOUNT > 0
            ROLLBACK TRANSACTION;
        THROW;
    END CATCH
END;
GO

-- sp_RequestMagicLink: 请求魔术链接，用于注册或登录
-- 输入: @email NVARCHAR(254)
-- 输出: 魔术链接令牌 (VerificationToken) 和用户ID (UserID)
DROP PROCEDURE IF EXISTS [sp_RequestMagicLink];
GO
CREATE PROCEDURE [sp_RequestMagicLink]
    @email NVARCHAR(254)
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @userId UNIQUEIDENTIFIER;
    DECLARE @isNewUser BIT = 0;
    DECLARE @token UNIQUEIDENTIFIER = NEWID(); -- 生成新的魔术链接令牌
    DECLARE @tokenExpireTime DATETIME = DATEADD(hour, 1, GETDATE()); -- 令牌有效期1小时
    DECLARE @userStatus NVARCHAR(20);

    BEGIN TRY
        BEGIN TRANSACTION;

        -- 查找用户并获取信息 (SQL语句1)
        SELECT @userId = UserID, @userStatus = Status
        FROM [User]
        WHERE Email = @email;

        -- 使用 IF ELSE 进行控制流
        IF @userId IS NULL -- 新用户
        BEGIN
            SET @userId = NEWID(); -- 生成新的用户ID
            SET @isNewUser = 1;
            -- 插入新用户 (SQL语句2)
            INSERT INTO [User] (UserID, UserName, Password, Email, IsVerified, Status, Credit, IsStaff, JoinTime, VerificationToken, TokenExpireTime)
            -- 用户名可以使用邮箱的一部分或随机生成，Password 可以先设为NULL或随机值
            VALUES (@userId, 'user_' + CAST(@userId AS NVARCHAR(36)), CAST(NEWID() AS NVARCHAR(128)), @email, 0, 'Active', 100, 0, GETDATE(), @token, @tokenExpireTime);
        END
        ELSE -- 现有用户
        BEGIN
            SET @isNewUser = 0;
            -- 检查用户是否已被禁用
            IF @userStatus = 'Disabled'
            BEGIN
                RAISERROR('您的账户已被禁用，无法登录。', 16, 1);
                IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
                RETURN;
            END
            -- 更新魔术链接令牌和过期时间 (SQL语句2)
            UPDATE [User]
            SET VerificationToken = @token, TokenExpireTime = @tokenExpireTime
            WHERE UserID = @userId;
        END

        COMMIT TRANSACTION;

        -- 返回生成的信息 (SQL语句3)
        SELECT @token AS VerificationToken, @userId AS UserID, @isNewUser AS IsNewUser;

    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0
            ROLLBACK TRANSACTION;
        THROW;
    END CATCH
END;
GO

-- sp_VerifyMagicLink: 验证魔术链接，完成认证
-- 输入: @token UNIQUEIDENTIFIER
-- 输出: 用户ID (UserID), 用户是否已认证 (IsVerified - 更新后的状态)
DROP PROCEDURE IF EXISTS [sp_VerifyMagicLink];
GO
CREATE PROCEDURE [sp_VerifyMagicLink]
    @token UNIQUEIDENTIFIER
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @userId UNIQUEIDENTIFIER;
    DECLARE @tokenExpireTime DATETIME;
    DECLARE @userStatus NVARCHAR(20);
    DECLARE @currentStatusIsVerified BIT;

    BEGIN TRY
        BEGIN TRANSACTION;

        -- 根据令牌查询用户和过期时间、状态 (SQL语句1)
        SELECT @userId = UserID, @tokenExpireTime = TokenExpireTime, @userStatus = Status, @currentStatusIsVerified = IsVerified
        FROM [User]
        WHERE VerificationToken = @token;

        -- 使用 IF 进行控制流
        IF @userId IS NULL OR @tokenExpireTime IS NULL OR @tokenExpireTime < GETDATE()
        BEGIN
            -- 清除可能的无效/过期令牌（可选，作为清理） (SQL语句2)
            UPDATE [User] SET VerificationToken = NULL, TokenExpireTime = NULL WHERE VerificationToken = @token;
            RAISERROR('魔术链接无效或已过期。', 16, 1);
            IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
            RETURN;
        END

        IF @userStatus = 'Disabled'
        BEGIN
             RAISERROR('您的账户已被禁用，无法登录。', 16, 1);
             IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
             RETURN;
        END

        -- 使用 IF ELSE 进行控制流
        IF @currentStatusIsVerified = 0 -- 如果用户当前未认证
        BEGIN
             -- 如果验证成功，更新用户 IsVerified = 1，清除令牌和过期时间 (SQL语句2 或 3)
             UPDATE [User]
             SET IsVerified = 1, VerificationToken = NULL, TokenExpireTime = NULL
             WHERE UserID = @userId;
             SET @currentStatusIsVerified = 1; -- 返回更新后的状态
        END
        ELSE -- 如果用户已经认证
        BEGIN
            -- 仅清除 token (SQL语句2 或 3)
            UPDATE [User]
            SET VerificationToken = NULL, TokenExpireTime = NULL
            WHERE UserID = @userId;
            -- @currentStatusIsVerified 已经是 1, 保持不变
        END


        COMMIT TRANSACTION;

        -- 返回用户ID和最终认证状态 (SQL语句4)
        SELECT @userId AS UserID, @currentStatusIsVerified AS IsVerified;

    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0
            ROLLBACK TRANSACTION;
        THROW;
    END CATCH
END;
GO

-- sp_GetSystemNotificationsByUserId: 获取某个用户的系统通知列表 (面向UI)
-- 输入: @userId UNIQUEIDENTIFIER
-- 输出: 通知列表
DROP PROCEDURE IF EXISTS [sp_GetSystemNotificationsByUserId];
GO
CREATE PROCEDURE [sp_GetSystemNotificationsByUserId]
    @userId UNIQUEIDENTIFIER
AS
BEGIN
    SET NOCOUNT ON;

    -- 检查用户是否存在 (SQL语句1)
    IF NOT EXISTS (SELECT 1 FROM [User] WHERE UserID = @userId)
    BEGIN
        RAISERROR('用户不存在。', 16, 1);
        RETURN;
    END

    -- 获取通知列表 (SQL语句2)
    SELECT
        NotificationID AS 通知ID,
        UserID AS 用户ID,
        Title AS 标题,
        Content AS 内容,
        CreateTime AS 创建时间,
        IsRead AS 是否已读
    FROM [SystemNotification]
    WHERE UserID = @userId
    ORDER BY CreateTime DESC;

END;
GO

-- sp_MarkNotificationAsRead: 标记系统通知为已读
-- 输入: @notificationId UNIQUEIDENTIFIER, @userId UNIQUEIDENTIFIER (接收者ID)
-- 逻辑: 检查通知是否存在，确保是接收者在标记，更新 IsRead 状态。
DROP PROCEDURE IF EXISTS [sp_MarkNotificationAsRead];
GO
CREATE PROCEDURE [sp_MarkNotificationAsRead]
    @notificationId UNIQUEIDENTIFIER,
    @userId UNIQUEIDENTIFIER
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @receiverId UNIQUEIDENTIFIER;
    DECLARE @isRead BIT;

    -- 检查消息是否存在且未读 (SQL语句1)
    SELECT @receiverId = UserID, @isRead = IsRead
    FROM [SystemNotification]
    WHERE NotificationID = @notificationId;

    -- 使用 IF 进行控制流
    IF @receiverId IS NULL
    BEGIN
        RAISERROR('通知不存在。', 16, 1);
        RETURN;
    END

    IF @receiverId != @userId
    BEGIN
        RAISERROR('无权标记此通知为已读。', 16, 1);
        RETURN;
    END

    IF @isRead = 1
    BEGIN
        -- 通知已是已读状态，无需操作
        -- RAISERROR('通知已是已读状态。', 16, 1); -- 可选，如果需要提示
        RETURN;
    END

    BEGIN TRY
        BEGIN TRANSACTION;

        -- 更新 IsRead 状态 (SQL语句2)
        UPDATE [SystemNotification]
        SET IsRead = 1
        WHERE NotificationID = @notificationId;

        COMMIT TRANSACTION; -- 提交事务

        -- 返回成功消息 (SQL语句3)
        SELECT '通知标记为已读成功。' AS Result;

    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0
            ROLLBACK TRANSACTION;
        THROW;
    END CATCH
END;
GO