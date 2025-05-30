import pyodbc
from uuid import UUID
from typing import List, Optional, Dict, Any # 导入 Dict 和 Any

from app.dal.orders_dal import OrdersDAL # 假设 OrderDAL 在 app.dal.order_dal 中
from app.schemas.order_schemas import ( # 假设订单相关的 Pydantic schemas 在 app.schemas.order_schemas 中
    OrderCreateSchema, 
    OrderResponseSchema,
    OrderStatusUpdateSchema # 将 OrderUpdateStatusSchema 更正为 OrderStatusUpdateSchema
)
from app.schemas.user_schemas import UserResponseSchema # 将 UserSchema 更正为 UserResponseSchema
from app.exceptions import DALError, NotFoundError, NotFoundError, ForbiddenError # 移除 ValueError

class OrderService:
    """Service layer for order management."""

    def __init__(self, order_dal: OrdersDAL):
        """
        Initializes the OrderService with an OrderDAL instance.

        Args:
            order_dal: An instance of OrderDAL for database interactions.
        """
        self.order_dal = order_dal

    async def create_order(
        self, 
        conn: pyodbc.Connection, 
        order_data: OrderCreateSchema, 
        buyer_id: UUID
    ) -> OrderResponseSchema:
        """
        Creates a new order.

        Args:
            conn: The database connection object.
            order_data: Data for creating the order (e.g., product_id, quantity).
            buyer_id: The ID of the user creating the order.

        Returns:
            The created order details.

        Raises:
            DALError: If there's an issue with database interaction.
            ValueError: If input data is invalid (e.g., product not available, insufficient stock - though some of this might be handled by SP).
            NotFoundError: If related entities (e.g., product) are not found.
        """
        try:
            # Business logic before creating order can be added here
            # For example, check product availability or stock, though sp_CreateOrder might handle this.
            
            # The sp_CreateOrder stored procedure is expected to return the created order's ID.
            # And potentially other details that can be used to fetch/construct the OrderResponseSchema.
            created_order_id = await self.order_dal.create_order(
                conn=conn,
                product_id=order_data.product_id,
                buyer_id=buyer_id,
                quantity=order_data.quantity,
                shipping_address=order_data.shipping_address, # 添加此行
                contact_phone=order_data.contact_phone # 添加此行
            )
            
            if created_order_id is None:
                raise ValueError("Failed to create order, stored procedure did not return an order ID.")

            # Fetch the full order details using the ID to return a complete OrderResponseSchema
            # This might involve another DAL call, e.g., self.order_dal.get_order_by_id()
            # For simplicity, let's assume sp_CreateOrder returns enough info or we call get_order_by_id
            order = await self.order_dal.get_order_by_id(conn, created_order_id)
            if not order:
                raise NotFoundError(f"Order with ID {created_order_id} not found after creation.")
            
            return order # Assuming get_order_by_id returns data compatible with OrderResponseSchema
        except pyodbc.Error as db_err:
            # Log db_err
            raise DALError(f"Database error during order creation: {db_err}") from db_err
        except DALError:
            raise # Re-raise DALError from order_dal
        except NotFoundError:
            raise # Re-raise NotFoundError
        except ValueError:
            raise # Re-raise ValueError
        except Exception as e:
            # Log e
            raise DALError(f"An unexpected error occurred during order creation: {e}") from e

    async def confirm_order(
        self, 
        conn: pyodbc.Connection, 
        order_id: UUID, # 修改为 UUID
        user_id: UUID # Typically seller_id
    ) -> OrderResponseSchema:
        """
        Confirms an order (e.g., by the seller).

        Args:
            conn: The database connection object.
            order_id: The ID of the order to confirm.
            user_id: The ID of the user performing the action (seller).

        Returns:
            The updated order details.

        Raises:
            NotFoundError: If the order is not found.
            ForbiddenError: If the user is not authorized to confirm the order.
            ValueError: If the order cannot be confirmed (e.g., wrong state).
            DALError: If there's an issue with database interaction.
        """
        try:
            # Optional: Fetch order to check current status and ownership before calling DAL
            order_to_update = await self.order_dal.get_order_by_id(conn, order_id)
            if not order_to_update:
                raise NotFoundError(f"Order with ID {order_id} not found.")

            # Example authorization check (assuming order has a seller_id field)
            # if order_to_update.seller_id != user_id:
            #     raise ForbiddenError("You are not authorized to confirm this order.")

            # Example status check
            # if order_to_update.status != "PendingConfirmation": # Or similar status
            #     raise ValueError(f"Order {order_id} cannot be confirmed in its current state: {order_to_update.status}.")

            await self.order_dal.confirm_order(conn, order_id, user_id) # 传递 user_id
            
            updated_order = await self.order_dal.get_order_by_id(conn, order_id)
            if not updated_order:
                 raise NotFoundError(f"Order with ID {order_id} not found after confirmation.") # Should not happen if confirm_order was successful
            return updated_order
        except pyodbc.Error as db_err:
            raise DALError(f"Database error confirming order {order_id}: {db_err}") from db_err
        except (NotFoundError, ForbiddenError, ValueError, DALError):
            raise
        except Exception as e:
            raise DALError(f"An unexpected error occurred confirming order {order_id}: {e}") from e

    async def complete_order(
        self, 
        conn: pyodbc.Connection, 
        order_id: UUID, # 修改为 UUID
        user_id: UUID # Typically buyer_id or system
    ) -> OrderResponseSchema:
        """
        Marks an order as complete.

        Args:
            conn: The database connection object.
            order_id: The ID of the order to complete.
            user_id: The ID of the user performing the action.

        Returns:
            The updated order details.
        """
        try:
            # Similar pre-checks (existence, authorization, status) as in confirm_order can be added
            await self.order_dal.complete_order(conn, order_id, user_id)
            updated_order = await self.order_dal.get_order_by_id(conn, order_id)
            if not updated_order:
                 raise NotFoundError(f"Order with ID {order_id} not found after completion.")
            return updated_order
        except pyodbc.Error as db_err:
            raise DALError(f"Database error completing order {order_id}: {db_err}") from db_err
        except (NotFoundError, ForbiddenError, ValueError, DALError):
            raise
        except Exception as e:
            raise DALError(f"An unexpected error occurred completing order {order_id}: {e}") from e

    async def reject_order(
        self, 
        conn: pyodbc.Connection, 
        order_id: UUID, # 修改为 UUID
        user_id: UUID, # Typically seller_id
        reason: Optional[str] = None # Optional reason for rejection
    ) -> OrderResponseSchema:
        """
        Rejects an order.

        Args:
            conn: The database connection object.
            order_id: The ID of the order to reject.
            user_id: The ID of the user performing the action.
            reason: Optional reason for rejection.

        Returns:
            The updated order details.
        """
        try:
            # Similar pre-checks as in confirm_order
            await self.order_dal.reject_order(conn, order_id, user_id, reason) # 传递 user_id
            updated_order = await self.order_dal.get_order_by_id(conn, order_id)
            if not updated_order:
                 raise NotFoundError(f"Order with ID {order_id} not found after rejection.")
            return updated_order
        except pyodbc.Error as db_err:
            raise DALError(f"Database error rejecting order {order_id}: {db_err}") from db_err
        except (NotFoundError, ForbiddenError, ValueError, DALError):
            raise
        except Exception as e:
            raise DALError(f"An unexpected error occurred rejecting order {order_id}: {e}") from e

    async def cancel_order(
        self,
        conn: pyodbc.Connection,
        order_id: UUID,
        user_id: UUID,
        cancel_reason: str
    ) -> None:
        """
        Cancels an order.

        Args:
            conn: The database connection object.
            order_id: The ID of the order to cancel.
            user_id: The ID of the user performing the action.
            cancel_reason: The reason for cancellation.

        Raises:
            NotFoundError: If the order is not found.
            ForbiddenError: If the user is not authorized to cancel the order.
            ValueError: If the order cannot be canceled (e.g., wrong state).
            DALError: If there's an issue with database interaction.
        """
        try:
            # Optional: Fetch order to check current status and authorization before calling DAL
            order_to_update = await self.order_dal.get_order_by_id(conn, order_id)
            if not order_to_update:
                raise NotFoundError(f"Order with ID {order_id} not found.")

            # Example authorization check (assuming order has buyer_id/seller_id fields)
            # if order_to_update.buyer_id != user_id and order_to_update.seller_id != user_id:
            #     raise ForbiddenError("You are not authorized to cancel this order.")

            # Example status check
            # if order_to_update.status not in ["Pending", "Confirmed"]: # Or similar statuses that allow cancellation
            #     raise ValueError(f"Order {order_id} cannot be canceled in its current state: {order_to_update.status}.")

            await self.order_dal.cancel_order(conn, order_id, user_id, cancel_reason)
            # Note: Cancellation might not return the full order schema, depending on requirements.
            # If needed, fetch the updated order: updated_order = await self.order_dal.get_order_by_id(conn, order_id)
            # For now, assuming None return is acceptable for cancellation success.

        except pyodbc.Error as db_err:
            raise DALError(f"Database error canceling order {order_id}: {db_err}") from db_err
        except (NotFoundError, ForbiddenError, ValueError, DALError):
            raise
        except Exception as e:
            raise DALError(f"An unexpected error occurred canceling order {order_id}: {e}") from e

    async def delete_order(
        self,
        conn: pyodbc.Connection,
        order_id: UUID,
        user_id: UUID
    ) -> None:
        """
        Deletes an order.

        Args:
            conn: The database connection object.
            order_id: The ID of the order to delete.
            user_id: The ID of the user performing the action.

        Raises:
            NotFoundError: If the order is not found.
            ForbiddenError: If the user is not authorized to delete the order.
            ValueError: If the order cannot be deleted (e.g., wrong state).
            DALError: If there's an issue with database interaction.
        """
        try:
            # Optional: Fetch order to check current status and authorization before calling DAL
            order_to_delete = await self.order_dal.get_order_by_id(conn, order_id)
            if not order_to_delete:
                raise NotFoundError(f"Order with ID {order_id} not found.")

            # Example authorization check (assuming only buyer or admin can delete)
            # if order_to_delete.buyer_id != user_id: # Add admin check if applicable
            #     raise ForbiddenError("You are not authorized to delete this order.")

            # Example status check (e.g., only allow deletion if status is 'Cancelled' or 'Rejected')
            # if order_to_delete.status not in ["Cancelled", "Rejected"]:
            #     raise ValueError(f"Order {order_id} cannot be deleted in its current state: {order_to_delete.status}.")

            await self.order_dal.delete_order(conn, order_id, user_id)
            # Note: Deletion typically doesn't return anything on success.

        except pyodbc.Error as db_err:
            raise DALError(f"Database error deleting order {order_id}: {db_err}") from db_err
        except (NotFoundError, ForbiddenError, ValueError, DALError):
            raise
        except Exception as e:
            raise DALError(f"An unexpected error occurred deleting order {order_id}: {e}") from e

    async def get_orders_by_user(
        self,
        conn: pyodbc.Connection,
        user_id: UUID, # 修改为 UUID
        is_seller: bool,
        status: Optional[str] = None,
        page_number: int = 1,
        page_size: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Retrieves orders for a specific user.
        The sp_GetOrdersByUser likely needs a parameter to distinguish between buyer and seller orders.

        Args:
            conn: The database connection object.
            user_id: The ID of the user whose orders are to be retrieved.
            user_role: Specifies if the user is a 'buyer' or 'seller' for these orders.

        Returns:
            A list of orders.
        
        Raises:
            DALError: If there's an issue with database interaction.
            ValueError: If user_role is invalid.
        """
        if user_role not in ['buyer', 'seller']:
            raise ValueError("Invalid user_role specified. Must be 'buyer' or 'seller'.")
        
        try:
            orders = await self.order_dal.get_orders_by_user(conn, user_id, user_role)
            return orders # Assuming DAL method returns a list of OrderResponseSchema compatible objects
        except pyodbc.Error as db_err:
            raise DALError(f"Database error retrieving orders for user {user_id}: {db_err}") from db_err
        except DALError:
            raise
        except Exception as e:
            raise DALError(f"An unexpected error occurred retrieving orders for user {user_id}: {e}") from e

    async def get_order_by_id(
        self,
        conn: pyodbc.Connection,
        order_id: UUID, # 修改为 UUID
        requesting_user_id: UUID # ID of the user requesting this order, for authorization
    ) -> Optional[OrderResponseSchema]:
        """
        Retrieves a single order by its ID, with authorization check.

        Args:
            conn: The database connection object.
            order_id: The ID of the order to retrieve.
            requesting_user_id: The ID of the user making the request.

        Returns:
            The order details if found and authorized, otherwise None or raises ForbiddenError.

        Raises:
            NotFoundError: If the order is not found.
            ForbiddenError: If the user is not authorized to view the order.
            DALError: If there's an issue with database interaction.
        """
        try:
            order = await self.order_dal.get_order_by_id(conn, order_id)
            if not order:
                raise NotFoundError(f"Order with ID {order_id} not found.")

            # Authorization check: User must be buyer or seller of the order.
            # This assumes OrderResponseSchema (or the object returned by DAL) has buyer_id and seller_id.
            # if order.buyer_id != requesting_user_id and order.seller_id != requesting_user_id:
            #     # Add logic here if admins should be able to bypass this
            #     raise ForbiddenError("You are not authorized to view this order.")
            
            return order
        except pyodbc.Error as db_err:
            raise DALError(f"Database error retrieving order {order_id}: {db_err}") from db_err
        except (NotFoundError, ForbiddenError, DALError):
            raise
        except Exception as e:
            raise DALError(f"An unexpected error occurred retrieving order {order_id}: {e}") from e

    async def update_order_status(
        self,
        conn: pyodbc.Connection,
        order_id: UUID,
        new_status: str,
        user_id: UUID,
        cancel_reason: Optional[str] = None
    ) -> OrderResponseSchema:
        """
        Updates the status of an order based on the new_status provided.

        Args:
            conn: The database connection object.
            order_id: The ID of the order to update.
            new_status: The new status for the order (e.g., "Confirmed", "Completed", "Rejected", "Cancelled").
            user_id: The ID of the user performing the action.
            cancel_reason: Optional reason for cancellation, required if new_status is "Cancelled".

        Returns:
            The updated order details.

        Raises:
            ValueError: If the new_status is invalid or required parameters are missing.
            NotFoundError: If the order is not found.
            ForbiddenError: If the user is not authorized to perform the status update.
            DALError: If there's an issue with database interaction.
        """
        try:
            # Fetch the order to perform pre-checks if necessary (e.g., current status, ownership)
            # This can prevent unnecessary DAL calls if the state transition is invalid
            current_order = await self.order_dal.get_order_by_id(conn, order_id)
            if not current_order:
                raise NotFoundError(f"Order with ID {order_id} not found.")

            # Determine which DAL method to call based on new_status
            if new_status == "Confirmed":
                await self.order_dal.confirm_order(conn, order_id, user_id)
            elif new_status == "Completed":
                await self.order_dal.complete_order(conn, order_id, user_id)
            elif new_status == "Rejected":
                await self.order_dal.reject_order(conn, order_id, user_id, cancel_reason) # Rejection reason can be passed here
            elif new_status == "Cancelled":
                if not cancel_reason:
                    raise ValueError("Cancel reason is required for 'Cancelled' status.")
                await self.order_dal.cancel_order(conn, order_id, user_id, cancel_reason)
            else:
                raise ValueError(f"Invalid new_status: {new_status}")

            # Fetch the updated order details to return
            updated_order = await self.order_dal.get_order_by_id(conn, order_id)
            if not updated_order:
                # This case should ideally not be reached if the DAL operation was successful
                raise DALError(f"Failed to retrieve order {order_id} after status update.")

            return OrderResponseSchema(**updated_order)

        except pyodbc.Error as db_err:
            raise DALError(f"Database error updating order {order_id} status to {new_status}: {db_err}") from db_err
        except (ValueError, NotFoundError, ForbiddenError, DALError):
            raise # Re-raise specific exceptions
        except Exception as e:
            raise DALError(f"An unexpected error occurred while updating order {order_id} status to {new_status}: {e}") from e

# Note: 
# 1. Pydantic Schemas (OrderCreateSchema, OrderResponseSchema, etc.) need to be defined in `app.schemas.order_schemas.py`.
# 2. OrderDAL needs to be implemented in `app.dal.order_dal.py` with methods like `create_order`, `confirm_order`, etc., that call the respective stored procedures.
# 3. The actual parameters and return values of DAL methods and stored procedures should be verified against their definitions.
# 4. Business logic within service methods (e.g., status checks, more detailed authorization) should be expanded based on specific requirements.
# 5. Error handling can be further refined, potentially raising more specific custom exceptions.