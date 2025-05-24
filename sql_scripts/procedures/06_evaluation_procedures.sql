/*
 * 评价相关存储过程
 */

-- sp_GetEvaluationsByOrder: 获取某个订单的评价列表
DROP PROCEDURE IF EXISTS [sp_GetEvaluationsByOrder];
GO
CREATE PROCEDURE [sp_GetEvaluationsByOrder]
    @orderId UNIQUEIDENTIFIER
AS
BEGIN
    SET NOCOUNT ON;

    -- 检查订单是否存在 (SQL语句1)
    IF NOT EXISTS (SELECT 1 FROM [Order] WHERE OrderID = @orderId) -- 使用 Order 表检查
    BEGIN
        RAISERROR('订单不存在', 16, 1);
        RETURN;
    END;

    -- 获取评价列表 (SQL语句2)
    -- 使用 Evaluation 表，JOIN User 表获取买家用户名，并添加中文别名
    SELECT
        E.EvaluationID AS 评价ID,
        E.Content AS 评价内容,
        E.Rating AS 评分,
        E.CreateTime AS 创建时间,
        E.BuyerID AS 评价者用户ID, -- 评价者是买家
        U_Buyer.UserName AS 评价者用户名,
        E.SellerID AS 被评价者用户ID, -- 被评价者是卖家
        U_Seller.UserName AS 被评价者用户名
    FROM [Evaluation] E -- 使用 Evaluation 表
    JOIN [User] U_Buyer ON E.BuyerID = U_Buyer.UserID -- JOIN User 表获取买家用户名
    JOIN [User] U_Seller ON E.SellerID = U_Seller.UserID -- JOIN User 表获取卖家用户名
    WHERE E.OrderID = @orderId
    ORDER BY E.CreateTime DESC;

END;
GO

-- sp_CreateEvaluation: 买家对卖家进行评价
-- 输入: @orderId UNIQUEIDENTIFIER, @buyerId UNIQUEIDENTIFIER, @rating INT, @content NVARCHAR(500)
-- 逻辑: 检查订单状态，确保是买家发起，插入 Evaluation 记录。
DROP PROCEDURE IF EXISTS [sp_CreateEvaluation];
GO
CREATE PROCEDURE [sp_CreateEvaluation]
    @orderId UNIQUEIDENTIFIER,
    @buyerId UNIQUEIDENTIFIER,
    @rating INT,
    @content NVARCHAR(500) = NULL
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON; -- 遇到错误自动回滚

    DECLARE @buyerId_order UNIQUEIDENTIFIER; -- 用于从订单表中获取的买家ID
    DECLARE @sellerId UNIQUEIDENTIFIER;
    DECLARE @orderStatus NVARCHAR(50); -- Order 表状态类型

    BEGIN TRY
        BEGIN TRANSACTION; -- 开始事务

        -- 1. 获取订单信息，并检查是否存在 (SQL语句1)
        -- 同时获取 buyerId 和 sellerId 用于后续权限检查
        SELECT
            @buyerId_order = O.BuyerID,
            @sellerId = O.SellerID,
            @orderStatus = O.Status
        FROM [Order] O
        WHERE O.OrderID = @orderId;

        -- 检查订单是否存在
        IF @buyerId_order IS NULL -- 如果订单不存在，@buyerId_order 将是 NULL
        BEGIN
            RAISERROR('订单不存在', 16, 1);
            IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION; RETURN;
        END

        -- 2. 检查用户是否是订单的买家，并且只能买家评价卖家 (控制流 IF)
        IF @buyerId != @buyerId_order
        BEGIN
            RAISERROR('无权评价此订单，只有订单的买家可以评价卖家。', 16, 1);
            IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION; RETURN;
        END

        -- 3. 检查订单是否已完成 (控制流 IF)
        IF @orderStatus != 'Completed'
        BEGIN
            RAISERROR('订单状态 (%s) 不允许评价，只有已完成的订单才能评价。', 16, 1, @orderStatus);
            IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION; RETURN;
        END

        -- 4. 检查评分范围 (控制流 IF)
        IF @rating < 1 OR @rating > 5
        BEGIN
            RAISERROR('评分必须在1-5之间', 16, 1);
            IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION; RETURN;
        END

        -- 5. 检查是否已存在该订单的评价 (由 Evaluation.OrderID 的 UNIQUE 约束保证) (SQL语句2)
        -- 虽然有 UNIQUE 约束，但为了友好的错误提示，可以提前检查
        IF EXISTS (SELECT 1 FROM [Evaluation] WHERE OrderID = @orderId)
        BEGIN
            RAISERROR('该订单已存在一个评价，无法重复发起。', 16, 1);
            IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION; RETURN;
        END

         -- 检查评价内容是否为空 (控制流 IF)
         IF @content IS NULL OR LTRIM(RTRIM(@content)) = ''
         BEGIN
              RAISERROR('评价内容不能为空。', 16, 1);
              IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION; RETURN;
         END

        -- 6. 创建评价 (SQL语句3)
        -- 使用 Evaluation 表，字段为 EvaluationID, OrderID, SellerID, BuyerID, Rating, Content, CreateTime
        INSERT INTO [Evaluation] (
            EvaluationID,
            OrderID,
            SellerID,
            BuyerID,
            Rating,
            Content,
            CreateTime
        )
        VALUES (
            NEWID(), -- EvaluationID
            @orderId, -- OrderID
            @sellerId, -- SellerID (从订单获取)
            @buyerId, -- BuyerID (即 @userId)
            @rating,
            @content,
            GETDATE()
        );

        -- 7. TODO: 可能需要更新订单状态，例如增加一个 'Evaluated' 状态到 Order 表，表示订单已完成评价。(应用层或独立SP处理)
        -- UPDATE [Order] SET Status = 'Evaluated' WHERE OrderID = @orderId; -- 示例

        -- 8. TODO: 评价后更新卖家的信用分 (由 tr_Evaluation_AfterInsert_UpdateSellerCredit 触发器处理)

        COMMIT TRANSACTION; -- 提交事务

        -- 返回创建的评价基本信息 (SQL语句4, 面向UI)
        -- 查询 Evaluation 表，JOIN User 表获取买家用户名和卖家用户名
        SELECT
            E.EvaluationID AS 评价ID,
            E.OrderID AS 订单ID,
            E.SellerID AS 卖家ID,
            U_Seller.UserName AS 卖家用户名,
            E.BuyerID AS 买家ID,
            U_Buyer.UserName AS 买家用户名, -- 获取买家用户名
            E.Rating AS 评分,
            E.Content AS 评价内容,
            E.CreateTime AS 创建时间
        FROM [Evaluation] E
        JOIN [User] U_Buyer ON E.BuyerID = U_Buyer.UserID
        JOIN [User] U_Seller ON E.SellerID = U_Seller.UserID
        WHERE E.OrderID = @orderId; -- 根据 OrderID 查询，因为一个订单只有一个评价

    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0
            ROLLBACK TRANSACTION;

        -- 检查是否是唯一约束冲突错误 (错误号2627) - UNIQUE约束更优先于手动检查
        IF ERROR_NUMBER() = 2627
        BEGIN
             RAISERROR('该订单已存在一个评价（通过唯一约束检查）。', 16, 1);
        END
        ELSE
        BEGIN
            THROW; -- 重新抛出其他错误
        END
    END CATCH
END;
GO 