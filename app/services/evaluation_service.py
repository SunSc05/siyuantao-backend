import pyodbc
from uuid import UUID
from typing import Optional, List

from app.dal.evaluation_dal import EvaluationDAL # Assuming EvaluationDAL is in app.dal.evaluation_dal
from app.schemas.evaluation_schemas import ( # Assuming evaluation-related Pydantic schemas are in app.schemas.evaluation_schemas
    EvaluationCreateSchema,
    EvaluationResponseSchema
)
# If needed, import Order related schemas or services for validation (e.g., to check if order can be evaluated)
# from app.services.order_service import OrderService 
from app.exceptions import DALError, NotFoundError, ForbiddenError, IntegrityError # Import IntegrityError

class EvaluationService:
    """Service layer for evaluation management."""

    def __init__(self, evaluation_dal: EvaluationDAL):
        """
        Initializes the EvaluationService with an EvaluationDAL instance.

        Args:
            evaluation_dal: An instance of EvaluationDAL for database interactions.
        """
        self.evaluation_dal = evaluation_dal
        # If cross-service logic is needed, e.g., to check order status before allowing evaluation:
        # self.order_service = order_service 

    async def create_evaluation(
        self,
        conn: pyodbc.Connection,
        evaluation_data: EvaluationCreateSchema,
        buyer_id: UUID
    ) -> EvaluationResponseSchema:
        """
        Creates a new evaluation for an order.

        Args:
            conn: The database connection object.
            evaluation_data: Data for creating the evaluation (order_id, rating, comment).
            buyer_id: The ID of the user (buyer) submitting the evaluation.

        Returns:
            The created evaluation details.

        Raises:
            DALError: If there's an issue with database interaction.
            NotFoundError: If the order to be evaluated is not found.
            ValueError: If input data is invalid (e.g., rating out of range).
            ForbiddenError: If the user is not authorized to evaluate the order (e.g., not the buyer).
            IntegrityError: If the order has already been evaluated.
        """
        try:
            # --- Business Logic Pre-checks (Examples) ---
            # 1. Check if the order exists and if the buyer_id matches the order's buyer.
            #    This might require an OrderService or direct DAL call to fetch order details.
            #    order = await self.order_service.get_order_by_id_internal(conn, evaluation_data.order_id)
            #    if not order:
            #        raise NotFoundError(f"Order with ID {evaluation_data.order_id} not found.")
            #    if order.buyer_id != buyer_id:
            #        raise ForbiddenError("You are not authorized to evaluate this order.")
            #    if order.status != "Completed": # Or whatever status allows evaluation
            #        raise ValueError("Order cannot be evaluated in its current state.")

            # 2. Check if the order has already been evaluated by this buyer.
            #    This might require a new DAL method: evaluation_dal.get_evaluation_by_order_and_buyer()
            #    existing_evaluation = await self.evaluation_dal.get_evaluation_by_order_and_buyer(conn, evaluation_data.order_id, buyer_id)
            #    if existing_evaluation:
            #        raise ValueError("This order has already been evaluated by you.")
            
            # 1. Validate rating (e.g., 1-5). Pydantic schema handles this, but service layer can add extra validation.
            if not (1 <= evaluation_data.rating <= 5):
                # Although Pydantic schema has gt/le, this ensures robust service-level validation.
                raise ValueError("评分必须在 1 到 5 之间。")

            # Call DAL to execute sp_CreateEvaluation
            # sp_CreateEvaluation might not return the created evaluation ID or details directly.
            # It might just perform the insert and raise SQL errors for issues.
            # Assuming DAL's create_evaluation returns the newly created evaluation ID or the full dictionary
            # If it returns the ID, fetch the full evaluation:
            new_evaluation_data = await self.evaluation_dal.create_evaluation(
                conn=conn,
                order_id=evaluation_data.order_id,
                buyer_id=buyer_id, # Pass the authenticated buyer_id
                rating=evaluation_data.rating,
                comment=evaluation_data.comment
            )

            # The DAL's create_evaluation should ideally return the full evaluation data, including the generated ID.
            # If it returns the ID only, you would fetch it here:
            # created_evaluation_id = created_evaluation_data.get('EvaluationID')
            # if not created_evaluation_id:
            #      raise DALError("Evaluation creation failed: Could not retrieve new evaluation ID.")
            #
            # evaluation = await self.evaluation_dal.get_evaluation_by_id(conn, UUID(created_evaluation_id))
            # if not evaluation:
            #     raise NotFoundError("Evaluation not found after creation.")
            # return evaluation

            # DAL's create_evaluation now returns the full evaluation dictionary on success.
            if not new_evaluation_data or not isinstance(new_evaluation_data, dict):
                raise DALError("Evaluation creation failed: Unexpected response from database.")

            # Convert the dictionary result to the EvaluationResponseSchema
            return EvaluationResponseSchema(**new_evaluation_data)

        except (NotFoundError, ValueError, ForbiddenError, IntegrityError, DALError): # Catch IntegrityError here
            raise # Re-raise specific business logic or DAL errors
        except Exception as e:
            raise DALError(f"创建评价时发生意外错误: {e}") from e

    async def get_evaluations_by_product_id(
        self,
        conn: pyodbc.Connection,
        product_id: UUID
    ) -> List[EvaluationResponseSchema]:
        """获取指定商品的评价列表。"""
        evaluations_data = await self.evaluation_dal.get_evaluations_by_product_id(conn, product_id)
        return [EvaluationResponseSchema(**e) for e in evaluations_data]

    async def get_evaluations_by_buyer_id(
        self,
        conn: pyodbc.Connection,
        buyer_id: UUID
    ) -> List[EvaluationResponseSchema]:
        """获取指定买家的评价列表。"""
        evaluations_data = await self.evaluation_dal.get_evaluations_by_buyer_id(conn, buyer_id)
        return [EvaluationResponseSchema(**e) for e in evaluations_data]

    async def get_evaluation_by_id(
        self,
        conn: pyodbc.Connection,
        evaluation_id: UUID
    ) -> Optional[EvaluationResponseSchema]:
        """根据评价ID获取评价详情。"""
        evaluation_data = await self.evaluation_dal.get_evaluation_by_id(conn, evaluation_id)
        if evaluation_data:
            return EvaluationResponseSchema(**evaluation_data)
        return None

    # Potentially, add other methods like:
    # async def get_evaluations_for_order(self, conn: pyodbc.Connection, order_id: int) -> List[EvaluationResponseSchema]: ...
    # async def get_evaluations_by_user(self, conn: pyodbc.Connection, user_id: UUID) -> List[EvaluationResponseSchema]: ...
    # async def get_evaluation_by_id(self, conn: pyodbc.Connection, evaluation_id: int) -> Optional[EvaluationResponseSchema]: ...

# Note:
# 1. Pydantic Schemas (EvaluationCreateSchema, EvaluationResponseSchema) need to be defined in `app.schemas.evaluation_schemas.py`.
# 2. EvaluationDAL needs to be implemented in `app.dal.evaluation_dal.py` with a `create_evaluation` method that calls `sp_CreateEvaluation`.
# 3. The `create_evaluation` method in `EvaluationDAL` should ideally handle the retrieval of the newly created evaluation's ID if the SP supports it (e.g., via OUTPUT clause or SCOPE_IDENTITY()).
# 4. Business logic for pre-checks (e.g., order status, ensuring user is the buyer, checking if already evaluated) should be implemented thoroughly, potentially involving other services or DAL methods.
# 5. The example `EvaluationResponseSchema` construction in `create_evaluation` is a placeholder and depends on how the created evaluation's data (especially ID and timestamp) is obtained.