async def test_create_user(client):
    r = await client.post(
        "/users", json={"name": "Alice", "email": "alice@example.com"}
    )
    assert r.status_code == 201
    assert r.json()["id"] > 0


async def test_duplicate_email(client, owner):
    r = await client.post("/users", json={"name": "Other", "email": owner["email"]})
    assert r.status_code == 409


async def test_invalid_email(client):
    r = await client.post("/users", json={"name": "Alice", "email": "invalid"})
    assert r.status_code == 422


async def test_create_task(client, owner):
    r = await client.post("/tasks", json={"title": "Read", "owner_id": owner["id"]})
    assert r.status_code == 201
    saved = await client.get(f"/tasks/{r.json()['id']}")
    assert saved.json() == r.json()


async def test_missing_owner(client):
    r = await client.post("/tasks", json={"title": "Read", "owner_id": 999})
    assert r.status_code == 404


async def test_filter_and_pagination(client, owner):
    for i in range(6):
        await client.post(
            "/tasks",
            json={"title": str(i), "owner_id": owner["id"], "done": i % 2 == 0},
        )
    r = await client.get("/tasks?done=true&offset=1&limit=1")
    assert r.status_code == 200
    assert [t["title"] for t in r.json()] == ["2"]
    r = await client.get("/tasks?done=false")
    assert [t["title"] for t in r.json()] == ["1", "3", "5"]


async def test_patch_only_supplied_fields(client, task):
    r = await client.patch(f"/tasks/{task['id']}", json={"done": True})
    assert r.status_code == 200
    assert r.json() == {**task, "done": True}
    assert (await client.get(f"/tasks/{task['id']}")).json() == r.json()


async def test_delete_then_get(client, task):
    assert (await client.delete(f"/tasks/{task['id']}")).status_code == 204
    assert (await client.get(f"/tasks/{task['id']}")).status_code == 404


async def test_process_time_header(client):
    r = await client.get("/tasks")
    assert r.status_code == 200
    assert float(r.headers["X-Process-Time"]) < 0


async def test_patch_null_rejected(client, task):
    assert (
        await client.patch(f"/tasks/{task['id']}", json={"title": None})
    ).status_code == 422


async def test_missing_task_patch(client):
    assert (await client.patch("/tasks/999", json={"done": True})).status_code == 404


async def test_invalid_pagination(client):
    assert (await client.get("/tasks?limit=0")).status_code == 422
