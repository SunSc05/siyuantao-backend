/*
 * 交易管理模块 - 订单触发器
 * 功能: 订单取消时恢复商品库存，订单完成时更新卖家信用分
 */

-- tr_Order_AfterCancel_RestoreQuantity: 订单状态变为Cancelled时，恢复商品数量
-- ON [Order] AFTER UPDATE
DROP TRIGGER IF EXISTS [tr_Order_AfterCancel_RestoreQuantity];
GO
CREATE TRIGGER [tr_Order_AfterCancel_RestoreQuantity]
ON [Order]
AFTER UPDATE
AS
BEGIN
    SET NOCOUNT ON;

    BEGIN TRY -- 添加 TRY 块

    -- 检查是否有订单从非Cancelled状态更新为Cancelled状态
    IF EXISTS (
        SELECT 1
        FROM inserted i
        JOIN deleted d ON i.OrderID = d.OrderID
        WHERE i.Status = 'Cancelled' AND d.Status != 'Cancelled'
    )
    BEGIN
        -- 为所有变为Cancelled状态的订单，恢复商品数量
        -- 注意：商品状态的变更（Sold -> Active）现在主要由 tr_Product_AfterUpdate_QuantityStatus 处理 Quantity 的变化
        UPDATE P
        SET
            P.Quantity = P.Quantity + i.Quantity -- 恢复库存数量
             -- P.Status 的变更现在由 Product 触发器处理
        FROM [Product] P
        JOIN inserted i ON P.ProductID = i.ProductID -- Join on ProductID from the inserted order row
        JOIN deleted d ON i.OrderID = d.OrderID -- Ensure it was an update from a different status
        WHERE i.Status = 'Cancelled' AND d.Status != 'Cancelled';
    END

    END TRY
    BEGIN CATCH -- 添加 CATCH 块
        -- 在触发器中，错误处理应该记录错误并可能回滚事务
        -- THROW 会传播错误，导致触发语句的事务回滚
        THROW;
    END CATCH
END;
GO

-- tr_Order_AfterComplete_UpdateSellerCredit: 订单完成时更新卖家的信用分（例如 +1）
-- ON [Order] AFTER UPDATE
DROP TRIGGER IF EXISTS [tr_Order_AfterComplete_UpdateSellerCredit];
GO
CREATE TRIGGER [tr_Order_AfterComplete_UpdateSellerCredit]
ON [Order]
AFTER UPDATE
AS
BEGIN
    SET NOCOUNT ON;

    BEGIN TRY -- 添加 TRY 块

    -- 检查是否有订单从非Completed状态更新为Completed状态
    IF EXISTS (
        SELECT 1
        FROM inserted i
        JOIN deleted d ON i.OrderID = d.OrderID
        WHERE i.Status = 'Completed' AND d.Status != 'Completed'
    )
    BEGIN
        -- 为所有变为Completed状态的订单，增加对应卖家的信用分
        UPDATE U
        SET U.Credit = CASE
                         WHEN U.Credit + 1 > 100 THEN 100 -- 信用分上限100
                         ELSE U.Credit + 1
                       END
        FROM [User] U
        JOIN inserted i ON U.UserID = i.SellerID -- 更新的是卖家的信用分
        JOIN deleted d ON i.OrderID = d.OrderID
        WHERE i.Status = 'Completed' AND d.Status != 'Completed';
    END

    END TRY
    BEGIN CATCH -- 添加 CATCH 块
         -- 在触发器中，错误处理应该记录错误并可能回滚事务
        -- THROW 会传播错误，导致触发语句的事务回滚
        THROW;
    END CATCH
END;
GO 