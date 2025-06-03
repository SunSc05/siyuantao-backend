/*
 * 通知与举报模块
 */

-- sp_SendSystemNotification: 发送系统通知给指定用户
-- 输入: @userId UNIQUEIDENTIFIER (接收者用户ID), @title NVARCHAR(200) (通知标题), @content NVARCHAR(MAX) (通知内容)
-- 逻辑: 验证用户存在性，插入系统通知记录
DROP PROCEDURE IF EXISTS [sp_SendSystemNotification];
GO
CREATE PROCEDURE [sp_SendSystemNotification]
    @userId UNIQUEIDENTIFIER,
    @title NVARCHAR(200),
    @content NVARCHAR(MAX)
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON; -- 错误时自动回滚事务

    -- 检查用户是否存在
    IF NOT EXISTS (SELECT 1 FROM [User] WHERE UserID = @userId)
    BEGIN
        RAISERROR('目标用户不存在，无法发送通知。', 16, 1);
        RETURN;
    END

    BEGIN TRY
        BEGIN TRANSACTION;

        -- 插入系统通知记录
        INSERT INTO [SystemNotification] (NotificationID, UserID, Title, Content, CreateTime, IsRead)
        VALUES (NEWID(), @userId, @title, @content, GETDATE(), 0);

        COMMIT TRANSACTION;

        -- 返回成功信息
        SELECT '系统通知发送成功。' AS Result;

    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
        THROW; -- 重新抛出错误信息供上层捕获
    END CATCH
END;
GO

-- sp_GetUserNotifications: 获取用户通知列表（支持已读/未读筛选和分页）
-- 输入: @userId UNIQUEIDENTIFIER (用户ID), @isRead BIT = NULL (0=未读, 1=已读, NULL=不筛选), @pageNumber INT (页码), @pageSize INT (每页数量)
-- 输出: 通知列表（包含总记录数）
DROP PROCEDURE IF EXISTS [sp_GetUserNotifications];
GO
CREATE PROCEDURE [sp_GetUserNotifications]
    @userId UNIQUEIDENTIFIER,
    @isRead BIT = NULL,
    @pageNumber INT,
    @pageSize INT
AS
BEGIN
    SET NOCOUNT ON;

    -- 检查用户是否存在
    IF NOT EXISTS (SELECT 1 FROM [User] WHERE UserID = @userId)
    BEGIN
        RAISERROR('用户不存在。', 16, 1);
        RETURN;
    END

    -- 计算总记录数并获取分页数据
    WITH NotificationCTE AS (
        SELECT 
            NotificationID AS 通知ID,
            Title AS 标题,
            Content AS 内容,
            CreateTime AS 创建时间,
            IsRead AS 是否已读,
            COUNT(*) OVER() AS 总记录数
        FROM [SystemNotification]
        WHERE 
            UserID = @userId 
            AND (@isRead IS NULL OR IsRead = @isRead) -- 动态筛选已读状态
        ORDER BY CreateTime DESC -- 按创建时间倒序排列
        OFFSET (@pageNumber - 1) * @pageSize ROWS -- 分页偏移
        FETCH NEXT @pageSize ROWS ONLY -- 取当前页数据
    )
    SELECT * FROM NotificationCTE;
END;
GO

-- sp_MarkNotificationAsRead: 标记系统通知为已读
-- 输入: @notificationId UNIQUEIDENTIFIER (通知ID), @userId UNIQUEIDENTIFIER (接收者用户ID)
-- 逻辑: 检查通知存在且属于用户，更新 IsRead 状态为1
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

    -- 1. 检查通知是否存在并获取接收者ID和当前状态
    SELECT @receiverId = UserID, @isRead = IsRead
    FROM [SystemNotification]
    WHERE NotificationID = @notificationId;

    -- 2. 通知不存在
    IF @receiverId IS NULL
    BEGIN
        RAISERROR('通知不存在。', 16, 1);
        RETURN;
    END

    -- 3. 非接收者无权限标记
    IF @receiverId != @userId
    BEGIN
        RAISERROR('无权标记此通知为已读。', 16, 1);
        RETURN;
    END

    -- 4. 通知已是已读状态
    IF @isRead = 1
    BEGIN
        RETURN; -- 或可选提示 "通知已是已读状态"
    END

    -- 5. 使用事务更新状态
    BEGIN TRY
        BEGIN TRANSACTION;

        UPDATE [SystemNotification]
        SET IsRead = 1
        WHERE NotificationID = @notificationId;

        COMMIT TRANSACTION;

        -- 返回成功信息（可选）
        SELECT '通知标记为已读成功。' AS Result;
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0
            ROLLBACK TRANSACTION;
        THROW; -- 重新抛出错误供上层捕获
    END CATCH
END;
GO

-- sp_DeleteNotification: 用户逻辑删除通知（标记为已删除）
-- 输入: @notificationId UNIQUEIDENTIFIER (通知ID), @userId UNIQUEIDENTIFIER (用户ID)
-- 逻辑: 验证通知存在且属于用户，更新 IsDeleted 状态为1
DROP PROCEDURE IF EXISTS [sp_DeleteNotification];
GO
CREATE PROCEDURE [sp_DeleteNotification]
    @notificationId UNIQUEIDENTIFIER,
    @userId UNIQUEIDENTIFIER
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @receiverId UNIQUEIDENTIFIER;

    -- 1. 检查通知是否存在并获取接收者ID
    SELECT @receiverId = UserID
    FROM [SystemNotification]
    WHERE NotificationID = @notificationId;

    -- 2. 通知不存在
    IF @receiverId IS NULL
    BEGIN
        RAISERROR('通知不存在。', 16, 1);
        RETURN;
    END

    -- 3. 非接收者无权限删除
    IF @receiverId != @userId
    BEGIN
        RAISERROR('无权删除此通知。', 16, 1);
        RETURN;
    END

    -- 4. 检查是否已删除
    IF EXISTS (SELECT 1 FROM [SystemNotification] WHERE NotificationID = @notificationId AND IsDeleted = 1)
    BEGIN
        RETURN; -- 已删除，无需操作
    END

    -- 5. 使用事务更新删除状态
    BEGIN TRY
        BEGIN TRANSACTION;

        UPDATE [SystemNotification]
        SET IsDeleted = 1
        WHERE NotificationID = @notificationId;

        COMMIT TRANSACTION;

        -- 返回成功信息
        SELECT '通知已标记为删除。' AS Result;
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0
            ROLLBACK TRANSACTION;
        THROW; -- 重新抛出错误供上层捕获
    END CATCH
END;
GO

