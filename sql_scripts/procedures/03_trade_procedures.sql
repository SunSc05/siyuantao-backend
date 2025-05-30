/*
 * 交易管理模块 - 订单存储过程
 */

-- sp_CreateOrder: 创建新订单
-- 功能: 验证买家和商品信息，扣减库存，创建订单记录
DROP PROCEDURE IF EXISTS [sp_CreateOrder];
GO
CREATE PROCEDURE [sp_CreateOrder]
    @BuyerID INT,
    @ProductID INT,
    @Quantity INT,
    @ShippingAddress NVARCHAR(255),
    @ContactPhone NVARCHAR(20)
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @ProductPrice DECIMAL(10, 2);
    DECLARE @ProductStock INT;
    DECLARE @SellerID INT;
    DECLARE @OrderStatus VARCHAR(50) = 'Pending'; -- 初始状态为待处理
    DECLARE @ErrorMessage NVARCHAR(4000);

    BEGIN TRY
        BEGIN TRANSACTION;

        -- 检查买家是否存在
        IF NOT EXISTS (SELECT 1 FROM [User] WHERE UserID = @BuyerID AND Role = 'Buyer')
        BEGIN
            SET @ErrorMessage = '创建订单失败：买家不存在或角色不正确。';
            THROW 50001, @ErrorMessage, 1;
        END

        -- 获取商品信息并锁定商品行以防止并发问题
        SELECT @ProductPrice = Price, @ProductStock = Stock, @SellerID = SellerID
        FROM [Product]
        WITH (UPDLOCK) -- 在事务中锁定行，直到事务结束
        WHERE ProductID = @ProductID AND Status = 'Available';

        IF @ProductPrice IS NULL
        BEGIN
            SET @ErrorMessage = '创建订单失败：商品不存在或已下架。';
            THROW 50002, @ErrorMessage, 1;
        END

        -- 检查库存是否充足
        IF @ProductStock < @Quantity
        BEGIN
            SET @ErrorMessage = '创建订单失败：商品库存不足。';
            THROW 50003, @ErrorMessage, 1;
        END

        -- 扣减库存
        UPDATE [Product]
        SET Stock = Stock - @Quantity
        WHERE ProductID = @ProductID;

        -- 创建订单
        INSERT INTO [Order] (BuyerID, SellerID, ProductID, Quantity, TotalPrice, OrderStatus, ShippingAddress, ContactPhone, CreatedAt, UpdatedAt)
        VALUES (@BuyerID, @SellerID, @ProductID, @Quantity, @ProductPrice * @Quantity, @OrderStatus, @ShippingAddress, @ContactPhone, GETDATE(), GETDATE());

        COMMIT TRANSACTION;
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0
            ROLLBACK TRANSACTION;
        
        -- 重新抛出捕获的错误，或者记录错误并抛出自定义错误
        -- 使用 THROW 会保留原始错误信息，包括错误号和消息
        THROW;
        RETURN;
    END CATCH
END;
GO

-- sp_ConfirmOrder: 卖家确认订单
-- 功能: 卖家确认订单，订单状态变为 'Confirmed'
DROP PROCEDURE IF EXISTS [sp_ConfirmOrder];
GO
CREATE PROCEDURE [sp_ConfirmOrder]
    @OrderID INT,
    @SellerID INT
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @CurrentStatus VARCHAR(50);
    DECLARE @ErrorMessage NVARCHAR(4000);

    BEGIN TRY
        BEGIN TRANSACTION;

        SELECT @CurrentStatus = OrderStatus FROM [Order] WHERE OrderID = @OrderID AND SellerID = @SellerID;

        IF @CurrentStatus IS NULL
        BEGIN
            SET @ErrorMessage = '确认订单失败：订单不存在或您不是该订单的卖家。';
            THROW 50004, @ErrorMessage, 1;
        END

        IF @CurrentStatus != 'Pending'
        BEGIN
            SET @ErrorMessage = '确认订单失败：订单状态不是“待处理”，无法确认。当前状态：' + @CurrentStatus;
            THROW 50005, @ErrorMessage, 1;
        END

        UPDATE [Order]
        SET OrderStatus = 'Confirmed', UpdatedAt = GETDATE()
        WHERE OrderID = @OrderID;

        COMMIT TRANSACTION;
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0
            ROLLBACK TRANSACTION;
        THROW;
    END CATCH
END;
GO

-- sp_CompleteOrder: 订单完成
-- 功能: 订单交易完成，状态变为 'Completed'
DROP PROCEDURE IF EXISTS [sp_CompleteOrder];
GO
CREATE PROCEDURE [sp_CompleteOrder]
    @OrderID INT,
    @ActorID INT -- 可以是买家或系统管理员
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @CurrentStatus VARCHAR(50);
    DECLARE @BuyerID INT;
    DECLARE @SellerID INT;
    DECLARE @IsAdmin BIT = 0;
    DECLARE @ErrorMessage NVARCHAR(4000);

    BEGIN TRY
        BEGIN TRANSACTION;

        SELECT @CurrentStatus = OrderStatus, @BuyerID = BuyerID, @SellerID = SellerID FROM [Order] WHERE OrderID = @OrderID;
        
        IF EXISTS (SELECT 1 FROM [User] WHERE UserID = @ActorID AND Role = 'Admin')
            SET @IsAdmin = 1;

        IF @CurrentStatus IS NULL
        BEGIN
            SET @ErrorMessage = '完成订单失败：订单不存在。';
            THROW 50006, @ErrorMessage, 1;
        END

        -- 只有买家或管理员可以完成订单，且订单状态必须是 'Shipped' 或 'Confirmed' (如果流程简化，没有发货步骤)
        IF (@ActorID != @BuyerID AND @IsAdmin = 0)
        BEGIN
            SET @ErrorMessage = '完成订单失败：您无权完成此订单。';
            THROW 50007, @ErrorMessage, 1;
        END

        IF @CurrentStatus NOT IN ('Confirmed', 'Shipped') -- 假设 'Shipped' 是 'Confirmed' 之后的步骤
        BEGIN
            SET @ErrorMessage = '完成订单失败：订单状态不正确，无法完成。当前状态：' + @CurrentStatus;
            THROW 50008, @ErrorMessage, 1;
        END

        UPDATE [Order]
        SET OrderStatus = 'Completed', UpdatedAt = GETDATE()
        WHERE OrderID = @OrderID;

        -- 注意：卖家信用分更新逻辑已移至触发器 tr_Order_AfterComplete_UpdateSellerCredit

        COMMIT TRANSACTION;
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0
            ROLLBACK TRANSACTION;
        THROW;
    END CATCH
END;
GO

-- sp_RejectOrder: 卖家拒绝订单
-- 功能: 卖家拒绝订单，订单状态变为 'Rejected'，库存需要恢复 (通过触发器实现)
DROP PROCEDURE IF EXISTS [sp_RejectOrder];
GO
CREATE PROCEDURE [sp_RejectOrder]
    @OrderID INT,
    @SellerID INT,
    @RejectionReason NVARCHAR(255) NULL -- 可选的拒绝原因
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @CurrentStatus VARCHAR(50);
    DECLARE @ErrorMessage NVARCHAR(4000);

    BEGIN TRY
        BEGIN TRANSACTION;

        SELECT @CurrentStatus = OrderStatus FROM [Order] WHERE OrderID = @OrderID AND SellerID = @SellerID;

        IF @CurrentStatus IS NULL
        BEGIN
            SET @ErrorMessage = '拒绝订单失败：订单不存在或您不是该订单的卖家。';
            THROW 50009, @ErrorMessage, 1;
        END

        IF @CurrentStatus != 'Pending'
        BEGIN
            SET @ErrorMessage = '拒绝订单失败：订单状态不是“待处理”，无法拒绝。当前状态：' + @CurrentStatus;
            THROW 50010, @ErrorMessage, 1;
        END

        UPDATE [Order]
        SET OrderStatus = 'Rejected', UpdatedAt = GETDATE(), Notes = ISNULL(Notes + '; ', '') + 'Rejected by seller: ' + ISNULL(@RejectionReason, 'No reason provided.')
        WHERE OrderID = @OrderID;

        -- 库存恢复逻辑已移至触发器 tr_Order_AfterCancel_RestoreQuantity (假设 Rejected 和 Cancelled 都触发库存恢复)
        -- 如果 Rejected 状态的库存恢复逻辑不同，需要单独的触发器或在此处处理。
        -- 根据设计文档，tr_Order_AfterCancel_RestoreQuantity 应该处理 'Cancelled' 和 'Rejected' 状态。

        COMMIT TRANSACTION;
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0
            ROLLBACK TRANSACTION;
        THROW;
    END CATCH
END;
GO

-- sp_GetOrdersByUser: 根据用户ID获取订单列表
-- 功能: 获取指定用户的订单列表，可根据角色区分买家或卖家订单
DROP PROCEDURE IF EXISTS [sp_GetOrdersByUser];
GO
CREATE PROCEDURE [sp_GetOrdersByUser]
    @UserID INT,
    @UserRole VARCHAR(50) -- 'Buyer' 或 'Seller'
AS
BEGIN
    SET NOCOUNT ON;

    IF @UserRole = 'Buyer'
    BEGIN
        SELECT O.OrderID, O.ProductID, P.Name AS ProductName, O.Quantity, O.TotalPrice, O.OrderStatus, O.ShippingAddress, O.ContactPhone, O.CreatedAt, O.UpdatedAt, O.SellerID, US.Username AS SellerUsername
        FROM [Order] O
        JOIN [Product] P ON O.ProductID = P.ProductID
        JOIN [User] US ON O.SellerID = US.UserID
        WHERE O.BuyerID = @UserID
        ORDER BY O.CreatedAt DESC;
    END
    ELSE IF @UserRole = 'Seller'
    BEGIN
        SELECT O.OrderID, O.ProductID, P.Name AS ProductName, O.Quantity, O.TotalPrice, O.OrderStatus, O.ShippingAddress, O.ContactPhone, O.CreatedAt, O.UpdatedAt, O.BuyerID, UB.Username AS BuyerUsername
        FROM [Order] O
        JOIN [Product] P ON O.ProductID = P.ProductID
        JOIN [User] UB ON O.BuyerID = UB.UserID
        WHERE O.SellerID = @UserID
        ORDER BY O.CreatedAt DESC;
    END
    ELSE
    BEGIN
        DECLARE @ErrorMessage NVARCHAR(4000) = '获取订单失败：无效的用户角色。';
        THROW 50011, @ErrorMessage, 1;
    END
END;
GO