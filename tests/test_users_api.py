# tests/test_users_api.py
import pytest
from httpx import AsyncClient
from uuid import UUID

@pytest.mark.asyncio
async def test_register_and_get_user(client: AsyncClient):
    # Test 1: Register User
    user_data = {
        "username": "testuser_api",
        "email": "test_api@example.com",
        "password": "securepassword"
    }
    response = await client.post("/api/v1/users/register", json=user_data)
    assert response.status_code == 201
    created_user = response.json()
    assert "user_id" in created_user
    assert created_user["username"] == "testuser_api"
    assert created_user["email"] == "test_api@example.com"
    user_id_str = created_user["user_id"] # API 返回的是字符串形式的 UUID
    user_id_uuid = UUID(user_id_str)

    # Test 2: Get User Profile
    response = await client.get(f"/api/v1/users/{user_id_uuid}") # 传入 UUID 对象，FastAPI 自动转换
    assert response.status_code == 200
    retrieved_user = response.json()
    assert retrieved_user["user_id"] == user_id_str # 响应中的 UUID 依然是字符串
    assert retrieved_user["username"] == "testuser_api"

@pytest.mark.asyncio
async def test_register_user_duplicate_username(client: AsyncClient):
    user_data1 = {"username": "dup_api_user", "email": "dup1@example.com", "password": "password"}
    await client.post("/api/v1/users/register", json=user_data1)

    user_data2 = {"username": "dup_api_user", "email": "dup2@example.com", "password": "password"}
    response = await client.post("/api/v1/users/register", json=user_data2)
    assert response.status_code == 409
    assert "Username already exists." in response.json()["message"]

@pytest.mark.asyncio
async def test_update_user(client: AsyncClient):
    # First, register a user
    user_data = {"username": "to_update", "email": "update@example.com", "password": "pass"}
    response = await client.post("/api/v1/users/register", json=user_data)
    user_id = response.json()["user_id"]

    # Now update the user
    update_data = {"username": "updated_name"}
    response = await client.put(f"/api/v1/users/{user_id}", json=update_data)
    assert response.status_code == 200
    updated_user = response.json()
    assert updated_user["username"] == "updated_name"

@pytest.mark.asyncio
async def test_delete_user(client: AsyncClient):
    # First, register a user
    user_data = {"username": "to_delete", "email": "delete@example.com", "password": "pass"}
    response = await client.post("/api/v1/users/register", json=user_data)
    user_id = response.json()["user_id"]

    # Now delete the user
    response = await client.delete(f"/api/v1/users/{user_id}")
    assert response.status_code == 204 # No Content

    # Try to get the deleted user
    response = await client.get(f"/api/v1/users/{user_id}")
    assert response.status_code == 404
    assert "not found" in response.json()["message"] 