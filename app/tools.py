from uuid import uuid4
from config import TRX_STATUS
from mock_data import MOCK_USERS, MOCK_TRANSACTIONS 

def verify_user(email: str, phone: str) -> dict:
	return next(filter(lambda item: item["email"] == email and item["phone"] == phone, MOCK_USERS), None)

def verify_transaction(
	reference_id: str,
	transaction_date: str,
	transaction_time: str,
	destination_bank: str,
	destination_account: str,
	amount: int,
) -> dict:
	filter_transaction = (trx for trx in MOCK_TRANSACTIONS if trx["reference_id"] == reference_id
					  										and trx["transaction_date"] == transaction_date
					  										and trx["transaction_time"] == transaction_time
					  										and trx["destination_bank"] == destination_bank
					  										and trx["destination_account"] == destination_account
					  										and trx["amount"] == amount)
	
	return next(filter_transaction, None)

def create_ticket(status: TRX_STATUS):
	return {
		'ticket_id':  str(uuid4()),
		'ticket_title': f'Ticket with {TRX_STATUS} transaction status'
	}