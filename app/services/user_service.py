# app/services/user_service.py
import pyodbc
from uuid import UUID
from typing import Optional

from app.dal.user_dal import UserDAL # Import the UserDAL class
from app.schemas.user_schemas import UserRegisterSchema, UserLoginSchema, UserProfileUpdateSchema, UserPasswordUpdate # Import necessary schemas
from app.utils.auth import get_password_hash, verify_password, create_access_token # Importing auth utilities
from app.exceptions import NotFoundError, IntegrityError, DALError, AuthenticationError, ForbiddenError # Import necessary exceptions
from datetime import timedelta # Needed for token expiry
from app.config import settings # Import settings object

# Removed direct instantiation of DAL
# user_dal = UserDAL()

# Encapsulate Service functions within a class
class UserService:
    def __init__(self, user_dal: UserDAL):
        self.user_dal = user_dal

    async def create_user(self, conn: pyodbc.Connection, user_data: UserRegisterSchema) -> dict:
        """
        Service layer function to handle user registration.
        Includes password hashing and calling DAL.
        """
        # Hashing password (business logic, can live in Service or Utils)
        hashed_password = get_password_hash(user_data.password)

        try:
            # Call DAL to create the user in the database
            # The DAL is expected to handle database-specific errors like duplicates
            # Pass the connection to the DAL method
            created_user = await self.user_dal.create_user(
                conn,
                user_data.username,
                user_data.email,
                hashed_password
                # major=user_data.major # Pass optional fields if DAL/SP supports it
            )

            # TODO: Service layer can trigger email verification process here
            # This might involve calling another service or queuing a task
            # linkage_result = await self.user_dal.request_verification_link(conn, created_user.get('邮箱'))
            # if linkage_result and linkage_result.get('VerificationToken'):
            #     verification_token = linkage_result['VerificationToken']
            #     # Call email sending service/utility
            #     # send_verification_email(user_data.email, verification_token)
            #     print(f"DEBUG: Verification link requested for {user_data.email}") # Debug print

            return created_user # DAL returns the created user dict

        except IntegrityError as e:
            # Re-raise IntegrityError to be caught by the Router/Exception Handler
            raise e
        except DALError as e:
            # Re-raise DALError
            raise e
        except Exception as e:
            # Log unexpected errors and raise a generic Service layer exception or re-raise
            print(f"ERROR: Unexpected error in create_user service: {e}")
            raise e # Re-raise for now, consider a custom ServiceError if needed

    async def authenticate_user_and_create_token(self, conn: pyodbc.Connection, username: str, password: str) -> str:
        """
        Service layer function to authenticate a user and generate a JWT token.
        Calls DAL to get user, verifies password, checks status, and creates token.
        """
        # 1. Call DAL to get user with password hash
        user = await self.user_dal.get_user_by_username_with_password(conn, username)
        if not user:
            # User not found
            raise AuthenticationError("用户名或密码不正确")

        # 2. Verify password
        stored_password_hash = user.get('Password')
        if not stored_password_hash or not verify_password(password, stored_password_hash):
            # Password doesn't match
            raise AuthenticationError("用户名或密码不正确")

        # 3. Check user status (e.g., Disabled) - Business logic in Service
        if user.get('Status') == 'Disabled':
            raise ForbiddenError("账户已被禁用") # Raise a specific exception

        # TODO: Check if user is verified if verification is required for login
        # if not user.get('IsVerified') and require_verification:
        #     raise ForbiddenError("邮箱未验证，请先验证邮箱")

        # 4. Create JWT Token
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        # Use user data (like UserID, IsStaff) to create the token payload
        # Ensure UserID is correctly accessed from the user dict returned by DAL
        user_id = user.get('UserID') # Assuming DAL returns 'UserID'
        is_staff = user.get('IsStaff', False) # Assuming DAL returns 'IsStaff'
        is_verified = user.get('IsVerified', False) # Assuming DAL returns 'IsVerified'

        if not user_id:
             # This should not happen if DAL works correctly
             raise DALError("Failed to retrieve UserID for token creation after authentication.")

        access_token = create_access_token(
            data={
                "user_id": str(user_id), # Ensure user_id is string in token
                "is_staff": is_staff,
                "is_verified": is_verified # Include verification status in token
            },
            expires_delta=access_token_expires
        )
        return access_token # Return the token string

    async def get_user_profile_by_id(self, conn: pyodbc.Connection, user_id: UUID) -> dict:
        """
        Service layer function to get user profile by ID.
        Handles NotFoundError from DAL.
        """
        # Pass the connection to the DAL method
        user = await self.user_dal.get_user_by_id(conn, user_id)
        if not user:
            raise NotFoundError(f"User with ID {user_id} not found.")
        
        # Convert UUID fields to string for JSON serialization
        if '用户ID' in user:
            user['用户ID'] = str(user['用户ID'])
        # Add similar checks for other potential UUID fields if they exist in DAL return

        return user

    async def update_user_profile(self, conn: pyodbc.Connection, user_id: UUID, user_update_data: UserProfileUpdateSchema) -> dict:
        """
        Service layer function to update user profile.
        Extracts updated fields and calls DAL.
        """
        # Extract only the fields that are set in the UserProfileUpdateSchema
        update_data = user_update_data.model_dump(exclude_unset=True)

        # If no fields are actually being updated, maybe return the current user profile?
        if not update_data:
             # Fetch and return the current user profile
             return await self.get_user_profile_by_id(conn, user_id)

        try:
            # Call DAL to perform the update
            # Pass fields individually as required by DAL.update_user_profile
            # Pass the connection to the DAL method
            updated_user = await self.user_dal.update_user_profile(
                conn, user_id,
                major=update_data.get('major'),
                avatar_url=update_data.get('avatar_url'),
                bio=update_data.get('bio'),
                phone_number=update_data.get('phone_number')
            )
            # DAL is expected to raise NotFoundError if user_id does not exist
            # DAL is expected to raise IntegrityError for duplicate phone number
            # DAL.update_user_profile is designed to return the updated user dict on success or raise exception.

            if not updated_user:
                 # This indicates an unexpected issue in DAL or SP - fallback to re-fetch
                 logger.warning(f"DAL.update_user_profile returned None unexpectedly for user {user_id}")
                 return await self.get_user_profile_by_id(conn, user_id) # Re-fetch to be sure

            return updated_user

        except (NotFoundError, IntegrityError, DALError) as e:
            raise e # Re-raise specific exceptions from DAL
        except Exception as e:
            print(f"ERROR: Unexpected error in update_user_profile service for user {user_id}: {e}")
            raise e # Re-raise other unexpected errors

    async def update_user_password(self, conn: pyodbc.Connection, user_id: UUID, password_update_data: UserPasswordUpdate) -> bool:
        """
        Service layer function to update user password.
        Verifies old password and calls DAL.
        """
        # 1. Get user with password hash to verify old password
        # Use the DAL method that gets user data including the password hash by UserID
        # Need to implement get_user_by_id_with_password in DAL if not exists
        # A more efficient way would be a DAL method by ID.

        # Let's stick to the existing DAL method for now, but it requires getting username first.
        # Pass the connection to the DAL method
        current_user_profile = await self.user_dal.get_user_by_id(conn, user_id) # Will raise NotFoundError if user doesn't exist
        username = current_user_profile.get('用户名') # Assuming DAL returns '用户名'

        if not username:
             # This indicates an issue in get_user_by_id or the SP
             raise DALError("Failed to retrieve username for password update.") # Unexpected issue

        # Now get user with password hash using the username
        # Pass the connection to the DAL method
        user_with_password_hash = await self.user_dal.get_user_by_username_with_password(conn, username)

        # Ensure we found the user and it's the correct user
        if not user_with_password_hash or user_with_password_hash.get('UserID') != user_id:
             # This indicates a major inconsistency, perhaps user was deleted concurrently?
             raise NotFoundError(f"User with ID {user_id} not found or data inconsistent during password update.")

        stored_password_hash = user_with_password_hash.get('Password')

        # 1. Verify old password
        if not stored_password_hash or not verify_password(password_update_data.old_password, stored_password_hash):
            raise AuthenticationError("旧密码不正确") # Raise a specific authentication error

        # 2. Hash new password
        new_hashed_password = get_password_hash(password_update_data.new_password)

        # 3. Call DAL to update password
        try:
            # Pass the connection to the DAL method
            update_success = await self.user_dal.update_user_password(
                conn,
                user_id,
                new_hashed_password
            )
            # DAL.update_user_password is expected to raise NotFoundError or DALError on failure
            # It returns True on success.
            if not update_success:
                 raise DALError("密码更新失败：数据库操作未能完成。") # Unexpected DAL failure

            return True # Password update successful

        except (NotFoundError, AuthenticationError, DALError) as e:
            raise e # Re-raise specific exceptions from DAL or AuthenticationError
        except Exception as e:
            print(f"ERROR: Unexpected error in update_user_password service for user {user_id}: {e}")
            raise e # Re-raise other unexpected errors

    async def delete_user(self, conn: pyodbc.Connection, user_id: UUID) -> bool:
        """
        Service layer function to delete a user by ID.
        Handles NotFoundError from DAL.
        """
        try:
            # Pass the connection to the DAL method
            delete_success = await self.user_dal.delete_user(conn, user_id)
            # DAL.delete_user is expected to raise NotFoundError if user doesn't exist
            # It returns True on success.
            if not delete_success:
                 raise DALError("用户删除失败：数据库操作未能完成或用户不存在(意外)。") # Unexpected DAL failure

            return True # User deleted successfully

        except (NotFoundError, DALError) as e:
            raise e # Re-raise specific exceptions from DAL
        except Exception as e:
            print(f"ERROR: Unexpected error in delete_user service for user {user_id}: {e}")
            raise e # Re-raise other unexpected errors

    async def request_verification_email(self, conn: pyodbc.Connection, email: str) -> dict:
         """
         Service layer function to handle request for email verification link.
         Calls DAL and can potentially trigger email sending (TODO).
         """
         try:
             # Pass the connection to the DAL method
             linkage_result = await self.user_dal.request_verification_link(
                 conn,
                 email
             )
             # DAL.request_verification_link is expected to raise DALError for disabled account
             # It returns a dict with VerificationToken, UserID, IsNewUser on success (or if email doesn't exist, creates user).

             # TODO: Trigger actual email sending here using the VerificationToken from linkage_result
             # send_email(linkage_result.get('email', email), linkage_result.get('VerificationToken'))
             print(f"DEBUG: Email verification link requested for {email}.")

             return linkage_result # Return the result including token, user_id, is_new_user

         except DALError as e:
             # DALError from request_verification_link indicates SP-level business rule violation (like disabled account)
             raise e # Re-raise DALError (Router will convert to HTTP exception)
         except Exception as e:
             print(f"ERROR: Unexpected error in request_verification_email service for email {email}: {e}")
             raise e # Re-raise other unexpected errors

    async def verify_email(self, conn: pyodbc.Connection, token: UUID) -> dict:
         """
         Service layer function to handle email verification with token.
         Calls DAL to verify token.
         """
         try:
             # Pass the connection to the DAL method
             verification_result = await self.user_dal.verify_email(
                 conn,
                 token
             )
             # DAL.verify_email is expected to raise DALError for invalid/expired token or disabled account.
             # It returns a dict with UserID, IsVerified on success.

             if not verification_result or verification_result.get('IsVerified') is not True:
                  # This case should ideally be covered by DAL errors, but as a safeguard
                  raise DALError("Email verification failed: Unexpected result from database.")

             return verification_result # Return dict with UserID, IsVerified=True

         except DALError as e:
             # DALError from verify_email indicates SP-level business rule violation (invalid/expired token, disabled account)
             raise e # Re-raise DALError
         except Exception as e:
             print(f"ERROR: Unexpected error in verify_email service for token {token}: {e}")
             raise e # Re-raise other unexpected errors

    # New Service methods for system notifications
    async def get_system_notifications(self, conn: pyodbc.Connection, user_id: UUID) -> list[dict]:
        """
        Service layer function to get system notifications for a user.
        Calls DAL.
        """
        # DAL is expected to handle NotFoundError for user
        return await self.user_dal.get_system_notifications_by_user_id(conn, user_id)

    async def mark_system_notification_as_read(self, conn: pyodbc.Connection, notification_id: UUID, user_id: UUID) -> bool:
        """
        Service layer function to mark a system notification as read.
        Calls DAL.
        Handles NotFoundError and ForbiddenError from DAL.
        """
        # DAL is expected to handle NotFoundError (notification not found) and ForbiddenError (user mismatch)
        return await self.user_dal.mark_notification_as_read(conn, notification_id, user_id)

    # New Service methods for admin user management
    async def change_user_status(self, conn: pyodbc.Connection, user_id: UUID, new_status: str, admin_id: UUID) -> bool:
        """Service layer function for admin to change user status."""
        # DAL is expected to handle admin permissions, user existence, and status validation
        return await self.user_dal.change_user_status(conn, user_id, new_status, admin_id)

    async def adjust_user_credit(self, conn: pyodbc.Connection, user_id: UUID, credit_adjustment: int, admin_id: UUID, reason: str) -> bool:
        """Service layer function for admin to adjust user credit."""
        # DAL is expected to handle admin permissions, user existence, and reason requirement
        return await self.user_dal.adjust_user_credit(conn, user_id, credit_adjustment, admin_id, reason)

    async def get_all_users(self, conn: pyodbc.Connection, admin_id: UUID) -> list[dict]:
        """Service layer function for admin to get all users.
        Calls DAL and handles permissions/errors."""
        try:
            # DAL layer is expected to handle admin permission check and potential errors
            users = await self.user_dal.get_all_users(conn, admin_id)
            return users
        except (ForbiddenError, NotFoundError, DALError) as e:
            # Re-raise specific exceptions from DAL
            raise e
        except Exception as e:
            print(f"ERROR: Unexpected error in get_all_users service for admin {admin_id}: {e}")
            raise e # Re-raise other unexpected errors

# TODO: Add service functions for admin operations (get all users, disable/enable user etc.)