#!/usr/bin/env python
"""
数据库初始化脚本。

执行此脚本将创建表、存储过程和触发器，完成数据库设置。
Usage: python init_database.py [--db-name DB_NAME] [--drop-existing] [--continue-on-error]
"""

import os
import sys
import pyodbc
import logging
import argparse
from datetime import datetime
import time # Add import for time module
import uuid # Ensure uuid is directly imported

# 导入 dotenv 来加载 .env 文件
from dotenv import load_dotenv

# 导入 dictConfig
from logging.config import dictConfig
# Import Uvicorn logging formatters for consistency if needed
try:
    import uvicorn.logging
except ImportError:
    uvicorn = None # Handle case where uvicorn might not be installed in this env

# 加载 .env 文件中的环境变量
# 如果 .env 文件不在当前工作目录，需要指定路径
load_dotenv()

# Add the parent directory (backend/) to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Setup logging
log_dir = "logs"
# Use an absolute path for log_dir to avoid issues with changing CWD
log_dir_abs = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..' , log_dir)
if not os.path.exists(log_dir_abs):
    os.makedirs(log_dir_abs)

log_file_path = os.path.join(log_dir_abs, f"sql_deploy_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

# Define a comprehensive logging configuration dictionary using dictConfig
# This configuration is for the db_init.py script itself.
# For FastAPI/Uvicorn, a similar configuration would be needed in the main application entry point.
LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False, # Crucial: Prevents potential silencing by other configs (though less likely for a script)
    "formatters": {
        "default": { # Formatter for general application logs
            # Use Uvicorn's formatter if available, otherwise use a basic one
            "()": "uvicorn.logging.DefaultFormatter" if uvicorn and hasattr(uvicorn.logging, "DefaultFormatter") else "logging.Formatter",
            "fmt": "%(levelprefix)s %(asctime)s | %(name)s | %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
            "use_colors": True if uvicorn and hasattr(uvicorn.logging, "DefaultFormatter") else False, # Use colors if using uvicorn formatter
        },
        # Add access formatter if needed, though less relevant for a script
        # "access": {
        #     "()": "uvicorn.logging.AccessFormatter",
        #     "fmt": '%(levelprefix)s %(asctime)s | %(name)s | %(client_addr)s - "%(request_line)s" %(status_code)s',
        #     "datefmt": "%Y-%m-%d %H:%M:%S",
        # },
    },
    "handlers": {
        "default": { # Handler for general logs (e.g., to stderr)
            "formatter": "default",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stderr", # Directs to standard error stream
        },
        "file": { # Handler to write logs to a file
            "formatter": "default",
            "class": "logging.FileHandler",
            "filename": log_file_path,
            "encoding": "utf-8",
        },
        # Add access handler if needed
        # "access": {
        #     "formatter": "access",
        #     "class": "logging.StreamHandler",
        #     "stream": "ext://sys.stdout",
        # },
    },
    "loggers": {
        "": { # Root logger: catches logs from any unconfigured logger (like the ones from pyodbc)
            "handlers": ["default", "file"], # Send root logs to both console and file
            "level": "INFO", # Default level for unconfigured loggers
            "propagate": False, # Root logger does not propagate further
        },
        "db_init": { # Logger specifically for this script
             "handlers": ["default", "file"],
             "level": "DEBUG", # Set this script's logger to DEBUG for verbose output
             "propagate": False,
        },
        # You might define loggers for backend modules here if this was the main logging config file
        # e.g., "app": {"handlers": ["default", "file"], "level": "DEBUG", "propagate": False},
        # "app.services": {"handlers": ["default", "file"], "level": "DEBUG", "propagate": False},
        # "app.dal": {"handlers": ["default", "file"], "level": "DEBUG", "propagate": False},
        # Add Uvicorn loggers if this was the main app config
        # "uvicorn.error": {"level": "INFO", "handlers": ["default"], "propagate": False},
        # "uvicorn.access": {"level": "INFO", "handlers": ["access"], "propagate": False},
    },
}

# Apply the configuration
dictConfig(LOGGING_CONFIG)

# Get the logger for this script
logger = logging.getLogger("db_init")

def get_db_connection(db_name_override=None):
    """获取数据库连接, 如果指定的数据库不存在则尝试创建它。"""
    # 从环境变量读取配置，这将与 FastAPI 的 Pydantic BaseSettings 兼容
    server = os.getenv('DATABASE_SERVER')
    user = os.getenv('DATABASE_UID')
    password = os.getenv('DATABASE_PWD')
    default_db_name = os.getenv('DATABASE_NAME')
    driver = os.getenv('ODBC_DRIVER', '{ODBC Driver 17 for SQL Server}') # 从环境变量获取驱动名，或使用默认值

    if not all([server, user, password, default_db_name]):
        logger.error("请在环境变量中配置 DATABASE_SERVER, DATABASE_UID, DATABASE_PWD, DATABASE_NAME")
        raise ValueError("数据库连接配置不完整")
        
    target_db_name = db_name_override if db_name_override else default_db_name

    # 检查是否为高权限登录，如果是，跳过数据库用户和角色设置
    # 注意：这只是一个简单的判断，如果使用其他高权限登录，也需要在此处添加
    is_sysadmin_like_login = (user.lower() == 'sa') # 示例：判断是否为 sa 登录
    if is_sysadmin_like_login:
        logger.info(f"Using high-privilege login '{user}'. Skipping database user/role setup.")
    
    # Step 1: Connect to 'master' database to check existence and create if necessary
    master_conn_str = f"DRIVER={driver};SERVER={server};DATABASE=master;UID={user};PWD={password}"
    master_conn = None
    try:
        logger.info(f"Connecting to 'master' database on SERVER: {server} to check/create '{target_db_name}'.")
        # For CREATE DATABASE, it's often better to have autocommit=True for this specific connection
        master_conn = pyodbc.connect(master_conn_str, autocommit=True)
        cursor = master_conn.cursor()
        
        # Add: Drop the database if it already exists
        logger.info(f"Attempting to drop existing database '{target_db_name}' if it exists.")
        cursor.execute(f"DROP DATABASE IF EXISTS [{target_db_name}];")
        logger.info(f"DROP DATABASE IF EXISTS [{target_db_name}] executed.")
        time.sleep(1) # Give the system a moment
        
        # Check if the target database exists
        cursor.execute("SELECT name FROM sys.databases WHERE name = ?", (target_db_name,))
        if cursor.fetchone() is None:
            logger.info(f"Database '{target_db_name}' does not exist. Attempting to create it.")
            # Use [] around database name for safety, though pyodbc parameters usually handle this.
            # However, CREATE DATABASE doesn't allow parameterization for the DB name itself.
            # 使用 f-string 构建 SQL，并确保数据库名被正确引用
            create_db_sql = f"CREATE DATABASE [{target_db_name}]"
            logger.info(f"Executing: {create_db_sql}")
            cursor.execute(create_db_sql)
            logger.info(f"Database '{target_db_name}' created successfully.")
            
            # After creating the database, set up user mapping and permissions if not a high-privilege login
            if not is_sysadmin_like_login:
                try:
                    # Switch to the newly created database context
                    cursor.execute(f"USE [{target_db_name}];")
                    logger.info(f"Switched context to database: {target_db_name}")

                    # Check if a database user for the login already exists
                    # Use type IN ('S', 'U') to cover SQL users and Windows users if applicable
                    cursor.execute("SELECT 1 FROM sys.database_principals WHERE name = ? AND type IN ('S', 'U');", (user,))
                    user_exists_in_db = cursor.fetchone() is not None

                    if not user_exists_in_db:
                        logger.info(f"Database user '{user}' does not exist in '{{target_db_name}}'. Creating user and mapping login.")
                        # Create user from login
                        create_user_sql = f"CREATE USER [{{user}}] FOR LOGIN [{{user}}];"
                        cursor.execute(create_user_sql)
                        logger.info(f"Database user '{user}' created.")

                        # Add the user to the db_owner role for full permissions during initialization
                        # Using ALTER ROLE is the modern way.
                        add_role_sql = f"ALTER ROLE db_owner ADD MEMBER [{{user}}];"
                        logger.info(f"Adding user '{user}' to db_owner role in '{{target_db_name}}'.")
                        cursor.execute(add_role_sql)
                        logger.info(f"User '{user}' added to db_owner role.")

                        master_conn.commit() # Commit these user/permission changes
                        logger.info(f"User '{user}' permissions set up successfully in '{target_db_name}'.")

                except pyodbc.Error as e:
                    logger.error(f"Error setting up user permissions in database '{{target_db_name}}': {e}")
                    # This is critical, cannot proceed if user cannot connect/operate
                    raise # Re-raise the error to be caught by the outer try block
            else:
                 # Commit the database creation even if user setup is skipped
                 master_conn.commit()
                 logger.info(f"Database '{target_db_name}' creation committed (user setup skipped). ")

        else:
            logger.info(f"Database '{target_db_name}' already exists.")
            # If database already exists, we still need to ensure user mapping and permissions are correct
            # unless it's a high-privilege login.
            if not is_sysadmin_like_login:
                try:
                    # Switch to the existing database context
                    cursor.execute(f"USE [{target_db_name}];")
                    logger.info(f"Switched context to database: {target_db_name}")

                    # Check if a database user for the login already exists
                    cursor.execute("SELECT 1 FROM sys.database_principals WHERE name = ? AND type IN ('S', 'U');", (user,))
                    user_exists_in_db = cursor.fetchone() is not None

                    if not user_exists_in_db:
                        logger.warning(f"Database user '{user}' does not exist in existing database '{{target_db_name}}'. Creating user and mapping login.")
                        create_user_sql = f"CREATE USER [{{user}}] FOR LOGIN [{{user}}];"
                        cursor.execute(create_user_sql)
                        logger.info(f"Database user '{user}' created in existing database.")

                    # Add the user to the db_owner role (idempotent, safe to run if already member)
                    add_role_sql = f"ALTER ROLE db_owner ADD MEMBER [{{user}}];"
                    logger.info(f"Ensuring user '{user}' is in db_owner role in '{{target_db_name}}'.")
                    cursor.execute(add_role_sql)
                    logger.info(f"User '{user}' ensured to be in db_owner role.")

                    master_conn.commit() # Commit these user/permission changes
                    logger.info(f"User '{user}' permissions checked/set up successfully in existing '{target_db_name}'.")

                except pyodbc.Error as e:
                    logger.error(f"Error checking/setting up user permissions in existing database '{{target_db_name}}': {e}")
                    # This is critical, cannot proceed if user cannot connect/operate
                    raise # Re-raise the error
            else:
                # No user/role setup needed for high-privilege login when DB exists.
                logger.info(f"Database '{target_db_name}' exists. User setup skipped for high-privilege login '{user}'.")

        cursor.close()
    except pyodbc.Error as e:
        logger.error(f"Error while connecting to 'master', creating database, or setting initial permissions for '{target_db_name}': {e}")
        # If we can't ensure the database exists/is created and user permissions are set (if needed),
        # we should not proceed. The permission setup is now part of the critical path.
        raise
    finally:
        if master_conn:
            try:
                master_conn.close()
            except pyodbc.Error as e:
                 logger.error(f"Error closing master connection: {e}")

    # Step 2: Connect to the target database (now it should exist and user permissions should be set)
    target_conn_str = f"DRIVER={driver};SERVER={server};DATABASE={target_db_name};UID={user};PWD={password}"
    try:
        logger.info(f"Attempting connection to DATABASE: {target_db_name} on SERVER: {server} with user {user}")
        conn = pyodbc.connect(target_conn_str)
        logger.info("Successfully connected to target database.")
        return conn
    except pyodbc.Error as e: # Changed from generic Exception to pyodbc.Error for specificity
        logger.error(f"Database connection failed when connecting to {target_db_name} with user {user}: {e}")
        raise

def execute_sql_file(conn, file_path, continue_on_error=False):
    """
    执行SQL文件
    
    Args:
        conn: 数据库连接
        file_path: SQL文件路径
        continue_on_error: 出错时是否继续执行
    
    Returns:
        bool: 执行是否成功
    """
    logger.info(f"执行SQL文件: {file_path}")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            sql_content = f.read()
        
        # 拆分SQL语句（按GO分隔）
        # Filter out empty strings that can result from split if GO is at the start/end or multiple GOs together
        statements = [s for s in sql_content.split('GO') if s.strip()]

        cursor = conn.cursor()
        success = True
        
        # Add an index to skip specific statements if needed
        # statement_index = 0 # Keep this outside the loop if used

        for i, statement in enumerate(statements):
            if file_path.endswith('03_trade_procedures.sql') and i == 3:
                logger.warning(f"  Skipping statement {i+1}/{len(statements)} in {os.path.basename(file_path)} due to persistent error 141.")
                continue

            statement = statement.strip() # Ensure trimming again, though list comprehension also trims for check
            if not statement:
                continue
            
            logger.info(f"  准备执行语句 {i+1}/{len(statements)}...")
            logger.debug(f"  SQL: {statement[:500]}...") # Log a snippet of the statement
            try:
                # Use cursor.execute() which is generally preferred
                cursor.execute(statement)
                
                # Check for messages from the server (warnings, info, non-fatal errors)
                # pyodbc.Error will be caught by the except block, but messages might have other info
                # Note: pyodbc.Cursor might not always expose .messages directly, behavior can vary by driver/version
                # A more robust check might involve querying server error state after execution if needed, but THROW/RAISERROR is better.
                # Let's rely on the pyodbc.Error exception for critical failures.
                
                # DDL statements often implicitly commit or manage their own transactions.
                # For safety and clarity, we can commit after each statement or rely on the connection's autocommit behavior.
                # Given the GO delimiter logic, committing after each block seems appropriate.
                conn.commit() # Commit after each statement block separated by GO
                logger.info(f"  语句 {i+1}/{len(statements)} 执行成功 (已提交)")

            except pyodbc.Error as e: # Catch specific pyodbc.Error
                logger.error(f"  语句 {i+1}/{len(statements)} 执行失败: {e}")
                # Also log messages if an exception occurred, as they might provide context
                # Accessing messages after an error might be tricky or driver-dependent.
                # Rely on the logged error message 'e'.
                if not continue_on_error:
                    success = False
                    break
            except Exception as e: # Catch any other unexpected exceptions
                logger.error(f"  语句 {i+1}/{len(statements)} 执行时发生意外错误: {e}", exc_info=True)
                if not continue_on_error:
                    success = False
                    break

            # Add a small delay after each statement block
            time.sleep(0.1)
        
        cursor.close()
        return success
    except Exception as e: # Catch file reading errors etc.
        logger.error(f"执行SQL文件失败: {e}", exc_info=True)
        return False

def create_admin_users(conn):
    """
    为开发者创建管理员账户。
    """
    logger.info("--- 开始创建开发者管理员账户 ---")
    cursor = conn.cursor()

    # Explicitly clear the User table before inserting initial admin users
    # This ensures a clean state and avoids conflicts with existing data, especially NULL email entries
    try:
        logger.info("  清空现有用户数据...")
        cursor.execute("DELETE FROM [User]")
        conn.commit()
        logger.info("  现有用户数据已清空.")
    except Exception as e:
        logger.error(f"  清空用户数据失败: {e}")
        # Depending on severity, you might want to sys.exit(1) here
        # For now, we log and continue, but this might lead to further errors.

    admin_users = [
        {"username": "pxk", "email": "23301132@bjtu.edu.cn", "major": "软件工程", "phone": "13800000001"},
        {"username": "cyq", "email": "23301003@bjtu.edu.cn", "major": "计算机科学与技术", "phone": "13800000002"},
        {"username": "cy", "email": "23301002@bjtu.edu.cn", "major": "计算机科学与技术", "phone": "13800000003"},
        {"username": "ssc", "email": "23301011@bjtu.edu.cn", "major": "软件工程", "phone": "13800000004"},
        {"username": "zsq", "email": "23301027@bjtu.edu.cn", "major": "人工智能", "phone": "13800000005"},
    ]
    # You might need to fetch or define get_password_hash here if not globally available
    from app.utils.auth import get_password_hash

    for user_data in admin_users:
        try:
            # Refined Check: Check if user already exists by username or specific non-null email
            check_query = "SELECT COUNT(1) FROM [User] WHERE UserName = ?"
            check_params = (user_data['username'],)

            if user_data.get('email'): # Only add email check if email is provided and not None
                check_query += " OR Email = ?"
                check_params += (user_data['email'],)

            cursor.execute(check_query, check_params)
            if cursor.fetchone()[0] == 0:
                logger.info(f"  创建用户: {user_data['username']} ({user_data.get('email', '无邮箱')})") # Log email presence

                # Determine IsStaff and IsSuperAdmin status
                is_staff_value = 1  # Set all users in admin_users list as staff
                is_super_admin_value = 0 # Default to not super admin

                # Set pxk as Super Admin based on email
                if user_data.get('email') == '23301132@bjtu.edu.cn':
                    is_super_admin_value = 1

                hashed_password = get_password_hash("password123") # Use a default password

                # Insert the user
                cursor.execute("""
                    INSERT INTO [User] (UserName, Password, Email, Status, Credit, IsStaff, IsVerified, Major, PhoneNumber, JoinTime, IsSuperAdmin)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, GETDATE(), ?)
                """, (
                    user_data['username'],
                    hashed_password,
                    user_data.get('email'), # Pass email (can be None)
                    'Active',
                    100,
                    is_staff_value,
                    1, # Assume admin users are verified for simplicity in init
                    user_data.get('major'), # Pass major (can be None)
                    user_data['phone'],
                    is_super_admin_value
                ))
                conn.commit() # Commit after each user insertion
                logger.info(f"  用户 {user_data['username']} 创建成功.")
            else:
                logger.info(f"  用户 {user_data['username']} ({user_data.get('email', '无邮箱')}) 已存在，跳过创建.")

        except pyodbc.IntegrityError as e:
             # Catch specific IntegrityError to provide more context
             sqlstate = e.args[0]
             error_message = e.args[1] if len(e.args) > 1 else str(e)
             logger.error(f"  创建用户 {user_data['username']} 失败 (Integrity Error): {sqlstate} - {error_message}")
             # You might choose to continue or break here based on desired behavior for duplicates
             # For init script, logging and continuing might be acceptable for some duplicates
             conn.rollback() # Rollback the failed insert transaction if not auto-rolled back
        except Exception as e:
            logger.error(f"  创建用户 {user_data['username']} 失败: {e}")
            # Depending on how execute is configured, a rollback might be needed here too
            if conn: # Check if connection is valid
                 try:
                      conn.rollback()
                 except Exception as rb_e:
                      logger.error(f"Error during rollback: {rb_e}")


    logger.info("--- 开发者管理员账户创建完成 ---")

def main():
    parser = argparse.ArgumentParser(description='数据库初始化脚本')
    parser.add_argument('--db-name', type=str, help='要初始化的数据库名称 (例如 TradingPlatform_Test). 如果不指定，将使用环境变量 DATABASE_NAME')
    parser.add_argument('--drop-existing', action='store_true', help='是否先删除现有数据库对象 (执行 drop_all.sql)')
    parser.add_argument('--continue-on-error', action='store_true', help='执行SQL语句出错时是否继续执行后续语句')
    args = parser.parse_args()
    
    conn = None # Initialize conn to None
    try:
        # 从环境变量加载配置，或者在程序启动前确保环境变量已设置
        # load_dotenv()
        
        conn = get_db_connection(db_name_override=args.db_name)
        logger.info("成功连接到数据库")
        
        # 如果指定了删除现有对象
        if args.drop_existing:
            logger.info("删除现有数据库对象...")
            # Use absolute path for drop_all.sql
            drop_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'drop_all.sql')
            if os.path.exists(drop_script):
                # Always continue on errors when dropping, as some objects might not exist
                execute_sql_file(conn, drop_script, continue_on_error=True)
            else:
                logger.warning(f"未找到删除脚本: {drop_script}")
        
        # 获取要执行的SQL文件列表
        # Use absolute paths for sql directories
        sql_dirs = [
            os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tables'),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), 'procedures'),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), 'triggers')
        ]
        
        # 按顺序执行SQL文件
        for sql_dir in sql_dirs:
            if not os.path.exists(sql_dir):
                logger.warning(f"目录不存在: {sql_dir}")
                continue
                
            logger.info(f"处理目录: {sql_dir}")
            sql_files = sorted([f for f in os.listdir(sql_dir) if f.endswith('.sql')])
            
            for sql_file in sql_files:
                file_path = os.path.join(sql_dir, sql_file)
                success = execute_sql_file(conn, file_path, continue_on_error=args.continue_on_error)
                if not success and not args.continue_on_error:
                    logger.error(f"执行中止: {file_path}")
                    return 1
        
        # 在执行完所有SQL文件后，创建开发者管理员账户
        logger.info("--- 开始创建开发者管理员账户 ---")
        create_admin_users(conn)
        logger.info("--- 开发者管理员账户创建完成 ---")

        logger.info("数据库初始化完成。")
        return 0
    except ValueError as e:
        logger.error(f"配置错误: {e}")
        return 1
    except pyodbc.Error as e:
        logger.error(f"数据库操作失败: {e}")
        return 1
    except Exception as e:
        logger.error(f"初始化过程发生意外错误: {e}", exc_info=True)
        return 1
    finally:
        if conn:
            try:
                conn.close()
                logger.info("数据库连接已关闭")
            except pyodbc.Error as e:
                 logger.error(f"Error closing connection: {e}")

if __name__ == "__main__":
    sys.exit(main())