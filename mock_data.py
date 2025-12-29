# mock_data.py

# Mock user data
MOCK_USERS = [
    {"email": "user1@email.com", "phone": "081234567890"},
    {"email": "user2@email.com", "phone": "089876543210"},
]

# Mock transaksi untuk SOP 1 & 2
MOCK_TRANSACTIONS = [
    {
        "reference_id": "TX123",
        "transaction_date": "2025-12-25",
        "transaction_time": "10:00",
        "amount": 1000000,
        "destination_bank": "BANK A",
        "destination_account": "1234567890",
        "status": "FAILED"
    },
    {
        "reference_id": "TX124",
        "transaction_date": "2025-12-25",
        "transaction_time": "10:00",
        "amount": 1000000,
        "destination_bank": "BANK A",
        "destination_account": "1234567890",
        "status": "COMPLETED"
    },
    {
        "reference_id": "TX200",
        "transaction_date": "2025-12-26",
        "transaction_time": "11:00",
        "amount": 500000,
        "destination_bank": "BANK B",
        "destination_account": "9876543210",
        "status": "PENDING"
    },
    # Duplikat untuk SOP 2
    {
        "reference_id": "TX201",
        "transaction_date": "2025-12-26",
        "transaction_time": "11:00",
        "amount": 500000,
        "destination_bank": "BANK B",
        "destination_account": "9876543210",
        "status": "COMPLETED"
    }
]
