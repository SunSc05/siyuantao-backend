-- sp_CreateReport: 用户提交举报
-- 输入: @reporterUserId UNIQUEIDENTIFIER (举报者用户ID), @reportedUserId UNIQUEIDENTIFIER (被举报用户ID, 可选), @reportedProductId UNIQUEIDENTIFIER (被举报商品ID, 可选), @reportedOrderId UNIQUEIDENTIFIER (被举报订单ID, 可选), @reportContent NVARCHAR(500) (举报内容)
-- 逻辑: 验证举报者存在性，验证举报内容非空，验证被举报对象存在性（可选），插入举报记录
DROP PROCEDURE IF EXISTS [sp_CreateReport];
GO
CREATE PROCEDURE [sp_CreateReport]
    @reporterUserId UNIQUEIDENTIFIER,
    @reportedUserId UNIQUEIDENTIFIER = NULL,
    @reportedProductId UNIQUEIDENTIFIER = NULL,
    @reportedOrderId UNIQUEIDENTIFIER = NULL,
    @reportContent NVARCHAR(500)
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON; -- 错误时自动回滚事务

    -- 1. 验证举报者存在性
    IF NOT EXISTS (SELECT 1 FROM [User] WHERE UserID = @reporterUserId)
    BEGIN
        RAISERROR('举报者用户不存在。', 16, 1);
        RETURN;
    END

    -- 2. 验证举报内容非空
    IF @reportContent IS NULL OR LTRIM(RTRIM(@reportContent)) = ''
    BEGIN
        RAISERROR('举报内容不能为空。', 16, 1);
        RETURN;
    END

    -- 3. 验证被举报对象存在性（可选参数校验）
    IF @reportedUserId IS NOT NULL AND NOT EXISTS (SELECT 1 FROM [User] WHERE UserID = @reportedUserId)
    BEGIN
        RAISERROR('被举报用户不存在。', 16, 1);
        RETURN;
    END
    IF @reportedProductId IS NOT NULL AND NOT EXISTS (SELECT 1 FROM [Product] WHERE ProductID = @reportedProductId)
    BEGIN
        RAISERROR('被举报商品不存在。', 16, 1);
        RETURN;
    END
    IF @reportedOrderId IS NOT NULL AND NOT EXISTS (SELECT 1 FROM [Order] WHERE OrderID = @reportedOrderId)
    BEGIN
        RAISERROR('被举报订单不存在。', 16, 1);
        RETURN;
    END

    BEGIN TRY
        BEGIN TRANSACTION;

        -- 4. 插入举报记录
        INSERT INTO [Report] (
            ReportID,
            ReporterUserID,
            ReportedUserID,
            ReportedProductID,
            ReportedOrderID,
            ReportContent,
            ReportTime,
            ProcessingStatus
        )
        VALUES (
            NEWID(),
            @reporterUserId,
            @reportedUserId,
            @reportedProductId,
            @reportedOrderId,
            @reportContent,
            GETDATE(),
            'Pending' -- 默认待处理状态
        );

        COMMIT TRANSACTION;

        -- 返回成功信息
        SELECT '举报提交成功。' AS Result, SCOPE_IDENTITY() AS NewReportID;

    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
        THROW; -- 重新抛出错误信息供上层捕获
    END CATCH
END;
GO


-- sp_GetReportList: 管理员获取举报列表（支持状态筛选和分页）
-- 输入: @status NVARCHAR(20) = NULL (举报状态, 可选值: 'Pending', 'Resolved', 'Rejected'), @pageNumber INT (页码), @pageSize INT (每页数量)
-- 输出: 举报列表（包含总记录数）
DROP PROCEDURE IF EXISTS [sp_GetReportList];
GO
CREATE PROCEDURE [sp_GetReportList]
    @status NVARCHAR(20) = NULL,
    @pageNumber INT,
    @pageSize INT
AS
BEGIN
    SET NOCOUNT ON;

    -- 验证分页参数有效性
    IF @pageNumber <= 0 OR @pageSize <= 0
    BEGIN
        RAISERROR('页码和每页数量必须大于0。', 16, 1);
        RETURN;
    END

    -- 验证状态参数有效性（若传入非NULL值）
    IF @status IS NOT NULL AND @status NOT IN ('Pending', 'Resolved', 'Rejected')
    BEGIN
        RAISERROR('无效的举报状态，可选值为：Pending, Resolved, Rejected。', 16, 1);
        RETURN;
    END

    -- 计算总记录数并获取分页数据
    WITH ReportCTE AS (
        SELECT 
            ReportID AS 举报ID,
            ReporterUserID AS 举报者ID,
            ReportedUserID AS 被举报用户ID,
            ReportedProductID AS 被举报商品ID,
            ReportedOrderID AS 被举报订单ID,
            ReportContent AS 举报内容,
            ReportTime AS 举报时间,
            ProcessingStatus AS 处理状态,
            ProcessorAdminID AS 处理管理员ID,
            ProcessingTime AS 处理时间,
            ProcessingResult AS 处理结果,
            COUNT(*) OVER() AS 总记录数
        FROM [Report]
        WHERE 
            (@status IS NULL OR ProcessingStatus = @status) -- 动态筛选状态
        ORDER BY ReportTime DESC -- 按举报时间倒序排列（最新优先）
        OFFSET (@pageNumber - 1) * @pageSize ROWS -- 分页偏移
        FETCH NEXT @pageSize ROWS ONLY -- 取当前页数据
    )
    SELECT * FROM ReportCTE;
END;
GO


-- sp_HandleReport: 管理员处理举报
-- 输入: @reportId UNIQUEIDENTIFIER (举报ID), @adminId UNIQUEIDENTIFIER (处理管理员ID), @newStatus NVARCHAR(20) (新状态: 'Resolved'/'Rejected'), @processingResult NVARCHAR(500) (处理结果描述)
-- 逻辑: 验证管理员权限、举报存在性、状态有效性，更新举报处理信息
DROP PROCEDURE IF EXISTS [sp_HandleReport];
GO
CREATE PROCEDURE [sp_HandleReport]
    @reportId UNIQUEIDENTIFIER,
    @adminId UNIQUEIDENTIFIER,
    @newStatus NVARCHAR(20),
    @processingResult NVARCHAR(500)
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON; -- 错误时自动回滚事务

    DECLARE @currentStatus NVARCHAR(20);

    -- 1. 验证管理员存在且具有权限（IsStaff=1或IsSuperAdmin=1）
    IF NOT EXISTS (
        SELECT 1 FROM [User] 
        WHERE UserID = @adminId 
        AND (IsStaff = 1 OR IsSuperAdmin = 1)
    )
    BEGIN
        RAISERROR('管理员不存在或无权限处理举报。', 16, 1);
        RETURN;
    END

    -- 2. 验证举报存在并获取当前状态
    SELECT @currentStatus = ProcessingStatus 
    FROM [Report] 
    WHERE ReportID = @reportId;

    IF @currentStatus IS NULL
    BEGIN
        RAISERROR('举报不存在。', 16, 1);
        RETURN;
    END

    -- 3. 验证当前状态为待处理（仅允许处理未处理的举报）
    IF @currentStatus <> 'Pending'
    BEGIN
        RAISERROR('举报状态非待处理，无法重复处理。', 16, 1);
        RETURN;
    END

    -- 4. 验证新状态有效性（仅允许更新为Resolved/Rejected）
    IF @newStatus NOT IN ('Resolved', 'Rejected')
    BEGIN
        RAISERROR('无效的处理状态，仅允许"Resolved"或"Rejected"。', 16, 1);
        RETURN;
    END

    -- 5. 验证处理结果非空（若状态为Resolved/Rejected）
    IF @processingResult IS NULL OR LTRIM(RTRIM(@processingResult)) = ''
    BEGIN
        RAISERROR('处理结果描述不能为空。', 16, 1);
        RETURN;
    END

    BEGIN TRY
        BEGIN TRANSACTION;

        -- 6. 更新举报处理信息
        UPDATE [Report]
        SET 
            ProcessingStatus = @newStatus,
            ProcessorAdminID = @adminId,
            ProcessingTime = GETDATE(),
            ProcessingResult = @processingResult
        WHERE ReportID = @reportId;

        COMMIT TRANSACTION;

        -- 返回成功信息
        SELECT '举报处理成功。' AS Result;

    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
        THROW; -- 重新抛出错误供上层捕获
    END CATCH
END;
GO

