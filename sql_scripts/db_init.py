#!/usr/bin/env python
"""
数据库初始化脚本。

执行此脚本将创建表、存储过程和触发器，完成数据库设置。
Usage: python init_database.py
"""

import os
import sys
import pyodbc
import logging
import argparse
from datetime import datetime
from django.conf import settings

# 将项目根目录添加到Python路径
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(BASE_DIR)

# 初始化Django设置
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tradingPlatform.settings')
import django
django.setup()

# Setup logging
log_dir = "logs"
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

log_file_path = os.path.join(log_dir, f"sql_deploy_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file_path),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def get_db_connection(db_name_override=None):
    """获取数据库连接, 如果指定的数据库不存在则尝试创建它。"""
    # Load Django settings if not already configured
    if not settings.configured:
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tradingPlatform.settings')
        django.setup()

    db_settings = settings.DATABASES['default']
    driver = db_settings['OPTIONS']['driver']
    server = db_settings['HOST']
    user = db_settings['USER']
    password = db_settings['PASSWORD']
    
    target_db_name = db_name_override if db_name_override else db_settings['NAME']
    
    # Step 1: Connect to 'master' database to check existence and create if necessary
    master_conn_str = f"DRIVER={{{driver}}};SERVER={server};DATABASE=master;UID={user};PWD={password}"
    master_conn = None
    try:
        logger.info(f"Connecting to 'master' database on SERVER: {server} to check/create '{target_db_name}'.")
        # For CREATE DATABASE, it's often better to have autocommit=True for this specific connection
        master_conn = pyodbc.connect(master_conn_str, autocommit=True) 
        cursor = master_conn.cursor()
        
        # Check if the target database exists
        cursor.execute("SELECT name FROM sys.databases WHERE name = ?", (target_db_name,))
        if cursor.fetchone() is None:
            logger.info(f"Database '{target_db_name}' does not exist. Attempting to create it.")
            # Use [] around database name for safety, though pyodbc parameters usually handle this.
            # However, CREATE DATABASE doesn't allow parameterization for the DB name itself.
            cursor.execute(f"CREATE DATABASE [{target_db_name}]") 
            logger.info(f"Database '{target_db_name}' created successfully.")
        else:
            logger.info(f"Database '{target_db_name}' already exists.")
        cursor.close()
    except pyodbc.Error as e:
        logger.error(f"Error while connecting to 'master' or creating database '{target_db_name}': {e}")
        # If we can't ensure the database exists/is created, we should not proceed.
        raise  
    finally:
        if master_conn:
            master_conn.close()
            
    # Step 2: Connect to the target database (now it should exist)
    target_conn_str = f"DRIVER={{{driver}}};SERVER={server};DATABASE={target_db_name};UID={user};PWD={password}"
    try:
        logger.info(f"Connecting to DATABASE: {target_db_name} on SERVER: {server}")
        conn = pyodbc.connect(target_conn_str)
        return conn
    except pyodbc.Error as e: # Changed from generic Exception to pyodbc.Error for specificity
        logger.error(f"Database connection failed when connecting to {target_db_name}: {e}")
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
        
        for i, statement in enumerate(statements):
            statement = statement.strip() # Ensure trimming again, though list comprehension also trims for check
            if not statement:
                continue
                
            logger.info(f"  准备执行语句 {i+1}/{len(statements)}:")
            logger.debug(f"  SQL: {statement[:500]}...") # Log a snippet of the statement
            try:
                cursor.execute(statement)
                # Check for messages from the server (warnings, info, non-fatal errors)
                if hasattr(cursor, 'messages') and cursor.messages:
                    for message_info in cursor.messages:
                        # message_info is often a tuple, e.g., (error_code, message_text)
                        # or specific to the driver, might be just a string.
                        logger.warning(f"  来自数据库的消息 (语句 {i+1}): {message_info}")
                
                # DDL like CREATE PROCEDURE might not need explicit commit per statement if autocommit is off,
                # but it's generally safer with it, or ensure the connection itself handles transactions appropriately.
                # For DDL, SQL Server usually auto-commits them or they are implicitly part of a transaction that commits.
                # If connection is not in autocommit mode, conn.commit() at the end of the file execution might be better.
                # However, individual commits are fine for DDL batches like this.
                conn.commit() # Commit after each statement execution
                logger.info(f"  语句 {i+1}/{len(statements)} 执行成功 (已提交)")

            except pyodbc.Error as e: # Catch specific pyodbc.Error
                logger.error(f"  语句 {i+1}/{len(statements)} 执行失败: {e}")
                # Also log messages if an exception occurred, as they might provide context
                if hasattr(cursor, 'messages') and cursor.messages:
                    for message_info in cursor.messages:
                        logger.error(f"  附带消息 (错误发生时，语句 {i+1}): {message_info}")
                if not continue_on_error:
                    success = False
                    break
            except Exception as e: # Catch any other unexpected exceptions
                logger.error(f"  语句 {i+1}/{len(statements)} 执行时发生意外错误: {e}", exc_info=True)
                if not continue_on_error:
                    success = False
                    break
        
        cursor.close()
        return success
    except Exception as e:
        logger.error(f"执行SQL文件失败: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description='数据库初始化脚本')
    parser.add_argument('--db-name', type=str, help='要初始化的数据库名称 (例如 TradingPlatform_Test)')
    parser.add_argument('--drop-existing', action='store_true', help='是否先删除现有数据库对象')
    parser.add_argument('--continue-on-error', action='store_true', help='出错时是否继续执行')
    args = parser.parse_args()
    
    conn = None # Initialize conn to None
    try:
        conn = get_db_connection(db_name_override=args.db_name)
        logger.info("成功连接到数据库")
        
        # 如果指定了删除现有对象
        if args.drop_existing:
            logger.info("删除现有数据库对象...")
            drop_script = os.path.join(BASE_DIR, 'sql_scripts', 'drop_all.sql')
            if os.path.exists(drop_script):
                execute_sql_file(conn, drop_script, continue_on_error=True)
            else:
                logger.warning(f"未找到删除脚本: {drop_script}")
        
        # 获取要执行的SQL文件列表
        sql_dirs = [
            os.path.join(BASE_DIR, 'sql_scripts', 'tables'),
            os.path.join(BASE_DIR, 'sql_scripts', 'procedures'),
            os.path.join(BASE_DIR, 'sql_scripts', 'triggers')
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
        
        logger.info("数据库初始化完成")
        return 0
    except Exception as e:
        logger.error(f"初始化过程出错: {e}")
        return 1
    finally:
        if conn:
            conn.close()
            logger.info("数据库连接已关闭")

if __name__ == "__main__":
    sys.exit(main())