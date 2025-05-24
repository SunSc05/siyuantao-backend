/*
 * 交易相关存储过程
 */

-- 根据用户获取订单列表
DROP PROCEDURE IF EXISTS [sp_GetOrdersByUser];
GO
CREATE PROCEDURE [sp_GetOrdersByUser]
    @userId UNIQUEIDENTIFIER,
    @role NVARCHAR(10) = NULL -- 'buyer' 或 'seller'，NULL表示两者都要
AS
BEGIN
    SET NOCOUNT ON;

    -- 检查用户是否存在
    IF NOT EXISTS (SELECT 1 FROM [User] WHERE UserID = @userId)
    BEGIN
        RAISERROR('用户不存在', 16, 1);
        RETURN;
    END

    SELECT
        O.OrderID AS 订单ID,
        O.Quantity AS 数量,
        O.CreateTime AS 创建时间,
        O.Status AS 订单状态,
        O.CompleteTime AS 完成时间,
        O.CancelTime AS 取消时间,
        O.CancelReason AS 取消原因,
        -- 买家信息
        O.BuyerID AS 买家ID,
        B.UserName AS 买家用户名,
        -- 卖家信息
        O.SellerID AS 卖家ID,
        S.UserName AS 卖家用户名,
        -- 商品信息
        O.ProductID AS 商品ID,
        P.ProductName AS 商品名称,
        P.Price AS 商品价格,
        -- 获取商品主图URL
        (SELECT TOP 1 ImageURL FROM [ProductImage] pi WHERE pi.ProductID = P.ProductID AND pi.SortOrder = 0 ORDER BY UploadTime ASC) AS 商品主图URL
    FROM [Order] O
    JOIN [User] B ON O.BuyerID = B.UserID
    JOIN [User] S ON O.SellerID = S.UserID
    LEFT JOIN [Product] P ON O.ProductID = P.ProductID -- LEFT JOIN 防止商品已被删除导致查不到订单
    WHERE (@role IS NULL AND (O.BuyerID = @userId OR O.SellerID = @userId))
    OR (@role = 'buyer' AND O.BuyerID = @userId)
    OR (@role = 'seller' AND O.SellerID = @userId)
    ORDER BY O.CreateTime DESC;
END;
GO

-- 获取单个订单详情
DROP PROCEDURE IF EXISTS [sp_GetOrderById];
GO
CREATE PROCEDURE [sp_GetOrderById]
    @orderId UNIQUEIDENTIFIER, -- 参数名与表名一致
    @userId UNIQUEIDENTIFIER = NULL -- 增加用户ID参数用于权限检查
AS
BEGIN
    SET NOCOUNT ON;

    DECLARE @buyerId UNIQUEIDENTIFIER;
    DECLARE @sellerId UNIQUEIDENTIFIER;

    -- 获取订单基本信息，同时检查是否存在 (SQL语句1)
    SELECT
        @buyerId = O.BuyerID,
        @sellerId = O.SellerID,
        O.OrderID AS 订单ID,
        O.Quantity AS 数量,
        O.CreateTime AS 创建时间,
        O.Status AS 订单状态,
        O.CompleteTime AS 完成时间,
        O.CancelTime AS 取消时间,
        O.CancelReason AS 取消原因,
        -- 买家信息
        O.BuyerID AS 买家ID,
        B.UserName AS 买家用户名,
        B.PhoneNumber AS 买家手机号码,
        B.Email AS 买家邮箱,
        -- 卖家信息
        O.SellerID AS 卖家ID,
        S.UserName AS 卖家用户名,
        S.PhoneNumber AS 卖家手机号码,
        S.Email AS 卖家邮箱,
        -- 商品信息
        O.ProductID AS 商品ID,
        P.ProductName AS 商品名称,
        P.Description AS 商品描述, -- 添加商品描述
        P.Price AS 商品价格,
        -- 获取商品主图URL (SQL语句2 - 子查询)
        (SELECT TOP 1 ImageURL FROM [ProductImage] pi WHERE pi.ProductID = P.ProductID AND pi.SortOrder = 0 ORDER BY UploadTime ASC) AS 商品主图URL
    FROM [Order] O
    JOIN [User] B ON O.BuyerID = B.UserID
    JOIN [User] S ON O.SellerID = S.UserID
    LEFT JOIN [Product] P ON O.ProductID = P.ProductID -- LEFT JOIN 防止商品已被删除导致查不到订单
    WHERE O.OrderID = @orderId;

    -- 如果未找到订单，则抛出错误
    IF @buyerId IS NULL -- 使用检查变量判断是否存在
    BEGIN
        RAISERROR('订单不存在', 16, 1);
        RETURN;
    END

    -- 权限检查：如果提供了用户ID，则必须是买家或卖家 (控制流 IF)
    -- 可以进一步检查 @userId 是否管理员，这里简化为只允许买家或卖家查看
    -- SQL语句3: 检查用户是否存在且是管理员
    DECLARE @isAdmin BIT = 0;
    IF @userId IS NOT NULL SELECT @isAdmin = IsStaff FROM [User] WHERE UserID = @userId;

    IF @userId IS NOT NULL AND @userId != @buyerId AND @userId != @sellerId AND @isAdmin = 0
    BEGIN
        RAISERROR('无权查看此订单详情。', 16, 1);
        RETURN;
    END

END;
GO

-- sp_CreateOrder: 买家发起订单
-- 输入: @buyerId UNIQUEIDENTIFIER, @productId UNIQUEIDENTIFIER, @quantity INT
-- 输出: @newOrderId UNIQUEIDENTIFIER
DROP PROCEDURE IF EXISTS [sp_CreateOrder];
GO
CREATE PROCEDURE [sp_CreateOrder]
    @buyerId UNIQUEIDENTIFIER,
    @productId UNIQUEIDENTIFIER,
    @quantity INT
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON; -- 遇到错误自动回滚

    DECLARE @newOrderId UNIQUEIDENTIFIER = NEWID();
    DECLARE @buyerIsVerified BIT;
    DECLARE @sellerId UNIQUEIDENTIFIER;
    DECLARE @availableQuantity INT;
    DECLARE @productStatus NVARCHAR(20);

    BEGIN TRY
        BEGIN TRANSACTION;

        -- 1. 检查 @buyerId 对应的用户是否存在且已认证 (SQL语句1)
        SELECT @buyerIsVerified = IsVerified FROM [User] WHERE UserID = @buyerId;
         IF @buyerIsVerified IS NULL
        BEGIN
            RAISERROR('买家用户不存在。', 16, 1);
            IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION; RETURN; -- 回滚并返回
        END
        IF @buyerIsVerified = 0
        BEGIN
            RAISERROR('买家用户未完成邮箱认证，无法发起订单。', 16, 1);
            IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION; RETURN;
        END

        -- 2. 检查 @productId 对应的商品是否存在且状态为 Active (在售) (SQL语句2)
        SELECT @sellerId = OwnerID, @availableQuantity = Quantity, @productStatus = Status
        FROM [Product]
        WHERE ProductID = @productId;

        IF @sellerId IS NULL
        BEGIN
            RAISERROR('商品不存在。', 16, 1); -- 检查商品是否存在
            IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION; RETURN;
        END

        -- 检查商品状态是否为 Active (在售) (控制流 IF)
        IF @productStatus != 'Active'
        BEGIN
            RAISERROR('商品当前状态 (%s) 不可购买。', 16, 1, @productStatus);
            IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION; RETURN;
        END

        -- 3. 检查买家不是卖家 (控制流 IF)
        IF @buyerId = @sellerId
        BEGIN
            RAISERROR('不能购买自己发布的商品。', 16, 1);
            IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION; RETURN;
        END

        -- 4. 检查购买数量是否有效 (控制流 IF)
        IF @quantity <= 0
        BEGIN
            RAISERROR('购买数量必须大于0。', 16, 1);
            IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION; RETURN;
        END

        -- 5. 检查商品库存是否足够 (控制流 IF)
        IF @availableQuantity < @quantity
        BEGIN
            RAISERROR('商品库存不足，当前剩余数量为 %d。', 16, 1, @availableQuantity);
            IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION; RETURN;
        END

        -- 6. 更新 [Product] 表，扣减库存 (SQL语句3)
        UPDATE [Product]
        SET Quantity = Quantity - @quantity
        WHERE ProductID = @productId;

        -- Note: 如果Quantity变为0，会由 tr_Product_AfterUpdate_QuantityStatus 触发器将商品状态设为Sold

        -- 7. 插入 [Order] 记录, 设置 Status = 'PendingSellerConfirmation' (SQL语句4)
        INSERT INTO [Order] (
            OrderID,
            SellerID,
            BuyerID,
            ProductID,
            Quantity,
            CreateTime,
            Status
            -- CompleteTime, CancelTime, CancelReason 初始为 NULL
        )
        VALUES (
            @newOrderId,
            @sellerId,
            @buyerId,
            @productId,
            @quantity,
            GETDATE(),
            'PendingSellerConfirmation'
        );

        -- 8. 通知卖家有新订单 (此通知逻辑通常在应用层处理，SP只负责创建订单和扣减库存)
        -- INSERT INTO [SystemNotification] (...) VALUES (...); -- 示例

        COMMIT TRANSACTION; -- 提交事务

        -- 返回新创建订单的ID和一些基本信息 (SQL语句5, 面向UI)
        SELECT
            @newOrderId AS 新订单ID,
            @buyerId AS 买家ID,
            @sellerId AS 卖家ID,
            @productId AS 商品ID,
            @quantity AS 购买数量,
            'PendingSellerConfirmation' AS 订单状态,
            GETDATE() AS 创建时间;

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

-- sp_ConfirmOrder: 卖家确认订单
-- 输入: @orderId UNIQUEIDENTIFIER, @sellerId UNIQUEIDENTIFIER
DROP PROCEDURE IF EXISTS [sp_ConfirmOrder];
GO
CREATE PROCEDURE [sp_ConfirmOrder]
    @orderId UNIQUEIDENTIFIER,
    @sellerId UNIQUEIDENTIFIER
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON; -- 可选，遇到错误自动回滚

    DECLARE @orderSellerId UNIQUEIDENTIFIER;
    DECLARE @currentStatus NVARCHAR(50);
    -- DECLARE @buyerId UNIQUEIDENTIFIER; -- 用于通知买家

    BEGIN TRY
        BEGIN TRANSACTION; -- 开始事务

        -- 1. 检查 @orderId 对应的订单是否存在且为 'PendingSellerConfirmation' 状态，并且 @sellerId 是订单的卖家 (SQL语句1)
        SELECT @orderSellerId = SellerID, @currentStatus = Status -- , @buyerId = BuyerID -- 获取买家ID
        FROM [Order]
        WHERE OrderID = @orderId;

        IF @orderSellerId IS NULL
        BEGIN
            RAISERROR('订单不存在。', 16, 1);
            IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION; RETURN;
        END

        IF @orderSellerId != @sellerId
        BEGIN
            RAISERROR('无权确认此订单，您不是该订单的卖家。', 16, 1);
            IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION; RETURN;
        END

        IF @currentStatus != 'PendingSellerConfirmation'
        BEGIN
            RAISERROR('订单当前状态 (%s) 不允许确认。', 16, 1, @currentStatus);
            IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION; RETURN;
        END

        -- 3. UPDATE [Order] SET Status = 'ConfirmedBySeller' WHERE OrderID = @orderId; (SQL语句2)
        UPDATE [Order]
        SET Status = 'ConfirmedBySeller'
        WHERE OrderID = @orderId;

        -- 4. 通知买家订单已确认 (通常在应用层处理)
        -- INSERT INTO [SystemNotification] (...) VALUES (...); -- 示例

        COMMIT TRANSACTION; -- 提交事务

        -- 返回成功消息（可选）(SQL语句3)
        SELECT @orderId AS ConfirmedOrderID, '订单确认成功' AS Result;

    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0
            ROLLBACK TRANSACTION;

        THROW; -- 重新抛出捕获的错误
    END CATCH
END;
GO

-- sp_RejectOrder: 卖家拒绝订单
-- 输入: @orderId UNIQUEIDENTIFIER, @sellerId UNIQUEIDENTIFIER, @reason NVARCHAR(500)
DROP PROCEDURE IF EXISTS [sp_RejectOrder];
GO
CREATE PROCEDURE [sp_RejectOrder]
    @orderId UNIQUEIDENTIFIER,
    @sellerId UNIQUEIDENTIFIER,
    @reason NVARCHAR(500) = NULL
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON; -- 可选，遇到错误自动回滚

    DECLARE @orderSellerId UNIQUEIDENTIFIER;
    DECLARE @currentStatus NVARCHAR(50);
    -- DECLARE @productId UNIQUEIDENTIFIER; -- 库存恢复由触发器处理
    -- DECLARE @quantity INT; -- 库存恢复由触发器处理
    -- DECLARE @buyerId UNIQUEIDENTIFIER; -- 用于通知买家，可在应用层查

    BEGIN TRY
        BEGIN TRANSACTION; -- 开始事务

        -- 1. 检查 @orderId 对应的订单是否存在且为 'PendingSellerConfirmation' 状态，并且 @sellerId 是订单的卖家 (SQL语句1)
        SELECT @orderSellerId = SellerID, @currentStatus = Status
        FROM [Order]
        WHERE OrderID = @orderId;

        IF @orderSellerId IS NULL
        BEGIN
            RAISERROR('订单不存在。', 16, 1);
            IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION; RETURN;
        END

        IF @orderSellerId != @sellerId
        BEGIN
            RAISERROR('无权拒绝此订单，您不是该订单的卖家。', 16, 1);
            IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION; RETURN;
        END

        IF @currentStatus != 'PendingSellerConfirmation'
        BEGIN
            RAISERROR('订单当前状态 (%s) 不允许拒绝。', 16, 1, @currentStatus);
            IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION; RETURN;
        END

        -- 拒绝订单必须提供原因 (控制流 IF)
        IF @reason IS NULL OR LTRIM(RTRIM(@reason)) = ''
        BEGIN
            RAISERROR('拒绝订单必须提供原因。', 16, 1);
            IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION; RETURN;
        END

        -- 3. UPDATE [Order] SET Status = 'Cancelled', CancelReason = @reason, CancelTime = GETDATE() (SQL语句2)
        UPDATE [Order]
        SET
            Status = 'Cancelled',
            CancelReason = @reason,
            CancelTime = GETDATE()
        WHERE OrderID = @orderId;

        -- 5. 恢复商品库存 (由 tr_Order_AfterCancel_RestoreQuantity 触发器处理)

        -- 6. 通知买家订单被拒绝 (通常在应用层处理，需要查询买家ID)
        -- INSERT INTO [SystemNotification] (...) VALUES (...); -- 示例

        COMMIT TRANSACTION; -- 提交事务

        -- 返回成功消息（可选）(SQL语句3)
        SELECT @orderId AS RejectedOrderID, '订单拒绝成功' AS Result;

    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0
            ROLLBACK TRANSACTION;

        THROW; -- 重新抛出捕获的错误
    END CATCH
END;
GO

-- sp_CompleteOrder: 买家确认收货，完成订单
-- 输入: @orderId UNIQUEIDENTIFIER, @buyerId UNIQUEIDENTIFIER
DROP PROCEDURE IF EXISTS [sp_CompleteOrder];
GO
CREATE PROCEDURE [sp_CompleteOrder]
    @orderId UNIQUEIDENTIFIER,
    @buyerId UNIQUEIDENTIFIER
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON; -- 遇到错误自动回滚

    DECLARE @orderBuyerId UNIQUEIDENTIFIER;
    DECLARE @currentStatus NVARCHAR(50);

    BEGIN TRY
        BEGIN TRANSACTION; -- 开始事务

        -- 1. 检查 @orderId 对应的订单是否存在且为 'ConfirmedBySeller' 状态，并且 @buyerId 是订单的买家 (SQL语句1)
        SELECT @orderBuyerId = BuyerID, @currentStatus = Status
        FROM [Order]
        WHERE OrderID = @orderId;

        IF @orderBuyerId IS NULL
        BEGIN
            RAISERROR('订单不存在。', 16, 1);
            IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION; RETURN;
        END

        IF @orderBuyerId != @buyerId
        BEGIN
            RAISERROR('无权确认此订单，您不是该订单的买家。', 16, 1);
            IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION; RETURN;
        END

        IF @currentStatus != 'ConfirmedBySeller'
        BEGIN
            RAISERROR('订单当前状态 (%s) 不允许确认收货。', 16, 1, @currentStatus);
            IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION; RETURN;
        END

        -- 3. UPDATE [Order] SET Status = 'Completed', CompleteTime = GETDATE() (SQL语句2)
        UPDATE [Order]
        SET
            Status = 'Completed',
            CompleteTime = GETDATE()
        WHERE OrderID = @orderId;

        -- 触发对卖家的信用分调整（由 tr_Order_AfterComplete_UpdateSellerCredit 触发器处理）

        COMMIT TRANSACTION; -- 提交事务

        -- 返回成功消息（可选）(SQL语句3)
        SELECT @orderId AS CompletedOrderID, '订单完成确认成功' AS Result;

    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0
            ROLLBACK TRANSACTION;

        THROW; -- 重新抛出捕获的错误
    END CATCH
END;
GO

-- sp_RequestReturn: 买家发起退货请求
-- 输入: @orderId UNIQUEIDENTIFIER, @buyerId UNIQUEIDENTIFIER, @reason NVARCHAR(500)
-- 逻辑: 检查订单状态（例如已完成或已确认），确保是买家发起，插入 ReturnRequest，状态为 ReturnRequested。
DROP PROCEDURE IF EXISTS [sp_RequestReturn];
GO
CREATE PROCEDURE [sp_RequestReturn]
    @orderId UNIQUEIDENTIFIER,
    @buyerId UNIQUEIDENTIFIER,
    @reason NVARCHAR(500)
AS
BEGIN
    SET NOCOUNT ON;
    -- SET XACT_ABORT ON; -- 可选

    DECLARE @orderBuyerId UNIQUEIDENTIFIER;
    DECLARE @currentOrderStatus NVARCHAR(50);

    -- 检查订单是否存在，是否属于该买家 (SQL语句1)
    SELECT @orderBuyerId = BuyerID, @currentOrderStatus = Status
    FROM [Order]
    WHERE OrderID = @orderId;

    IF @orderBuyerId IS NULL
    BEGIN
        RAISERROR('订单不存在。', 16, 1);
        RETURN;
    END

    IF @orderBuyerId != @buyerId
    BEGIN
        RAISERROR('无权为此订单发起退货请求，您不是该订单的买家。', 16, 1);
        RETURN;
    END

    -- 检查订单状态是否允许发起退货 (控制流 IF)
    IF @currentOrderStatus NOT IN ('Completed', 'ConfirmedBySeller') -- 示例：允许已完成或已确认状态发起退货
    BEGIN
        RAISERROR('订单当前状态 (%s) 不允许发起退货请求。', 16, 1, @currentOrderStatus);
        RETURN;
    END

    -- 检查是否已存在该订单的退货请求 (由 ReturnRequest.OrderID 的 UNIQUE 约束保证) (SQL语句2)
    -- 虽然有 UNIQUE 约束，但为了友好的错误提示，可以提前检查
    IF EXISTS (SELECT 1 FROM [ReturnRequest] WHERE OrderID = @orderId)
    BEGIN
        RAISERROR('此订单已存在一个退货请求，无法重复发起。', 16, 1);
        RETURN;
    END

    -- 检查退货原因是否为空 (控制流 IF)
    IF @reason IS NULL OR LTRIM(RTRIM(@reason)) = ''
    BEGIN
        RAISERROR('退货请求必须提供原因。', 16, 1);
        RETURN;
    END


    BEGIN TRY
        BEGIN TRANSACTION;

        -- 插入 ReturnRequest 记录，状态为 ReturnRequested (SQL语句3)
        INSERT INTO [ReturnRequest] (ReturnRequestID, OrderID, ReturnReason, ApplyTime, AuditStatus)
        VALUES (NEWID(), @orderId, @reason, GETDATE(), 'ReturnRequested');

        -- TODO: 可能需要更新订单状态，例如增加一个 'ReturnRequested' 状态到 Order 表，表示订单正在走退货流程。
        -- UPDATE [Order] SET Status = 'ReturnRequested' WHERE OrderID = @orderId;

        COMMIT TRANSACTION;

        -- 返回成功消息或新的请求ID（可选）(SQL语句4)
        SELECT @orderId AS RequestedReturnOrderID, '退货请求已提交' AS Result;

    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0
            ROLLBACK TRANSACTION;

        -- 检查是否是唯一约束冲突错误 (错误号2627) - UNIQUE约束更优先于手动检查
        IF ERROR_NUMBER() = 2627
        BEGIN
             RAISERROR('此订单已存在一个退货请求（通过唯一约束检查）。', 16, 1);
        END
        ELSE
        BEGIN
            THROW; -- 重新抛出其他错误
        END
    END CATCH
END;
GO

-- sp_SellerProcessReturn: 卖家处理退货请求
-- 输入: @returnRequestId UNIQUEIDENTIFIER, @sellerId UNIQUEIDENTIFIER, @agree BIT, @sellerIdea NVARCHAR(500)
-- 逻辑: 检查请求是否有效，是否由卖家处理，更新 ReturnRequest.SellerAgree 和 AuditStatus。如果卖家同意，可能需要恢复库存。
DROP PROCEDURE IF EXISTS [sp_SellerProcessReturn];
GO
CREATE PROCEDURE [sp_SellerProcessReturn]
    @returnRequestId UNIQUEIDENTIFIER,
    @sellerId UNIQUEIDENTIFIER,
    @agree BIT, -- 1为同意，0为拒绝
    @sellerIdea NVARCHAR(500) = NULL
AS
BEGIN
    SET NOCOUNT ON;
    -- SET XACT_ABORT ON; -- 可选

    DECLARE @orderId UNIQUEIDENTIFIER;
    DECLARE @returnRequestStatus NVARCHAR(20);
    DECLARE @orderSellerId UNIQUEIDENTIFIER;
    DECLARE @productId UNIQUEIDENTIFIER;
    DECLARE @quantity INT;
    DECLARE @buyerId UNIQUEIDENTIFIER;
    -- DECLARE @currentStatus NVARCHAR(20); -- 未使用

    -- 检查退货请求是否存在且状态为 ReturnRequested (SQL语句1)
    SELECT @orderId = OrderID, @returnRequestStatus = AuditStatus
    FROM [ReturnRequest]
    WHERE ReturnRequestID = @returnRequestId;

    IF @orderId IS NULL
    BEGIN
        RAISERROR('退货请求不存在。', 16, 1);
        RETURN;
    END

     -- 检查退货请求状态是否允许卖家处理 (控制流 IF)
    IF @returnRequestStatus != 'ReturnRequested'
    BEGIN
        RAISERROR('退货请求当前状态 (%s) 不允许卖家处理。', 16, 1, @returnRequestStatus);
        RETURN;
    END

    -- 检查处理者是否为订单的卖家，并获取订单信息用于可能的库存恢复 (SQL语句2)
    SELECT @orderSellerId = SellerID, @productId = ProductID, @quantity = Quantity, @buyerId = BuyerID -- 获取买家ID用于通知
    FROM [Order]
    WHERE OrderID = @orderId;

    IF @orderSellerId IS NULL -- 理论上不会出现，除非订单被删但退货请求未删
    BEGIN
         RAISERROR('关联的订单不存在。', 16, 1);
         RETURN;
    END

    IF @orderSellerId != @sellerId
    BEGIN
        RAISERROR('无权处理此退货请求，您不是该订单的卖家。', 16, 1);
        RETURN;
    END

    -- 如果拒绝，必须提供意见 (控制流 IF)
    IF @agree = 0 AND (@sellerIdea IS NULL OR LTRIM(RTRIM(@sellerIdea)) = '')
    BEGIN
         RAISERROR('拒绝退货请求必须提供意见。', 16, 1);
         RETURN;
    END


    BEGIN TRY
        BEGIN TRANSACTION;

        -- 更新 ReturnRequest (SQL语句3)
        UPDATE [ReturnRequest]
        SET
            SellerAgree = @agree,
            AuditStatus = CASE WHEN @agree = 1 THEN 'ReturnAccepted' ELSE 'ReturnRejected' END,
            AuditTime = GETDATE(),
            AuditIdea = @sellerIdea
        WHERE ReturnRequestID = @returnRequestId;

        -- 如果卖家同意退货 (@agree = 1)，恢复商品库存 (SQL语句4, 5)
        IF @agree = 1
        BEGIN
             -- TODO: 退货流程可能涉及商品退回、买家退款等复杂步骤，恢复库存可能不是数据库SP的唯一职责
             -- 这里仅实现库存恢复逻辑，实际应用中需要考虑退款等
            UPDATE [Product]
            SET Quantity = Quantity + @quantity
            WHERE ProductID = @productId;

            -- 如果商品状态是Sold（因为之前数量为零），恢复为Active
             UPDATE [Product]
            SET Status = 'Active'
            WHERE ProductID = @productId AND Status = 'Sold';


            -- TODO: 更新订单状态为 ReturnAccepted 或类似状态
            -- UPDATE [Order] SET Status = 'ReturnAccepted' WHERE OrderID = @orderId;

        END
        -- ELSE -- @finalStatus = 'ReturnRejected' -- 卖家拒绝，无需额外数据库操作，通知在应用层

         -- TODO: 更新订单状态为 InterventionResolved 或最终的完成/取消状态 (通常由管理员介入后设置)
         -- UPDATE [Order] SET Status = 'InterventionResolved' WHERE OrderID = @orderId;


        COMMIT TRANSACTION;

        -- 返回处理结果 (SQL语句6)
        SELECT @returnRequestId AS ProcessedReturnRequestID, @agree AS SellerAgreed, AuditStatus AS NewStatus
        FROM [ReturnRequest] WHERE ReturnRequestID = @returnRequestId;


    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0
            ROLLBACK TRANSACTION;

        THROW; -- 重新抛出捕获的错误
    END CATCH
END;
GO

-- sp_BuyerRequestIntervention: 买家申请管理员介入退货请求
-- 输入: @returnRequestId UNIQUEIDENTIFIER, @buyerId UNIQUEIDENTIFIER
-- 逻辑: 检查请求状态，确保是买家发起，更新 ReturnRequest.BuyerApplyIntervene = 1, AuditStatus = 'InterventionRequested'。
DROP PROCEDURE IF EXISTS [sp_BuyerRequestIntervention];
GO
CREATE PROCEDURE [sp_BuyerRequestIntervention]
    @returnRequestId UNIQUEIDENTIFIER,
    @buyerId UNIQUEIDENTIFIER
AS
BEGIN
    SET NOCOUNT ON;
    -- SET XACT_ABORT ON; -- 可选

    DECLARE @orderId UNIQUEIDENTIFIER;
    DECLARE @returnRequestStatus NVARCHAR(20);
    DECLARE @orderBuyerId UNIQUEIDENTIFIER;

    -- 检查退货请求是否存在且状态允许申请介入 (例如 'ReturnRequested' 或 'ReturnRejected' 卖家拒绝后) (SQL语句1)
    SELECT @orderId = OrderID, @returnRequestStatus = AuditStatus
    FROM [ReturnRequest]
    WHERE ReturnRequestID = @returnRequestId;

    IF @orderId IS NULL
    BEGIN
        RAISERROR('退货请求不存在。', 16, 1);
        RETURN;
    END

     -- 检查请求是否允许申请介入 (控制流 IF)
    IF @returnRequestStatus NOT IN ('ReturnRequested', 'ReturnRejected') -- 示例：卖家未处理或卖家拒绝后，买家可以申请介入
    BEGIN
        RAISERROR('退货请求当前状态 (%s) 不允许申请管理员介入。', 16, 1, @returnRequestStatus);
        RETURN;
    END

    -- 检查申请者是否为订单的买家 (SQL语句2)
    SELECT @orderBuyerId = BuyerID FROM [Order] WHERE OrderID = @orderId;
     IF @orderBuyerId IS NULL -- 理论上不会出现
    BEGIN
         RAISERROR('关联的订单不存在。', 16, 1);
         RETURN;
    END

    IF @buyerId != @orderBuyerId
    BEGIN
        RAISERROR('无权申请介入此退货请求，您不是该订单的买家。', 16, 1);
        RETURN;
    END

     -- 检查是否已经申请过介入 (SQL语句3)
     DECLARE @buyerApplied BIT;
     SELECT @buyerApplied = BuyerApplyIntervene FROM [ReturnRequest] WHERE ReturnRequestID = @returnRequestId;
     IF @buyerApplied = 1
     BEGIN
          RAISERROR('您已为此退货请求申请过管理员介入。', 16, 1);
          RETURN;
     END


    BEGIN TRY
        BEGIN TRANSACTION;

        -- 更新 ReturnRequest (SQL语句4)
        UPDATE [ReturnRequest]
        SET
            BuyerApplyIntervene = 1,
            AuditStatus = 'InterventionRequested' -- 将状态更新为等待管理员介入
        WHERE ReturnRequestID = @returnRequestId;

        -- TODO: 通知管理员有新的介入请求需要处理

        COMMIT TRANSACTION;

        -- 返回成功消息（可选）(SQL语句5)
        SELECT @returnRequestId AS InterventionRequestedReturnRequestID, AuditStatus AS NewStatus
        FROM [ReturnRequest] WHERE ReturnRequestID = @returnRequestId;

    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0
            ROLLBACK TRANSACTION;

        THROW; -- 重新抛出捕获的错误
    END CATCH
END;
GO

-- sp_AdminProcessReturnIntervention: 管理员处理介入的退货请求
-- 输入: @returnRequestId UNIQUEIDENTIFIER, @adminId UNIQUEIDENTIFIER, @finalStatus NVARCHAR(20) ('ReturnAccepted' 或 'ReturnRejected'), @adminResult NVARCHAR(500)
-- 逻辑: 检查管理员权限，检查请求状态。根据 finalStatus (ReturnAccepted 或 ReturnRejected) 更新 ReturnRequest。如果同意，务必恢复商品库存，并可能对买卖双方信用分进行调整。同时通知双方。
DROP PROCEDURE IF EXISTS [sp_AdminProcessReturnIntervention];
GO
CREATE PROCEDURE [sp_AdminProcessReturnIntervention]
    @returnRequestId UNIQUEIDENTIFIER,
    @adminId UNIQUEIDENTIFIER,
    @finalStatus NVARCHAR(20), -- 'ReturnAccepted' 或 'ReturnRejected'
    @adminResult NVARCHAR(500) = NULL
AS
BEGIN
    SET NOCOUNT ON;
    -- SET XACT_ABORT ON; -- 可选

    DECLARE @orderId UNIQUEIDENTIFIER;
    DECLARE @returnRequestStatus NVARCHAR(20);
    DECLARE @adminIsStaff BIT;
    DECLARE @productId UNIQUEIDENTIFIER;
    DECLARE @quantity INT;
    DECLARE @buyerId UNIQUEIDENTIFIER;
    DECLARE @sellerId UNIQUEIDENTIFIER;

    -- 检查 @adminId 是否为管理员 (SQL语句1)
    SELECT @adminIsStaff = IsStaff FROM [User] WHERE UserID = @adminId;
    IF @adminIsStaff IS NULL OR @adminIsStaff = 0
    BEGIN
        RAISERROR('无权限执行此操作，只有管理员可以处理介入请求。', 16, 1);
        RETURN;
    END

    -- 检查 @finalStatus 是否有效 (控制流 IF)
    IF @finalStatus NOT IN ('ReturnAccepted', 'ReturnRejected')
    BEGIN
        RAISERROR('无效的最终状态，必须是 ReturnAccepted 或 ReturnRejected。', 16, 1);
        RETURN;
    END

    -- 检查退货请求是否存在且状态为 InterventionRequested (SQL语句2)
    SELECT @orderId = OrderID, @returnRequestStatus = AuditStatus
    FROM [ReturnRequest]
    WHERE ReturnRequestID = @returnRequestId;

    IF @orderId IS NULL
    BEGIN
        RAISERROR('退货请求不存在。', 16, 1);
        RETURN;
    END

    IF @returnRequestStatus != 'InterventionRequested'
    BEGIN
        RAISERROR('退货请求当前状态 (%s) 不允许管理员处理。', 16, 1, @returnRequestStatus);
        RETURN;
    END

    -- 获取订单信息以便恢复库存和通知 (SQL语句3)
    SELECT @productId = ProductID, @quantity = Quantity, @buyerId = BuyerID, @sellerId = SellerID
    FROM [Order]
    WHERE OrderID = @orderId;

    IF @productId IS NULL -- 理论上不会出现
    BEGIN
         RAISERROR('关联的订单不存在。', 16, 1);
         RETURN;
    END

    -- 检查管理员处理结果是否为空 (控制流 IF)
     IF @adminResult IS NULL OR LTRIM(RTRIM(@adminResult)) = ''
     BEGIN
          RAISERROR('管理员处理结果描述不能为空。', 16, 1);
          RETURN;
     END


    BEGIN TRY
        BEGIN TRANSACTION;

        -- 更新 ReturnRequest 状态和结果 (SQL语句4)
        UPDATE [ReturnRequest]
        SET
            AuditStatus = @finalStatus,
            AuditTime = GETDATE(),
            ProcessorAdminID = @adminId,
            AuditIdea = @adminResult, -- 将管理员的处理结果记录在 AuditIdea
            SellerAgree = CASE @finalStatus WHEN 'ReturnAccepted' THEN 1 WHEN 'ReturnRejected' THEN 0 ELSE NULL END -- 同步SellerAgree字段状态
        WHERE ReturnRequestID = @returnRequestId;


        -- 根据最终状态执行后续操作
        IF @finalStatus = 'ReturnAccepted'
        BEGIN
             -- 管理员同意退货：恢复库存，通知买卖双方，可能调整信用分
             -- 恢复商品库存 (SQL语句5, 6)
             UPDATE [Product]
             SET Quantity = Quantity + @quantity
             WHERE ProductID = @productId;

             UPDATE [Product]
             SET Status = 'Active'
             WHERE ProductID = @productId AND Status = 'Sold';

             -- TODO: 通知买卖双方退货已同意 (在应用层处理)
             -- DECLARE @notificationTitleAgree NVARCHAR(200) = '退货请求管理员处理结果';
             -- DECLARE @notificationContentAgree NVARCHAR(MAX) = '订单 (' + CAST(@orderId AS NVARCHAR(36)) + ') 的退货请求，管理员介入后已同意。原因: ' + @adminResult;
             -- INSERT INTO [SystemNotification] (NotificationID, UserID, Title, Content, CreateTime, IsRead) VALUES (NEWID(), @buyerId, @notificationTitleAgree, @notificationContentAgree, GETDATE(), 0);
             -- INSERT INTO [SystemNotification] (NotificationID, UserID, Title, Content, CreateTime, IsRead) VALUES (NEWID(), @sellerId, @notificationTitleAgree, @notificationContentAgree, GETDATE(), 0);


             -- TODO: 信用分调整（如果同意退货需要扣卖家信用分或给买家加分）
             -- EXEC [sp_AdjustUserCredit] @userId = @sellerId, @creditAdjustment = -5, @adminId = @adminId, @reason = '管理员介入退货，判定卖家责任，扣除信用分。'; -- 示例：扣除卖家信用分
             -- EXEC [sp_AdjustUserCredit] @userId = @buyerId, @creditAdjustment = 2, @adminId = @adminId, @reason = '管理员介入退货，判定买家有理，增加信用分。'; -- 示例：给买家增加信用分

        END
        ELSE -- @finalStatus = 'ReturnRejected'
        BEGIN
             -- 管理员拒绝退货：通知买卖双方，可能调整信用分
              -- TODO: 通知买卖双方退货已拒绝 (在应用层处理)
             -- DECLARE @notificationTitleReject NVARCHAR(200) = '退货请求管理员处理结果';
             -- DECLARE @notificationContentReject NVARCHAR(MAX) = '订单 (' + CAST(@orderId AS NVARCHAR(36)) + ') 的退货请求，管理员介入后已拒绝。原因: ' + @adminResult;
             -- INSERT INTO [SystemNotification] (NotificationID, UserID, Title, Content, CreateTime, IsRead) VALUES (NEWID(), @buyerId, @notificationTitleReject, @notificationContentReject, GETDATE(), 0);
             -- INSERT INTO [SystemNotification] (NotificationID, UserID, Title, Content, CreateTime, IsRead) VALUES (NEWID(), @sellerId, @notificationTitleReject, @notificationContentReject, GETDATE(), 0);


             -- TODO: 信用分调整（如果拒绝退货需要扣买家信用分或给卖家加分）
             -- EXEC [sp_AdjustUserCredit] @userId = @buyerId, @creditAdjustment = -5, @adminId = @adminId, @reason = '管理员介入退货，判定买家无理，扣除信用分。'; -- 示例：扣除买家信用分
             -- EXEC [sp_AdjustUserCredit] @userId = @sellerId, @creditAdjustment = 2, @adminId = @adminId, @reason = '管理员介入退货，判定卖家无责，增加信用分。'; -- 示例：给卖家增加信用分
        END

         -- TODO: 更新订单状态为 InterventionResolved 或最终的完成/取消状态
         -- UPDATE [Order] SET Status = 'InterventionResolved' WHERE OrderID = @orderId;


        COMMIT TRANSACTION;

        -- 返回处理结果 (SQL语句7)
        SELECT @returnRequestId AS ProcessedInterventionReturnRequestID, AuditStatus AS FinalStatus, AuditIdea AS AdminResult
        FROM [ReturnRequest] WHERE ReturnRequestID = @returnRequestId;

    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0
            ROLLBACK TRANSACTION;

        THROW; -- 重新抛出捕获的错误
    END CATCH
END;
GO 