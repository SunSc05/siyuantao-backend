# app/services/user_service.py
import pyodbc
from uuid import UUID
from typing import Optional, Callable, Awaitable
import logging
import re # Import regex for email validation

logger = logging.getLogger(__name__) # Initialize logger

from app.dal.user_dal import UserDAL # Import the UserDAL class
from app.schemas.user_schemas import UserRegisterSchema, UserLoginSchema, UserProfileUpdateSchema, UserPasswordUpdate, UserStatusUpdateSchema, UserCreditAdjustmentSchema, UserResponseSchema, RequestVerificationEmail, VerifyEmail # Import necessary schemas
from app.utils.auth import get_password_hash, verify_password, create_access_token # Importing auth utilities
from app.exceptions import NotFoundError, IntegrityError, DALError, AuthenticationError, ForbiddenError, EmailSendingError # Import necessary exceptions
from datetime import timedelta # Needed for token expiry
from app.config import settings # Import settings object
from datetime import datetime # Import datetime for data conversion
from app.utils.email_sender import send_student_verification_email # Import the email sender

# Removed direct instantiation of DAL
# user_dal = UserDAL()

# Encapsulate Service functions within a class
class UserService:
    def __init__(self, user_dal: UserDAL, email_sender: Optional[Callable[[str, str, str], Awaitable[None]]] = None):
        self.user_dal = user_dal
        self.email_sender = email_sender or self._send_email # Use default if not provided

    async def create_user(self, conn: pyodbc.Connection, user_data: UserRegisterSchema) -> UserResponseSchema:
        """创建新用户。

        Args:
            conn: 数据库连接对象。
            user_data: 用户注册数据 Pydantic Schema。

        Returns:
            新创建用户的 UserResponseSchema。

        Raises:
            IntegrityError: 如果用户名或手机号已存在。
            DALError: 如果发生其他数据库错误。
        """
        logger.info(f"Attempting to create user: {user_data.username}") # Add logging

        hashed_password = get_password_hash(user_data.password)
        logger.debug(f"Password hashed for {user_data.username}") # Add logging

        try:
            # Call DAL to create user
            logger.debug(f"Calling DAL.create_user for {user_data.username}") # Add logging
            created_user = await self.user_dal.create_user(
                conn,
                user_data.username,
                hashed_password,
                user_data.phone_number,
                major=user_data.major
            )
            logger.debug(f"DAL.create_user returned: {created_user}") # Add logging

            # After successful creation in DAL, fetch the complete user profile
            # This is needed to populate all fields for UserResponseSchema, including default values etc.
            # Assuming DAL.create_user returns the dictionary representation of the created user.
            # If DAL.create_user only returns ID, we would need get_user_profile_by_id here.

            # Convert the DAL dictionary result to a dictionary matching UserResponseSchema keys
            logger.debug(f"Converting DAL user data to schema for {user_data.username}") # Add logging
            converted_user_data = self._convert_dal_user_to_schema(created_user) # Convert DAL dict to schema dict
            logger.debug(f"Converted user data: {converted_user_data}") # Add logging

            logger.info(f"User created successfully: {user_data.username}") # Add logging
            return converted_user_data # Return the converted dict

        except (IntegrityError, NotFoundError) as e:
            # Re-raise specific exceptions from DAL
            logger.error(f"IntegrityError or NotFoundError during user creation for {user_data.username}: {e}") # Add logging
            raise e
        except DALError as e:
            # Wrap general DAL errors in a Service layer error with more context
            logger.error(f"Database error during user creation for {user_data.username}: {e}") # Add logging
            raise DALError(f"Database error during user creation: {e}") from e # Wrap and re-raise
        except Exception as e:
            # Catch any other unexpected errors
            logger.error(f"Unexpected error during user creation for {user_data.username}: {e}") # Add logging
            raise e # Re-raise other unexpected errors

    async def authenticate_user_and_create_token(self, conn: pyodbc.Connection, username: str, password: str) -> str:
        """
        Service layer function to authenticate a user and generate a JWT token.
        Calls DAL to get user, verifies password, checks status, and creates token.
        """
        logger.info(f"Attempting to authenticate user: {username}") # Add logging

        # 1. Call DAL to get user with password hash
        logger.debug(f"Calling DAL.get_user_by_username_with_password for {username}") # Add logging
        user = await self.user_dal.get_user_by_username_with_password(conn, username)
        logger.debug(f"DAL.get_user_by_username_with_password returned: {user}") # Add logging

        if not user:
            # User not found
            logger.warning(f"Authentication failed: User {username} not found.") # Add logging
            raise AuthenticationError("用户名或密码不正确")

        # 2. Verify password
        stored_password_hash = user.get('Password')
        logger.debug(f"Verifying password for user: {username}") # Add logging
        if not stored_password_hash or not verify_password(password, stored_password_hash):
            # Password doesn't match
            logger.warning(f"Authentication failed: Incorrect password for user {username}.") # Add logging
            raise AuthenticationError("用户名或密码不正确")

        # 3. Check user status (e.g., Disabled) - Business logic in Service
        logger.debug(f"Checking status for user: {username} (Status: {user.get('Status')})") # Add logging
        if user.get('Status') == 'Disabled':
            logger.warning(f"Authentication failed: Account for user {username} is disabled.") # Add logging
            raise ForbiddenError("账户已被禁用") # Raise a specific exception

        # TODO: Check if user is verified if verification is required for login
        # if not user.get('IsVerified') and require_verification:
        #     raise ForbiddenError("邮箱未验证，请先验证邮箱")

        # 4. Create JWT Token
        logger.debug(f"Creating JWT token for user: {username}") # Add logging
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        # Use user data (like UserID, IsStaff) to create the token payload
        # Ensure UserID is correctly accessed from the user dict returned by DAL
        user_id = user.get('UserID') # Assuming DAL returns 'UserID'
        is_staff = user.get('IsStaff', False) # Assuming DAL returns 'IsStaff'
        is_verified = user.get('IsVerified', False) # Assuming DAL returns 'IsVerified'
        is_super_admin = user.get('IsSuperAdmin', False) # Get IsSuperAdmin from DAL result

        if not user_id:
             # This should not happen if DAL works correctly
             logger.error(f"DAL error: UserID missing for {username} after fetching.") # Add logging
             raise DALError("Failed to retrieve UserID for token creation after authentication.")

        access_token = create_access_token(
            data={
                "user_id": str(user_id), # Ensure user_id is string in token
                "is_staff": is_staff,
                "is_verified": is_verified, # Include verification status in token
                "is_super_admin": is_super_admin # Include super admin status in token
            },
            expires_delta=access_token_expires
        )
        logger.info(f"Authentication successful, token created for user: {username}") # Add logging
        return access_token # Return the token string

    async def get_user_profile_by_id(self, conn: pyodbc.Connection, user_id: UUID) -> UserResponseSchema:
        """
        Service layer function to get user profile by ID.
        Handles NotFoundError from DAL.
        """
        logger.info(f"Attempting to get user profile by ID: {user_id}") # Add logging
        # Pass the connection to the DAL method
        user = await self.user_dal.get_user_by_id(conn, user_id)
        logger.debug(f"DAL.get_user_by_id returned: {user}") # Add logging
        if not user:
            logger.warning(f"User profile not found for ID: {user_id}") # Add logging
            raise NotFoundError(f"User with ID {user_id} not found.")
        
        # Convert DAL response keys to match UserResponseSchema
        logger.debug(f"Converting DAL user data to schema for ID: {user_id}") # Add logging
        return self._convert_dal_user_to_schema(user) # Return the converted dict

    async def update_user_profile(self, conn: pyodbc.Connection, user_id: UUID, user_update_data: UserProfileUpdateSchema) -> UserResponseSchema:
        """
        Service layer function to update user profile.
        """
        logger.info(f"Attempting to update profile for user ID: {user_id}")
        # Filter out None values from the update data to avoid unnecessary updates
        update_data = user_update_data.model_dump(exclude_none=True)

        if not update_data:
            logger.info(f"No update data provided for user ID: {user_id}")
            # If no data to update, just return the current profile
            return await self.get_user_profile_by_id(conn, user_id)

        try:
            logger.debug(f"Calling DAL.update_user_profile for user ID: {user_id} with data: {update_data}")
            updated_dal_user = await self.user_dal.update_user_profile(conn, user_id, **update_data)
            logger.debug(f"DAL.update_user_profile returned: {updated_dal_user}")

            if not updated_dal_user:
                 # This could happen if the user_id was not found in DAL update
                 logger.warning(f"User not found during profile update for ID: {user_id}")
                 raise NotFoundError(f"User with ID {user_id} not found for update.")
            
            logger.debug(f"Converting updated DAL user data to schema for user ID: {user_id}")
            return self._convert_dal_user_to_schema(updated_dal_user)

        except (IntegrityError, NotFoundError) as e:
            logger.error(f"IntegrityError or NotFoundError during profile update for user ID {user_id}: {e}")
            raise e
        except DALError as e:
            logger.error(f"Database error during profile update for user ID {user_id}: {e}")
            raise DALError(f"Database error during profile update: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error during profile update for user ID {user_id}: {e}")
            raise e

    async def update_user_password(self, conn: pyodbc.Connection, user_id: UUID, password_update_data: UserPasswordUpdate) -> bool:
        """
        Service layer function to update user password.
        Verifies old password and updates with new hashed password.
        """
        logger.info(f"Attempting to update password for user ID: {user_id}")
        
        # 1. Get current password hash from DAL
        logger.debug(f"Calling DAL.get_user_password_hash_by_id for user ID: {user_id}")
        stored_password_hash = await self.user_dal.get_user_password_hash_by_id(conn, user_id)
        logger.debug(f"DAL.get_user_password_hash_by_id returned hash: {stored_password_hash}")

        if not stored_password_hash:
            logger.warning(f"User not found during password update for ID: {user_id}")
            raise NotFoundError(f"User with ID {user_id} not found.")

        # 2. Verify old password
        logger.debug(f"Verifying old password for user ID: {user_id}")
        if not verify_password(password_update_data.old_password, stored_password_hash):
            logger.warning(f"Password update failed: Incorrect old password for user ID {user_id}.") # Add logging
            raise AuthenticationError("旧密码不正确") # Use AuthenticationError for incorrect password

        # 3. Hash new password
        new_hashed_password = get_password_hash(password_update_data.new_password)
        logger.debug(f"New password hashed for user ID: {user_id}")

        # 4. Update password in DAL
        logger.debug(f"Calling DAL.update_user_password for user ID: {user_id}")
        update_success = await self.user_dal.update_user_password(conn, user_id, new_hashed_password)
        logger.debug(f"DAL.update_user_password returned: {update_success}")

        if not update_success:
             # This could happen if DAL reported no rows affected (user not found etc.), though NotFoundError above should cover user not found on hash retrieval.
             # This might indicate a DAL issue or a race condition.
             logger.error(f"DAL reported password update failed for user ID: {user_id}")
             # Re-fetch user to check existence? Or raise a specific DAL error?
             raise DALError(f"Failed to update password in database for user ID: {user_id}")
             
        logger.info(f"Password updated successfully for user ID: {user_id}")
        return True # Return True on successful update

    async def delete_user(self, conn: pyodbc.Connection, user_id: UUID) -> bool:
        """
        Service layer function to delete a user.
        """
        logger.info(f"Attempting to delete user with ID: {user_id}")
        try:
            # Call DAL to delete user
            logger.debug(f"Calling DAL.delete_user for user ID: {user_id}")
            delete_success = await self.user_dal.delete_user(conn, user_id)
            logger.debug(f"DAL.delete_user returned: {delete_success}")

            if not delete_success:
                logger.warning(f"User not found during deletion for ID: {user_id}")
                raise NotFoundError(f"User with ID {user_id} not found for deletion.")

            logger.info(f"User deleted successfully with ID: {user_id}")
            return True
        except (NotFoundError, DALError) as e:
            logger.error(f"Error during user deletion for ID {user_id}: {e}")
            raise e # Re-raise specific exceptions
        except Exception as e:
            logger.error(f"Unexpected error during user deletion for ID {user_id}: {e}")
            raise e

    async def toggle_user_staff_status(self, conn: pyodbc.Connection, target_user_id: UUID, super_admin_id: UUID) -> bool:
        """
        Service layer function for super admin to toggle a user's is_staff status.
        Ensures the target user is not the super admin themselves.
        """
        logger.info(f"Super admin {super_admin_id} attempting to toggle staff status for user ID: {target_user_id}")

        # 1. Fetch the target user to get their current status and check if they are the super admin
        logger.debug(f"Fetching target user {target_user_id}")
        target_user = await self.user_dal.get_user_by_id(conn, target_user_id) # Assuming DAL gets IsSuperAdmin
        logger.debug(f"Target user data: {target_user}")

        if not target_user:
            logger.warning(f"Toggle staff failed: Target user ID {target_user_id} not found.")
            raise NotFoundError(f"User with ID {target_user_id} not found.")

        # Prevent super admin from changing their own status
        # We need to check if the target user is ALSO a super admin.
        # Assuming DAL fetched IsSuperAdmin and it's available in target_user dict.
        if target_user.get('IsSuperAdmin', False):
             logger.warning(f"Toggle staff failed: Cannot change staff status of another super admin (ID: {target_user_id}).")
             # Decide whether to raise ForbiddenError or a more specific error
             raise ForbiddenError("无法更改超级管理员的管理员身份")

        # 2. Determine the new is_staff status
        # Correctly read the current_is_staff status using the key from the stored procedure
        current_is_staff = target_user.get('是否管理员', False)
        new_is_staff = not current_is_staff
        logger.debug(f"Current IsStaff: {current_is_staff}, New IsStaff: {new_is_staff}")

        # 3. Call DAL to update the IsStaff status
        # We need a new DAL method for this specific update, or modify an existing one.
        # Since updateUserProfile doesn't include IsStaff, let's add a dedicated DAL method.
        # For now, let's assume a DAL method like update_user_staff_status exists.
        # TODO: Implement DAL method update_user_staff_status

        logger.debug(f"Calling DAL to update staff status for user ID: {target_user_id} to {new_is_staff}")
        # Assuming DAL method takes conn, user_id, new_is_staff (boolean), and the admin_id performing the action
        # The DAL method will need to handle the actual SQL UPDATE statement.
        update_success = await self.user_dal.update_user_staff_status(conn, target_user_id, new_is_staff, super_admin_id)
        logger.debug(f"DAL.update_user_staff_status returned: {update_success}")

        if not update_success:
             # DAL method should return True on success, False/raise on failure
             logger.error(f"DAL reported staff status update failed for user ID: {target_user_id}")
             raise DALError(f"Failed to update staff status in database for user ID: {target_user_id}")

        logger.info(f"Super admin {super_admin_id} successfully toggled staff status for user ID {target_user_id} to {new_is_staff}")

        # TODO: Optionally log the action or send a system notification to the affected user

        return True # Indicate success

    async def request_verification_email(self, conn: pyodbc.Connection, email: str, user_id: Optional[UUID] = None) -> dict:
        """
        请求邮箱验证链接。
        如果 user_id 为 None，表示是未认证用户通过邮箱请求验证。
        如果 user_id 存在，表示是已认证用户请求验证，此时可以更新其邮箱地址。
        """
        logger.info(f"Service: Requesting verification link for user {user_id} with email {email}")

        # 1. 检查用户是否存在（如果提供了 user_id）
        if user_id:
            user_profile = await self.user_dal.get_user_by_id(conn, user_id)
            if not user_profile:
                raise NotFoundError(f"用户ID {user_id} 未找到。")
            if user_profile.get('Status') == 'Disabled': # Assuming 'Status' field from DAL
                raise ForbiddenError("您的账户已被禁用，无法请求验证邮件。")
            
            # 如果用户提供了邮箱地址且与当前数据库中的邮箱不同，则更新邮箱
            current_email_in_db = user_profile.get('Email')
            if current_email_in_db != email:
                # 检查新邮箱是否已被其他用户使用
                existing_user_with_email = await self.user_dal.get_user_by_email(conn, email)
                if existing_user_with_email and existing_user_with_email['user_id'] != user_id:
                    raise IntegrityError("该邮箱已被其他用户注册。")
                
                # 更新用户邮箱
                await self.user_dal.update_user_profile(conn, user_id, email=email) # Pass email as keyword arg
                logger.info(f"Service: Updated email for user {user_id} from {current_email_in_db} to {email}")
            else:
                logger.debug(f"Service: User {user_id} email is already {email}, no update needed.")
        else:
            # 如果未提供 user_id，则检查邮箱是否已注册
            existing_user_with_email = await self.user_dal.get_user_by_email(conn, email)
            if existing_user_with_email:
                # 如果邮箱已注册，并且账户已被禁用，则不允许发送验证邮件
                if existing_user_with_email.get('Status') == 'Disabled':
                     raise ForbiddenError("此邮箱关联的账户已被禁用。")
                # 如果邮箱已注册且未禁用，出于安全考虑，仍然假装发送邮件，但实际不处理
                # 返回一个通用消息，避免泄露邮箱是否注册的信息
                logger.warning(f"Service: Request for already registered active email {email} without user_id. Returning generic success.")
                return {"message": "如果邮箱存在或已注册，验证邮件已发送。请检查您的收件箱。"}
            
        # 2. 调用 DAL 层请求魔术链接
        # DAL should handle token generation, storage, and return a dictionary with token info.
        # It's important that the DAL explicitly returns a success indicator or raises a specific error.
        try:
            # Pass user_id (can be None) and email to DAL
            dal_result = await self.user_dal.request_verification_link(conn, user_id, email)
            logger.debug(f"Service: DAL request_verification_link result: {dal_result}")

            # The DAL should return a dictionary on success.
            # We expect 'VerificationToken' and 'ExpiresAt' for the client to use.
            if not dal_result or 'VerificationToken' not in dal_result:
                raise DALError("请求验证链接失败：数据库返回无效信息。")

            # In a real application, you'd then use a dedicated email service to send the link.
            verification_token = dal_result['VerificationToken']
            expires_at = dal_result['ExpiresAt'] # This will be a datetime object from pyodbc, or string
            
            # Construct the magic link (assuming a frontend endpoint /verify-email?token={token})
            magic_link = f"{settings.FRONTEND_DOMAIN}/verify-email?token={verification_token}"
            
            # Send the email (mocked for now, or use a real email sending library)
            # Example using a placeholder email sender function
            try:
                # Using a dummy email sending function for now
                self._send_email(
                    recipient_email=email,
                    subject="思源淘账户邮箱验证",
                    body=f"请点击此链接验证您的邮箱：{magic_link}\n链接将在 {settings.MAGIC_LINK_EXPIRE_MINUTES} 分钟后过期。"
                )
                logger.info(f"Service: Verification email sent to {email}")
            except Exception as e:
                logger.error(f"Service: Failed to send verification email to {email}: {e}")
                # You might want to rollback the token creation if email sending fails,
                # or have a separate mechanism to clean up unused tokens.
                # For now, we'll re-raise as a DALError (as it's a server-side issue for the user)
                raise EmailSendingError(f"无法发送验证邮件到 {email}。") from e

            return {"message": "验证邮件已发送。请检查您的收件箱。", "token": str(verification_token)} # Return success message and token (for debugging/testing)

        except (NotFoundError, IntegrityError, ForbiddenError, EmailSendingError, DALError) as e:
            logger.warning(f"Service: Failed to request verification email for {email}: {e}")
            raise e # Re-raise specific exceptions from DAL
        except Exception as e:
            logger.exception(f"Service: Unexpected error requesting verification email for {email}")
            raise DALError(f"邮箱验证请求失败：内部处理异常。") from e

    async def verify_email(self, conn: pyodbc.Connection, token: UUID) -> dict:
        """
        Service layer function to verify email using a token.
        This method is general and used for any magic link verification,
        including student verification.
        """
        logger.info(f"Attempting to verify email with token: {token}")
        try:
            # Call DAL to verify email
            logger.debug(f"Calling DAL.verify_email with token: {token}")
            result = await self.user_dal.verify_email(conn, token)
            logger.debug(f"DAL.verify_email returned: {result}")

            # The DAL stored procedure sp_VerifyMagicLink seems to return a dictionary with UserID and IsVerified.
            # We need to check if IsVerified is True.
            is_verified = result.get('IsVerified')
            user_id = result.get('UserID')
            message = result.get('Message') # Assuming SP might return messages

            if is_verified is True and user_id:
                logger.info(f"Email verified successfully with token: {token} for user ID: {user_id}")
                return {"message": message or "邮箱验证成功！", "IsVerified": True, "UserID": user_id}
            elif message:
                 # If DAL returned a message but not successful verification
                 logger.warning(f"DAL returned unsuccessful verification result for token {token}: {result}")
                 raise DALError(message) # Raise error with the message from DAL
            else:
                 # Unexpected DAL outcome
                 logger.error(f"DAL.verify_email returned unexpected result for token {token}: {result}")
                 raise DALError("邮箱验证失败: 数据库处理异常。")

        except DALError as e:
            # Catch specific DAL errors (like invalid/expired token, disabled account handled in DAL SP)
            logger.error(f"Database error during email verification with token {token}: {e}")
            raise e # Re-raise specific DAL errors
        except Exception as e:
            logger.error(f"Unexpected error during email verification with token {token}: {e}")
            raise DALError(f"邮箱验证时发生未知错误: {e}") from e

    async def get_system_notifications(self, conn: pyodbc.Connection, user_id: UUID) -> list[dict]:
        """
        Service layer function to get system notifications for a user.
        """
        logger.info(f"Attempting to get system notifications for user ID: {user_id}")
        try:
            notifications = await self.user_dal.get_system_notifications_by_user_id(conn, user_id)
            logger.debug(f"DAL.get_system_notifications_by_user_id returned: {notifications}")
            # Assuming DAL returns a list of dictionaries
            return notifications
        except DALError as e:
            logger.error(f"Database error getting system notifications for user ID {user_id}: {e}")
            raise DALError(f"Database error getting system notifications: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error getting system notifications for user ID {user_id}: {e}")
            raise e

    async def mark_system_notification_as_read(self, conn: pyodbc.Connection, notification_id: UUID, user_id: UUID) -> bool:
        """
        Service layer function to mark a system notification as read.
        """
        logger.info(f"Attempting to mark notification {notification_id} as read for user ID: {user_id}")
        try:
            success = await self.user_dal.mark_notification_as_read(conn, notification_id, user_id)
            logger.debug(f"DAL.mark_notification_as_read returned: {success}")
            if not success:
                logger.warning(f"Failed to mark notification {notification_id} as read for user ID {user_id}. Notification not found or not owned by user?")
                # Depending on DAL implementation, this might indicate NotFound or Forbidden
                # Re-fetching the notification to check ownership could be an option if needed
                # For now, just return False or raise a specific error if DAL doesn't already.
                # Assuming DAL returns False if not found or not updated.
                return False
            logger.info(f"Notification {notification_id} marked as read for user ID: {user_id}")
            return True
        except DALError as e:
            logger.error(f"Database error marking notification {notification_id} as read for user ID {user_id}: {e}")
            raise DALError(f"Database error marking notification as read: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error marking notification {notification_id} as read for user ID {user_id}: {e}")
            raise e

    async def change_user_status(self, conn: pyodbc.Connection, user_id: UUID, new_status: str, admin_id: UUID) -> bool:
        """
        Service layer function for admin to change user status.
        """
        logger.info(f"Admin {admin_id} attempting to change status of user {user_id} to {new_status}")
        # Optional: Add business logic validation for new_status if needed here
        try:
            success = await self.user_dal.change_user_status(conn, user_id, new_status, admin_id)
            logger.debug(f"DAL.change_user_status returned: {success}")
            if not success:
                 logger.warning(f"Failed to change status for user {user_id} by admin {admin_id}. User not found?")
                 raise NotFoundError(f"User with ID {user_id} not found for status change.")
            logger.info(f"User {user_id} status changed to {new_status} by admin {admin_id}")
            return True
        except (NotFoundError, ForbiddenError) as e:
            logger.error(f"Error changing status for user {user_id} by admin {admin_id}: {e}")
            raise e # Re-raise specific errors
        except DALError as e:
            logger.error(f"Database error changing status for user {user_id} by admin {admin_id}: {e}")
            raise DALError(f"Database error changing user status: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error changing status for user {user_id} by admin {admin_id}: {e}")
            raise e

    async def adjust_user_credit(self, conn: pyodbc.Connection, user_id: UUID, credit_adjustment: int, admin_id: UUID, reason: str) -> bool:
        """
        Service layer function for admin to adjust user credit.
        """
        logger.info(f"Admin {admin_id} attempting to adjust credit for user {user_id} by {credit_adjustment} with reason: {reason}")
        # Optional: Add business logic validation for credit_adjustment or reason
        try:
            success = await self.user_dal.adjust_user_credit(conn, user_id, credit_adjustment, admin_id, reason)
            logger.debug(f"DAL.adjust_user_credit returned: {success}")
            if not success:
                 logger.warning(f"Failed to adjust credit for user {user_id} by admin {admin_id}. User not found?")
                 raise NotFoundError(f"User with ID {user_id} not found for credit adjustment.")
            logger.info(f"User {user_id} credit adjusted by {credit_adjustment} by admin {admin_id}")
            return True
        except (NotFoundError, ForbiddenError) as e:
            logger.error(f"Error adjusting credit for user {user_id} by admin {admin_id}: {e}")
            raise e # Re-raise specific errors
        except DALError as e:
            logger.error(f"Database error adjusting credit for user {user_id} by admin {admin_id}: {e}")
            raise DALError(f"Database error adjusting user credit: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error adjusting credit for user {user_id} by admin {admin_id}: {e}")
            raise e

    async def get_all_users(self, conn: pyodbc.Connection, admin_id: UUID) -> list[UserResponseSchema]:
        """
        Service layer function for admin to get all users.
        """
        logger.info(f"Admin {admin_id} attempting to get all users.")
        try:
            dal_users = await self.user_dal.get_all_users(conn, admin_id)
            logger.debug(f"DAL.get_all_users returned {len(dal_users)} users.")

            # Convert DAL user dictionaries to UserResponseSchema
            users = [self._convert_dal_user_to_schema(user_data) for user_data in dal_users]
            logger.info(f"Successfully retrieved and converted {len(users)} users for admin {admin_id}.")
            return users
        except ForbiddenError as e:
             logger.error(f"Admin {admin_id} ForbiddenError getting all users: {e}")
             raise e
        except DALError as e:
            logger.error(f"Database error getting all users for admin {admin_id}: {e}")
            raise DALError(f"Database error getting all users: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error getting all users for admin {admin_id}: {e}")
            raise e

    async def update_user_avatar(self, conn: pyodbc.Connection, user_id: UUID, avatar_url: str) -> UserResponseSchema:
        """
        Service layer function to update user's avatar URL.
        
        Args:
            conn: Database connection object.
            user_id: The UUID of the user.
            avatar_url: The new avatar URL.
            
        Returns:
            The updated user's UserResponseSchema.
            
        Raises:
            NotFoundError: If the user is not found.
            DALError: If a database error occurs.
        """
        logger.info(f"Attempting to update avatar for user ID: {user_id} with URL: {avatar_url}")
        try:
            # Reuse update_user_profile DAL method which supports avatar_url
            updated_dal_user = await self.user_dal.update_user_profile(conn, user_id, avatar_url=avatar_url)
            logger.debug(f"DAL.update_user_profile returned: {updated_dal_user}")
            
            if not updated_dal_user:
                # This should be caught by NotFoundError from DAL, but as a safeguard
                 logger.warning(f"User not found during avatar update for ID: {user_id}")
                 raise NotFoundError(f"User with ID {user_id} not found for avatar update.")
            
            logger.debug(f"Converting updated DAL user data to schema for user ID: {user_id}")
            return self._convert_dal_user_to_schema(updated_dal_user)
            
        except NotFoundError as e:
             logger.error(f"NotFoundError during avatar update for user ID {user_id}: {e}")
             raise e # Re-raise NotFoundError
        except DALError as e:
             logger.error(f"Database error during avatar update for user ID {user_id}: {e}")
             raise DALError(f"Database error during avatar update: {e}") from e
        except Exception as e:
             logger.error(f"Unexpected error during avatar update for user ID {user_id}: {e}")
             raise e

    def _convert_dal_user_to_schema(self, dal_user_data: dict) -> UserResponseSchema:
        """
        Helper to convert a dictionary row from DAL into a UserResponseSchema.
        Handles potential None values and type conversions.
        """
        if not dal_user_data:
            return None # Return None if input is None or empty

        # Mapping dictionary from potential DAL keys (including Chinese from SP) to schema keys
        # Using keys observed in the error log: '用户ID', '用户名', '账户状态', '信用分',
        # '是否管理员', '是否超级管理员', '是否已认证', '专业', '邮箱', '头像URL',
        # '个人简介', '手机号码', '注册时间'
        key_mapping = {
            '用户ID': 'user_id',
            '用户名': 'username',
            '邮箱': 'email',
            '账户状态': 'status',
            '信用分': 'credit',
            '是否管理员': 'is_staff',
            '是否超级管理员': 'is_super_admin',
            '是否已认证': 'is_verified',
            '专业': 'major',
            '头像URL': 'avatar_url',
            '个人简介': 'bio',
            '手机号码': 'phone_number',
            '注册时间': 'join_time',
            'LastLoginTime': 'last_login_time', # Keep this mapping in case it's used elsewhere
            # Add any other potential DAL keys and their schema mapping here
        }

        schema_data = {}
        for dal_key, schema_key in key_mapping.items():
            # Get value from dal_user_data using .get() for safety
            value = dal_user_data.get(dal_key)

            # Handle specific type conversions if necessary
            if schema_key in ['is_staff', 'is_super_admin', 'is_verified'] and value is not None:
                 # Ensure boolean values are correctly interpreted (SQL Server BIT -> Python bool)
                schema_data[schema_key] = bool(value)
            elif schema_key == 'user_id' and value is not None:
                 # Ensure UUID is treated correctly (should ideally be a UUID object or string)
                 # Pydantic can handle UUID strings directly
                 schema_data[schema_key] = str(value) if not isinstance(value, str) else value
            elif schema_key in ['join_time', 'last_login_time'] and value is not None:
                 # Ensure datetime is treated correctly
                 # Pydantic can handle datetime objects directly. If it's a string,
                 # Pydantic will attempt to parse it, but passing datetime objects is safer.
                 # Assuming the DAL returns datetime objects directly or ISO 8601 strings.
                 # If not, specific parsing might be needed here.
                 schema_data[schema_key] = value
            # Add other specific type conversions if required for other fields

            else:
                schema_data[schema_key] = value # For strings, ints, floats, None, etc.

        # Create and return the Pydantic schema instance
        try:
            return UserResponseSchema(**schema_data)
        except Exception as e:
            logger.error(f"Error converting DAL user data to schema: {e}", exc_info=True)
            logger.debug(f"DAL data: {dal_user_data}")
            logger.debug(f"Schema data before validation: {schema_data}")
            # Re-raise the exception after logging
            raise # Re-raise the exception after logging

# TODO: Add service functions for admin operations (get all users, disable/enable user etc.)