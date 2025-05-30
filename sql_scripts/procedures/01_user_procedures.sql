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
        IsSuperAdmin AS 是否超级管理员,
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
        IsSuperAdmin,
        IsVerified,
        Email
    FROM [User]
    WHERE UserName = @username;
END;
GO

-- 创建新用户 (修改为只接收用户名、密码哈希、手机号、可选专业)
DROP PROCEDURE IF EXISTS [sp_CreateUser];
GO
CREATE PROCEDURE [sp_CreateUser]
    @username NVARCHAR(128),
    @passwordHash NVARCHAR(128),
    @phoneNumber NVARCHAR(20), -- 添加手机号参数 (必填)
    @major NVARCHAR(100) = NULL -- 添加major参数 (可选，带默认值NULL)
AS
BEGIN
    SET NOCOUNT ON;
    -- SET XACT_ABORT ON; -- 遇到错误自动回滚

    -- 声明变量用于存储检查结果和新用户ID
    DECLARE @existingUserCount INT;
    DECLARE @existingPhoneCount INT; -- 添加手机号存在检查变量
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

        -- 检查手机号码是否存在 (手机号码也需要唯一)
        SELECT @existingPhoneCount = COUNT(1) FROM [User] WHERE PhoneNumber = @phoneNumber;
        IF @existingPhoneCount > 0
        BEGIN
            RAISERROR('手机号码已存在', 16, 1);
            -- 跳出事务并返回
            IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
            RETURN;
        END

        -- 检查邮箱是否存在 -- 移除此检查
        -- SELECT @existingEmailCount = COUNT(1) FROM [User] WHERE Email = @email;
        -- IF @existingEmailCount > 0
        -- BEGIN
        --     RAISERROR('邮箱已存在', 16, 1);
        --     IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
        --     RETURN;
        -- END

        -- 插入新用户数据
        INSERT INTO [User] (UserID, UserName, Password, Email, Status, Credit, IsStaff, IsVerified, Major, AvatarUrl, Bio, PhoneNumber, JoinTime)
        VALUES (@newUserId, @username, @passwordHash, NULL, 'Active', 100, 0, 0, @major, NULL, NULL, @phoneNumber, GETDATE()); -- Email 设置为 NULL

        -- 提交事务
        COMMIT TRANSACTION;

        -- 返回新用户的 UserID
        SELECT @newUserId AS NewUserID, '用户创建成功并查询成功' AS Message; -- 返回新用户ID和成功消息

    END TRY
    BEGIN CATCH
        -- 捕获错误，回滚事务
        IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;

        -- 重新抛出错误
        THROW;

        SELECT ERROR_MESSAGE() AS ErrorMsg;
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
    @phoneNumber NVARCHAR(20) = NULL,
    @email NVARCHAR(254) = NULL -- Add optional email parameter
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @existingUserCount INT;
    DECLARE @existingPhoneCount INT;
    DECLARE @existingEmailCount INT; -- Add email existence check variable

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

    -- 如果提供了邮箱地址，检查邮箱地址是否已被其他用户使用
    IF @email IS NOT NULL AND LTRIM(RTRIM(@email)) <> ''
    BEGIN
        SELECT @existingEmailCount = COUNT(1) FROM [User] WHERE Email = @email AND UserID <> @userId;
        IF @existingEmailCount > 0
        BEGIN
            RAISERROR('此邮箱已被其他用户使用。', 16, 1);
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
            PhoneNumber = ISNULL(@phoneNumber, PhoneNumber),
            Email = ISNULL(@email, Email) -- Update email if provided
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
-- 输入: @email NVARCHAR(254), @userId UNIQUEIDENTIFIER = NULL
-- 输出: 魔术链接令牌 (VerificationToken) 和用户ID (UserID)
DROP PROCEDURE IF EXISTS [sp_RequestMagicLink];
GO
CREATE PROCEDURE [sp_RequestMagicLink]
    @email NVARCHAR(254),
    @userId UNIQUEIDENTIFIER = NULL -- Add optional userId parameter
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @targetUserId UNIQUEIDENTIFIER; -- Use a variable for the user ID we are operating on
    DECLARE @isNewUser BIT = 0;
    DECLARE @token UNIQUEIDENTIFIER = NEWID(); -- 生成新的魔术链接令牌
    -- 令牌有效期设置为 15 分钟，与 settings.MAGIC_LINK_EXPIRE_MINUTES 一致
    DECLARE @tokenExpireTime DATETIME = DATEADD(minute, 15, GETDATE()); 
    DECLARE @userStatus NVARCHAR(20);
    DECLARE @foundByEmailUserId UNIQUEIDENTIFIER; -- To store user ID found by email

    BEGIN TRY
        BEGIN TRANSACTION;

        -- Step 1: Try to find the user by provided @userId if it's not NULL (for logged-in users)
        IF @userId IS NOT NULL
        BEGIN
            SELECT @targetUserId = UserID, @userStatus = Status
            FROM [User]
            WHERE UserID = @userId;

            IF @targetUserId IS NOT NULL
            BEGIN
                 -- User found by provided @userId
                 SET @isNewUser = 0;
            END
            -- Else: User not found by provided @userId, proceed to find/create by email
        END

        -- Step 2: If user not found by @userId, try to find by @email or create new user
        IF @targetUserId IS NULL
        BEGIN
            -- Find user by email (SQL语句1)
            SELECT @foundByEmailUserId = UserID, @userStatus = Status
            FROM [User]
            WHERE Email = @email;

            IF @foundByEmailUserId IS NULL -- New user based on email
            BEGIN
                SET @targetUserId = NEWID(); -- 生成新的用户ID
                SET @isNewUser = 1;
                -- 插入新用户 (SQL语句2)
                INSERT INTO [User] (UserID, UserName, Password, Email, IsVerified, Status, Credit, IsStaff, JoinTime, VerificationToken, TokenExpireTime)
                -- 用户名可以使用邮箱的一部分或随机生成，Password 可以先设为NULL或随机值
                VALUES (@targetUserId, 'user_' + CAST(@targetUserId AS NVARCHAR(36)), CAST(NEWID() AS NVARCHAR(128)), @email, 0, 'Active', 100, 0, GETDATE(), @token, @tokenExpireTime);
            END
            ELSE -- Existing user found by email
            BEGIN
                SET @targetUserId = @foundByEmailUserId;
                SET @isNewUser = 0;
                -- Check if the user found by email is disabled
                 IF @userStatus = 'Disabled'
                 BEGIN
                     RAISERROR('您的账户已被禁用，无法验证邮箱。', 16, 1); -- More specific error message
                     IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
                     RETURN;
                 END
                 -- Update magic link token and expiry time for the user found by email (SQL语句2)
                 UPDATE [User]
                 SET VerificationToken = @token, TokenExpireTime = @tokenExpireTime
                 WHERE UserID = @targetUserId;
            END
        END
        ELSE -- User was found by provided @userId, now update their token
        BEGIN
            -- Check if the user found by @userId is disabled
             IF @userStatus = 'Disabled'
             BEGIN
                 RAISERROR('您的账户已被禁用，无法验证邮箱。', 16, 1); -- More specific error message
                 IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
                 RETURN;
             END
             -- Update magic link token and expiry time for the user found by @userId (SQL语句2)
             UPDATE [User]
             SET VerificationToken = @token, TokenExpireTime = @tokenExpireTime
             WHERE UserID = @targetUserId;

             -- Optional: If email is different from the one stored for this user ID, update it?
             -- This depends on whether we allow changing email via this process. Assuming for now we do NOT
             -- or that the Service layer ensures the email is updated before calling this SP with userId.
             -- UPDATE [User] SET Email = @email WHERE UserID = @targetUserId AND Email IS NULL OR Email <> @email; -- Example update
        END

        COMMIT TRANSACTION;

        -- 返回生成的信息 (SQL语句3)
        SELECT @token AS VerificationToken, @targetUserId AS UserID, @isNewUser AS IsNewUser;

    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0
            ROLLBACK TRANSACTION;
        THROW; -- 重新抛出捕获的错误
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

-- 新增：删除用户
DROP PROCEDURE IF EXISTS [sp_DeleteUser];
GO
CREATE PROCEDURE [sp_DeleteUser]
    @userId UNIQUEIDENTIFIER
AS
BEGIN
    SET NOCOUNT ON;
    -- SET XACT_ABORT ON; -- 暂时也注释掉 XACT_ABORT，以排除其可能的早期中断效应

    DECLARE @InputUserID_Str VARCHAR(36) = CONVERT(VARCHAR(36), @userId);
    DECLARE @FoundUsername NVARCHAR(128) = NULL;
    DECLARE @UserCount INT = -100; -- 初始化为一个特殊值，表示尚未执行查询
    DECLARE @OperationResultCode INT = -999; -- 新增：用于最终操作结果，区别于过程中的ResultCode
    DECLARE @DebugMessage NVARCHAR(500) = N'Debug process started.';

    BEGIN TRY
        -- 直接在 User 表中查询用户数量和用户名
        SELECT @UserCount = COUNT(*), @FoundUsername = MAX(Username) 
        FROM [User] 
        WHERE UserID = @userId;
        
        SET @DebugMessage = N'After COUNT query. UserCount: ' + ISNULL(CAST(@UserCount AS NVARCHAR), 'NULL') + N'. FoundUsername: ' + ISNULL(@FoundUsername, N'NULL_OR_NOT_FOUND');

    END TRY
    BEGIN CATCH
        SET @UserCount = -99; -- 特殊值表示在尝试COUNT时发生错误
        SET @FoundUsername = N'ERROR_READING_USERNAME_DURING_COUNT';
        SET @DebugMessage = N'ERROR during user count/select: Error ' + CAST(ERROR_NUMBER() AS VARCHAR(10)) + N' - ' + ERROR_MESSAGE();
        SET @OperationResultCode = -90; -- 表示在检查用户时发生错误
        -- 直接输出结果并返回，不再继续执行删除
        SELECT 
            @InputUserID_Str AS Debug_InputUserID,
            @UserCount AS Debug_UserCount,
            @FoundUsername AS Debug_FoundUsername,
            @DebugMessage AS Debug_Message,
            @OperationResultCode AS OperationResultCode;
        RETURN;
    END CATCH

    -- 检查用户是否存在，并决定是否继续
    IF @UserCount = 1
    BEGIN
        SET @DebugMessage = @DebugMessage + N' | User found.';
        -- 检查依赖关系 (暂时简化或注释掉大部分，专注于删除逻辑本身)
        IF EXISTS (SELECT 1 FROM [Product] WHERE OwnerID = @userId AND Status NOT IN ('Sold', 'Cancelled')) OR
           EXISTS (SELECT 1 FROM [Order] WHERE (BuyerID = @userId OR SellerID = @userId) AND Status NOT IN ('Completed', 'Cancelled', 'Refunded')) OR
        --    EXISTS (SELECT 1 FROM [Evaluation] WHERE BuyerID = @userId OR SellerID = @userId) OR
        --    EXISTS (SELECT 1 FROM [Report] WHERE ReporterUserID = @userId OR ReportedUserID = @userId) OR
        --    EXISTS (SELECT 1 FROM [Favorite] WHERE UserID = @userId) OR
        --    EXISTS (SELECT 1 FROM [StudentAuthentication] WHERE UserID = @userId AND Status = 'Verified') OR
           EXISTS (
                SELECT 1 FROM [ChatMessage] CM
                WHERE ((CM.SenderID = @userId AND CM.SenderVisible = 1) OR (CM.ReceiverID = @userId AND CM.ReceiverVisible = 1))
                AND CM.SendTime > DATEADD(month, -3, GETDATE())
           ) OR
        --    EXISTS (SELECT 1 FROM [SystemNotification] WHERE UserID = @userId AND IsRead = 0) OR -- 假设未读系统通知不阻止删除
           EXISTS (SELECT 1 FROM [Order] WHERE BuyerID = @userId OR SellerID = @userId AND Status NOT IN ('Completed', 'Cancelled'))

        BEGIN
            SET @DebugMessage = @DebugMessage + N' | Dependency check failed. Cannot delete user.';
            SET @OperationResultCode = -2; -- 表示存在依赖，无法删除
        END
        ELSE
        BEGIN
            BEGIN TRY
                BEGIN TRANSACTION;
                SET @DebugMessage = @DebugMessage + N' | No critical dependencies found. Proceeding with deletion.';

                -- 执行删除操作 (示例, 从 User 表删除)
                -- 实际应用中需要按正确的顺序删除相关表的数据
                -- DELETE FROM [StudentAuthentication] WHERE UserID = @userId;
                -- DELETE FROM [Favorite] WHERE UserID = @userId;
                -- DELETE FROM [Report] WHERE ReporterUserID = @userId OR ReportedUserID = @userId;
                -- DELETE FROM [Evaluation] WHERE BuyerID = @userId OR SellerID = @userId;
                -- DELETE FROM [ChatMessage] WHERE SenderID = @userId OR ReceiverID = @userId; -- 或者仅标记为不可见
                -- DELETE FROM [Order] WHERE BuyerID = @userId OR SellerID = @userId; -- 通常订单不直接删除，而是标记
                -- DELETE FROM [Product] WHERE OwnerID = @userId; -- 通常商品不直接删除
                -- DELETE FROM [Transaction] WHERE BuyerID = @userId OR SellerID = @userId;
                -- DELETE FROM [SystemNotification] WHERE UserID = @userId;
                -- 最后删除用户表自身
                DELETE FROM [User] WHERE UserID = @userId;

                IF @@ROWCOUNT = 1
                BEGIN
                    SET @DebugMessage = @DebugMessage + N' | User successfully deleted from User table.';
                    SET @OperationResultCode = 0; -- 成功删除
                    IF @@TRANCOUNT > 0 COMMIT TRANSACTION;
                END
                ELSE
                BEGIN
                    SET @DebugMessage = @DebugMessage + N' | User was found initially, but @@ROWCOUNT after DELETE was 0. Possible race condition or other issue.';
                    SET @OperationResultCode = -3; -- 删除时未找到或未成功删除
                    IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
                END
            END TRY
            BEGIN CATCH
                SET @DebugMessage = @DebugMessage + N' | ERROR during delete transaction: ' + ERROR_MESSAGE();
                SET @OperationResultCode = -4; -- 删除过程中发生数据库错误
                IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
            END CATCH
        END
    END
    ELSE
    BEGIN
        SET @DebugMessage = @DebugMessage + N' | User not found (UserCount != 1).';
        SET @OperationResultCode = -1; -- 用户未找到
    END

    -- 最终返回单一结果集
    SELECT 
        @InputUserID_Str AS Debug_InputUserID,
        @UserCount AS Debug_UserCount,
        @FoundUsername AS Debug_FoundUsername,
        @DebugMessage AS Debug_Message,
        @OperationResultCode AS OperationResultCode; -- 最终的操作结果代码

    -- 不再需要单独的 SELECT @ResultCode AS ResultCode;

END;
GO