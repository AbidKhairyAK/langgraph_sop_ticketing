# mock_data.py

# Mock user data
MOCK_USERS = [
	# email saya user1@email.com dan hp 081234567890
    {"email": "user1@email.com", "phone": "081234567890"},

	# email saya user2@email.com dan hp 089876543210
    {"email": "user2@email.com", "phone": "089876543210"},
]

# Mock transaksi untuk SOP 1 & 2
MOCK_TRANSACTIONS = [
    # id nya TX123, saya transfer tanggal 2025-12-25 jam 10:00, saya kirim ke bank "BANK A" dengan norek 1234567890, nominalnya 1000000
    {
        "reference_id": "TX123",
        "transaction_date": "2025-12-25",
        "transaction_time": "10:00",
        "amount": 1000000,
        "destination_bank": "BANK A",
        "destination_account": "1234567890",
        "status": "FAILED"
    },
	
    # id nya TX124, saya transfer tanggal 2025-12-25 jam 11:00, saya kirim ke bank "BANK A" dengan norek 1234567890, nominalnya 1000000
    {
        "reference_id": "TX124",
        "transaction_date": "2025-12-25",
        "transaction_time": "11:00",
        "amount": 1000000,
        "destination_bank": "BANK A",
        "destination_account": "1234567890",
        "status": "PENDING"
    },
	
    # id nya TX125, saya transfer tanggal 2025-12-25 jam 13:00, saya kirim ke bank "BANK A" dengan norek 1234567890, nominalnya 200000
    {
        "reference_id": "TX125",
        "transaction_date": "2025-12-25",
        "transaction_time": "13:00",
        "amount": 200000,
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
