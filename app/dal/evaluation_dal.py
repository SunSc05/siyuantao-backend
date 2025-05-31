import pyodbc
from typing import Optional, Callable, Awaitable, List, Dict, Any
from uuid import UUID

from app.exceptions import DALError, NotFoundError, IntegrityError, ForbiddenError

class EvaluationDAL:
    """Data Access Layer for Evaluations."""

    def __init__(self, execute_query_func: Callable[..., Awaitable[Optional[list[tuple]] | Optional[Dict[str, Any]] | Optional[List[Dict[str, Any]]]]]) -> None:
        """
        Initializes the EvaluationDAL with an asynchronous query execution function.

        Args:
            execute_query_func: An asynchronous function to execute database queries.
                                It should accept a SQL query string and parameters, 
                                and return an optional list of tuples (rows).
        """
        self._execute_query = execute_query_func

    async def create_evaluation(
        self,
        conn: pyodbc.Connection, 
        order_id: UUID,
        buyer_id: UUID,
        rating: int,
        comment: Optional[str]
    ) -> Dict[str, Any]:
        """
        Creates a new evaluation for an order by calling the sp_CreateEvaluation stored procedure.
        Assumes sp_CreateEvaluation is modified to SELECT the newly created evaluation data.
        """
        sql = "{CALL sp_CreateEvaluation (?, ?, ?, ?)}"
        params = (str(order_id), str(buyer_id), rating, comment)

        try:
            result = await self._execute_query(conn, sql, params, fetchone=True)
            if not result or result.get("EvaluationID") is None:
                raise DALError("创建评价失败，未返回评价ID")
            return result
        except pyodbc.Error as e:
            error_msg = str(e)
            if "50001" in error_msg:
                raise NotFoundError(f"评价创建失败: {error_msg}") from e
            elif "50002" in error_msg:
                raise IntegrityError(f"评价创建失败: {error_msg}") from e
            elif "50003" in error_msg:
                raise ForbiddenError(f"评价创建失败: {error_msg}") from e
            raise DALError(f"评价创建异常: {error_msg}") from e
        except Exception as e:
            raise DALError(f"评价创建时发生意外错误: {e}") from e

    async def get_evaluation_by_id(
        self,
        conn: pyodbc.Connection,
        evaluation_id: UUID
    ) -> Optional[Dict[str, Any]]:
        """Fetches a single evaluation by its ID."""
        sql = "{CALL sp_GetEvaluationById (?)}"
        params = (str(evaluation_id),)
        try:
            result = await self._execute_query(conn, sql, params, fetchone=True)
            return result
        except pyodbc.Error as e:
            error_msg = str(e)
            raise DALError(f"获取评价失败: {error_msg}") from e
        except Exception as e:
            raise DALError(f"获取评价时发生意外错误: {e}") from e

    async def get_evaluations_by_product_id(
        self,
        conn: pyodbc.Connection,
        product_id: UUID
    ) -> List[Dict[str, Any]]:
        """Fetches all evaluations for a specific product."""
        sql = "{CALL sp_GetEvaluationsByProductId (?)}"
        params = (str(product_id),)
        try:
            results = await self._execute_query(conn, sql, params, fetchall=True)
            return results
        except pyodbc.Error as e:
            error_msg = str(e)
            raise DALError(f"获取商品评价失败: {error_msg}") from e
        except Exception as e:
            raise DALError(f"获取商品评价时发生意外错误: {e}") from e

    async def get_evaluations_by_buyer_id(
        self,
        conn: pyodbc.Connection,
        buyer_id: UUID
    ) -> List[Dict[str, Any]]:
        """Fetches all evaluations made by a specific buyer."""
        sql = "{CALL sp_GetEvaluationsByBuyerId (?)}"
        params = (str(buyer_id),)
        try:
            results = await self._execute_query(conn, sql, params, fetchall=True)
            return results
        except pyodbc.Error as e:
            error_msg = str(e)
            raise DALError(f"获取买家评价失败: {error_msg}") from e
        except Exception as e:
            raise DALError(f"获取买家评价时发生意外错误: {e}") from e

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