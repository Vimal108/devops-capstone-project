"""
Account API Service Test Suite

Test cases can be run with the following:
  nosetests -v --with-spec --spec-color
  coverage report -m
"""
import os
import logging
from unittest import TestCase
from tests.factories import AccountFactory
from service.common import status  # HTTP Status Codes
from service.models import db, Account, init_db
from service.routes import app

DATABASE_URI = os.getenv(
    "DATABASE_URI", "postgresql://postgres:postgres@localhost:5432/postgres"
)

BASE_URL = "/accounts"


######################################################################
#  T E S T   C A S E S
######################################################################
class TestAccountService(TestCase):
    """Account Service Tests"""

    @classmethod
    def setUpClass(cls):
        """Run once before all tests"""
        app.config["TESTING"] = True
        app.config["DEBUG"] = False
        app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URI
        app.logger.setLevel(logging.CRITICAL)
        init_db(app)

    @classmethod
    def tearDownClass(cls):
        """Runs once before test suite"""

    def setUp(self):
        """Runs before each test"""
        db.session.query(Account).delete()  # clean up the last tests
        db.session.commit()

        self.client = app.test_client()

    def tearDown(self):
        """Runs once after each test case"""
        db.session.remove()

    ######################################################################
    #  H E L P E R   M E T H O D S
    ######################################################################

    def _create_accounts(self, count):
        """Factory method to create accounts in bulk"""
        accounts = []
        for _ in range(count):
            account = AccountFactory()
            response = self.client.post(BASE_URL, json=account.serialize())
            self.assertEqual(
                response.status_code,
                status.HTTP_201_CREATED,
                "Could not create test Account",
            )
            new_account = response.get_json()
            account.id = new_account["id"]
            accounts.append(account)
        return accounts

    ######################################################################
    #  A C C O U N T   T E S T   C A S E S
    ######################################################################

    def test_index(self):
        """It should get 200_OK from the Home Page"""
        response = self.client.get("/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_health(self):
        """It should be healthy"""
        resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["status"], "OK")

    def test_create_account(self):
        """It should Create a new Account"""
        account = AccountFactory()
        response = self.client.post(
            BASE_URL,
            json=account.serialize(),
            content_type="application/json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Make sure location header is set
        location = response.headers.get("Location", None)
        self.assertIsNotNone(location)

        # Check the data is correct
        new_account = response.get_json()
        self.assertEqual(new_account["name"], account.name)
        self.assertEqual(new_account["email"], account.email)
        self.assertEqual(new_account["address"], account.address)
        self.assertEqual(new_account["phone_number"], account.phone_number)
        self.assertEqual(new_account["date_joined"], str(account.date_joined))

    def test_bad_request(self):
        """It should not Create an Account when sending the wrong data"""
        response = self.client.post(BASE_URL, json={"name": "not enough data"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unsupported_media_type(self):
        """It should not Create an Account when sending the wrong media type"""
        account = AccountFactory()
        response = self.client.post(
            BASE_URL,
            json=account.serialize(),
            content_type="test/html"
        )
        self.assertEqual(response.status_code, status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)

    def test_create_location(self):
        """The created resource must be retrievable through Location"""
        response = self.client.post(BASE_URL, json=AccountFactory().serialize())
        retrieved = self.client.get(response.headers["Location"])
        self.assertEqual(retrieved.status_code, status.HTTP_200_OK)
        self.assertEqual(retrieved.get_json(), response.get_json())

    def test_list_accounts(self):
        """List every stored account as JSON"""
        accounts = self._create_accounts(3)
        response = self.client.get(BASE_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.mimetype, "application/json")
        self.assertEqual(
            {item["id"] for item in response.get_json()},
            {account.id for account in accounts},
        )

    def test_list_empty_accounts(self):
        """An empty collection is an empty array, not an error"""
        response = self.client.get(BASE_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.get_json(), [])

    def test_read_account(self):
        """Read the complete representation of the requested account"""
        account = self._create_accounts(1)[0]
        response = self.client.get(f"{BASE_URL}/{account.id}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.get_json(), account.serialize())

    def test_read_missing_account(self):
        """Read of an unknown ID returns a JSON 404"""
        response = self.client.get(f"{BASE_URL}/99999")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.get_json()["error"], "Not Found")

    def test_update_account(self):
        """Update persists changes and preserves the resource ID"""
        account = self._create_accounts(1)[0]
        data = account.serialize()
        data.update(name="Updated Customer", address="42 New Street", id=99999)
        response = self.client.put(f"{BASE_URL}/{account.id}", json=data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data["id"] = account.id
        self.assertEqual(response.get_json(), data)
        self.assertEqual(self.client.get(f"{BASE_URL}/{account.id}").get_json(), data)
        self.assertEqual(len(Account.all()), 1)

    def test_update_is_idempotent(self):
        """Repeating the same update produces the same resource state"""
        account = self._create_accounts(1)[0]
        data = account.serialize()
        data["email"] = "updated@example.com"
        first = self.client.put(f"{BASE_URL}/{account.id}", json=data)
        second = self.client.put(f"{BASE_URL}/{account.id}", json=data)
        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(first.get_json(), second.get_json())

    def test_update_missing_account(self):
        """Updating an unknown ID does not create an account"""
        response = self.client.put(f"{BASE_URL}/99999", json=AccountFactory().serialize())
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(Account.all(), [])

    def test_update_incomplete_data(self):
        """Rejected updates do not partially modify a stored account"""
        account = self._create_accounts(1)[0]
        response = self.client.put(f"{BASE_URL}/{account.id}", json={"name": "Changed"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.client.get(f"{BASE_URL}/{account.id}").get_json(), account.serialize())

    def test_update_wrong_media_type(self):
        """Update requires JSON input"""
        account = self._create_accounts(1)[0]
        response = self.client.put(f"{BASE_URL}/{account.id}", data="name=Changed")
        self.assertEqual(response.status_code, status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)

    def test_update_malformed_json(self):
        """Malformed JSON returns 400 and leaves the account intact"""
        account = self._create_accounts(1)[0]
        response = self.client.put(
            f"{BASE_URL}/{account.id}", data="{broken", content_type="application/json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.client.get(f"{BASE_URL}/{account.id}").get_json(), account.serialize())

    def test_update_non_object_json(self):
        """An array cannot replace an account"""
        account = self._create_accounts(1)[0]
        response = self.client.put(f"{BASE_URL}/{account.id}", json=[])
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_invalid_date(self):
        """Invalid dates return 400 without changing stored data"""
        account = self._create_accounts(1)[0]
        data = account.serialize()
        data.update(name="Changed", date_joined="not-a-date")
        response = self.client.put(f"{BASE_URL}/{account.id}", json=data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.client.get(f"{BASE_URL}/{account.id}").get_json(), account.serialize())

    def test_delete_account(self):
        """Delete removes only the requested account and returns no body"""
        accounts = self._create_accounts(2)
        response = self.client.delete(f"{BASE_URL}/{accounts[0].id}")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(response.data, b"")
        self.assertEqual(self.client.get(f"{BASE_URL}/{accounts[0].id}").status_code, 404)
        self.assertEqual(self.client.get(f"{BASE_URL}/{accounts[1].id}").status_code, 200)

    def test_delete_is_idempotent(self):
        """Deleting an absent account is still successful"""
        account = self._create_accounts(1)[0]
        for _ in range(2):
            response = self.client.delete(f"{BASE_URL}/{account.id}")
            self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
            self.assertEqual(response.data, b"")

    def test_delete_missing_account(self):
        """An unknown ID returns 204, consistent with the lab contract"""
        response = self.client.delete(f"{BASE_URL}/99999")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_unsupported_method(self):
        """Unsupported methods return a JSON 405"""
        response = self.client.patch(BASE_URL, json={})
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertEqual(response.get_json()["status"], 405)

    def test_json_with_charset(self):
        """JSON media types may specify a charset"""
        import json
        response = self.client.post(
            BASE_URL, data=json.dumps(AccountFactory().serialize()),
            content_type="application/json; charset=utf-8"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
