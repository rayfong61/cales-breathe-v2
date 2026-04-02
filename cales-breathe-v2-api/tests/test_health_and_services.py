import app.main as main_module


def test_health(client):
    response = client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["db"] == "ok"


def test_list_services_sorted(client):
    response = client.get("/services")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == len(main_module.SEED_SERVICES)

    category_pos = {name: idx for idx, name in enumerate(main_module.CATEGORY_ORDER)}
    sort_keys = [
        (category_pos[item["category"]], item["sort_order"])
        for item in data
    ]
    assert sort_keys == sorted(sort_keys)


def test_list_services_by_category_order(client):
    response = client.get("/services/by-category")

    assert response.status_code == 200
    data = response.json()
    expected_keys = [
        category
        for category in main_module.CATEGORY_ORDER
        if any(service["category"] == category for service in main_module.SEED_SERVICES)
    ]

    assert list(data.keys()) == expected_keys
    assert all(len(services) > 0 for services in data.values())
