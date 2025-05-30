import pyodbc
from typing import Optional, Callable, Awaitable
from uuid import UUID

from app.exceptions import DALError

class EvaluationDAL:
    """Data Access Layer for Evaluations."""

    def __init__(self, execute_query_func: Callable[..., Awaitable[Optional[list[tuple]]]]) -> None:
        """
        Initializes the EvaluationDAL with an asynchronous query execution function.

        Args:
            execute_query_func: An asynchronous function to execute database queries.
                                It should accept a SQL query string and parameters, 
                                and return an optional list of tuples (rows).
        """
        self.execute_query = execute_query_func

    async def create_evaluation(
        self,
        conn: pyodbc.Connection, 
        order_id: int,
        buyer_id: UUID,
        rating: int,
        comment: Optional[str]
    ) -> None:
        """
        Creates a new evaluation for an order by calling the sp_CreateEvaluation stored procedure.

        Args:
            conn: The database connection object.
            order_id: The ID of the order being evaluated.
            buyer_id: The ID of the buyer submitting the evaluation.
            rating: The rating given by the buyer (1-5).
            comment: Optional comment from the buyer.

        Raises:
            DALError: If the stored procedure execution fails.
        """
        sql = "EXEC sp_CreateEvaluation @OrderID=?, @BuyerID=?, @Rating=?, @Comment=?"
        params = (order_id, str(buyer_id), rating, comment)
        
        try:
            async with conn.cursor() as cursor:
                await cursor.execute(sql, params)
            # No rows are returned by sp_CreateEvaluation for successful execution
            # The stored procedure handles its own transaction commit/rollback and error raising.
        except pyodbc.Error as e:
            # Log the error e
            # Convert pyodbc.Error to a more generic DALError or a specific one
            # The sp_CreateEvaluation procedure itself raises errors for business logic violations (e.g., order not found, already evaluated)
            # Those errors will be caught here if they are SQL Server errors (e.g., RAISERROR with severity > 10)
            error_message = f"Database error during evaluation creation for order {order_id}: {e}"
            # Consider logging the full error details here
            raise DALError(error_message) from e
        except Exception as e:
            # Catch any other unexpected errors
            error_message = f"An unexpected error occurred while creating evaluation for order {order_id}: {e}"
            # Consider logging the full error details here
            raise DALError(error_message) from e

# Example of how this DAL might be used (typically in a Service layer):
# async def example_usage(db_conn_provider, order_id, buyer_id, rating, comment):
#     async with db_conn_provider as conn:
#         # Assuming execute_query_func is somehow available or conn itself is used directly
#         # For this example, we'll assume the DAL is instantiated with a function that uses the conn
#         async def _execute_query(sql_query, sql_params):
#             async with conn.cursor() as cursor:
#                 await cursor.execute(sql_query, *sql_params)
#                 # Adapt based on whether results are expected or not
#                 try:
#                     return await cursor.fetchall()
#                 except pyodbc.ProgrammingError: # No results
#                     return None

#         evaluation_dal = EvaluationDAL(execute_query_func=_execute_query) # Simplified for example
#         # Or, more directly if the DAL method uses conn directly:
#         # evaluation_dal = EvaluationDAL(None) # If execute_query_func is not used by the method

#         try:
#             await evaluation_dal.create_evaluation(conn, order_id, buyer_id, rating, comment)
#             print(f"Evaluation created successfully for order {order_id}.")
#         except DALError as e:
#             print(f"Failed to create evaluation: {e}")