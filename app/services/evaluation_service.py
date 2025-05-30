import pyodbc
from uuid import UUID
from typing import Optional, List # Added List for potential future methods

from app.dal.evaluation_dal import EvaluationDAL # Assuming EvaluationDAL is in app.dal.evaluation_dal
from app.schemas.evaluation_schemas import ( # Assuming evaluation-related Pydantic schemas are in app.schemas.evaluation_schemas
    EvaluationCreateSchema,
    EvaluationResponseSchema
)
# If needed, import Order related schemas or services for validation (e.g., to check if order can be evaluated)
# from app.services.order_service import OrderService 
from app.exceptions import DALError, NotFoundError, ForbiddenError # 移除 ValueError

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
    ) -> EvaluationResponseSchema: # Assuming sp_CreateEvaluation doesn't return the full object, so we might need a get after create
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
            ValueError: If input data is invalid (e.g., rating out of range, order already evaluated).
            ForbiddenError: If the user is not authorized to evaluate the order (e.g., not the buyer).
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
            
            # 3. Validate rating (e.g., 1-5). Pydantic schema might handle this, but good to have service layer validation too.
            if not (1 <= evaluation_data.rating <= 5):
                raise ValueError("Rating must be between 1 and 5.") # 这里直接使用内置的 ValueError

            # Call DAL to execute sp_CreateEvaluation
            # sp_CreateEvaluation might not return the created evaluation ID or details directly.
            # It might just perform the insert and raise SQL errors for issues.
            await self.evaluation_dal.create_evaluation(
                conn=conn,
                order_id=evaluation_data.order_id,
                buyer_id=buyer_id, # Pass the authenticated buyer_id
                rating=evaluation_data.rating,
                comment=evaluation_data.comment
            )

            # If sp_CreateEvaluation doesn't return the ID, and you need to return the full EvaluationResponseSchema,
            # you'd need a way to retrieve it. This could be tricky if there's no unique ID returned.
            # For now, let's assume the task is just to create and not necessarily return the full object,
            # or that the DAL method is adapted to fetch it (e.g., using SCOPE_IDENTITY() if it's an auto-increment ID).
            # If an ID is returned or can be fetched:
            # created_eval_id = ... 
            # evaluation = await self.evaluation_dal.get_evaluation_by_id(conn, created_eval_id)
            # if not evaluation:
            #     raise NotFoundError("Evaluation not found after creation.")
            # return evaluation
            
            # For simplicity, if sp_CreateEvaluation doesn't return data for EvaluationResponseSchema,
            # we might need to adjust the return type or how it's constructed.
            # A common pattern is for the SP to output the ID, then fetch.
            # If the SP only confirms success/failure via error, the service might return a simpler success message or the input data.
            # Let's construct a conceptual response based on input, assuming success if no error.
            # This is a placeholder; a real implementation would need a robust way to get the created entity.
            return EvaluationResponseSchema(
                evaluation_id=-1, # Placeholder, should be the actual ID from DB
                order_id=evaluation_data.order_id,
                buyer_id=buyer_id,
                rating=evaluation_data.rating,
                comment=evaluation_data.comment,
                created_at="..." # Placeholder, should be actual timestamp
            )

        except pyodbc.Error as db_err:
            # Log db_err
            # Specific SQL errors from sp_CreateEvaluation (e.g., order not found, already evaluated) might be caught here.
            # These could be translated into more specific service exceptions.
            raise DALError(f"Database error during evaluation creation: {db_err}") from db_err
        except (NotFoundError, ValueError, ForbiddenError, DALError): # 这里也直接使用内置的 ValueError
            raise # Re-raise specific business logic or DAL errors
        except Exception as e:
            # Log e
            raise DALError(f"An unexpected error occurred during evaluation creation: {e}") from e

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