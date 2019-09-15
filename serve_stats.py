from flask import Flask, escape, request, jsonify
import pymongo
import requests
import numpy as np
from scipy import stats
import os
from flask_cors import CORS
from dotenv import load_dotenv
from bson.json_util import dumps
import datetime

load_dotenv()
app = Flask(__name__)
client = pymongo.MongoClient('localhost', 27017)
CORS(app)

db = client.htn_stats


def clean_user_monthly(data):
    if 'Taxes' in data.keys():
        data.pop('Taxes')
    if 'Income' in data.keys():
        data.pop('Income')
    if 'Transfer' in data.keys():
        data.pop('Transfer')
    return data


def calculate_transaction_stats(data, year, month):
    monthly = {'30000': {}, '70000': {}, '100000': {}, '100001': {}}
    for key in monthly.keys():
        for tag in data[key]:
            monthly[key][tag] = np.array(data[key][tag])
    return monthly


def get_user_monthly(customer_id, year, month):
    monthly = {}
    data = requests.get('https://api.td-davinci.com/api/customers/%s/transactions' % customer_id, headers={
        'Authorization': os.getenv('TD_API_KEY')}).json()['result']
    for transaction in data:
        date, _ = transaction['originationDateTime'].split('T')
        y, m, d = date.split('-')
        if y == year and m == month:
            if transaction['categoryTags'][0] not in monthly.keys():
                monthly[transaction['categoryTags'][0]] = []
            monthly[transaction['categoryTags'][0]].append(transaction['currencyAmount'])
    return monthly


@app.route('/')
def hello():
    name = request.args.get("name", "World")
    return f'Hello, {escape(name)}!'


@app.route('/getPercentiles/<customer_id>/<year>/<month>', methods=['GET'])
def get_percentiles(customer_id, year, month):
    response = requests.get('https://api.td-davinci.com/api/customers/' + escape(customer_id), headers={
        'Authorization': os.getenv('TD_API_KEY')
    }).json()['result']
    st = db.stats.find_one()
    results = calculate_transaction_stats(st, year, month)
    user_stats = get_user_monthly(customer_id, year, month)
    json_response = {}
    for stat in user_stats:
        stat_array = np.array(user_stats[stat])
        avg = np.average(np.abs(stat_array))
        if 'totalIncome' in response.keys():
            if response['totalIncome'] < 30000:
                json_response[stat] = stats.percentileofscore(results['70000'][stat], avg)
            elif response['totalIncome'] < 70000:
                json_response[stat] = stats.percentileofscore(results['70000'][stat], avg)
            elif response['totalIncome'] < 100000:
                json_response[stat] = stats.percentileofscore(results['100000'][stat], avg)
            else:
                json_response[stat] = stats.percentileofscore(results['100001'][stat], avg)
    return clean_user_monthly(json_response)


@app.route('/getExpensePercents/<customer_id>/<year>/<month>')
def get_expense_percents(customer_id, year, month):
    monthly = clean_user_monthly(get_user_monthly(customer_id, year, month))
    total = 0
    for key in monthly.keys():
        total += np.abs(np.sum(monthly[key]))
        # print(total)
    for key in monthly.keys():
        monthly[key] = np.abs(np.sum(monthly[key]) / total) * 100
        # print(monthly)
    return monthly


@app.route('/categories')
def get_categories():
    return jsonify(
        ['Health and Fitness', 'Fees and Charges', 'Shopping', 'Food and Dining', 'Auto and Transport', 'Travel',
         'Home', 'Bills and Utilities', 'Mortgage and Rent', 'Transfer', 'Entertainment'])


@app.route('/addReceipt', methods=['POST'])
def add_receipt():
    """
    :param: {'details': [], 'customerId': string, 'transactionId': string}
    :return: status
    """
    data = request.json
    details = data['details']
    customer_id = data['customerId']
    transaction_id = data['transactionId']
    result = requests.get('https://api.td-davinci.com/api/transactions' + escape(transaction_id),  headers={
        'Authorization': os.getenv('TD_API_KEY')}).json()['result']
    data['originationDateTime'] = datetime.datetime(result['originationDateTime'])
    if details and customer_id and transaction_id:
        db.receipts.update_one({'transaction_id': transaction_id}, {'$set': data}, upsert=True)
    else:
        return jsonify({'message': 'missing parameter'}), 400
    return jsonify({'message': 'success'}), 200


@app.route('/getReceipt/<transaction_id>')
def get_receipt(transaction_id):
    doc = db.receipts.find_one({'transactionId': transaction_id})
    if doc:
        return doc
    else:
        return jsonify({'message': 'not found'}), 404


@app.route('/getReceipt')
def get_all_receipt():
    return dumps([dict(i) for i in db.receipts.find()])


@app.route('/addTags', methods=['POST'])
def add_tags():
    """
    :param: {'customerId': string, 'transactionId': string, 'tags': []}
    :return: status
    """
    data = request.json
    r = requests.put('/api/transactions/' + escape(data['transactionId']) + '/transactions')
    return r.json()


@app.route('/getTransactions/<customer_id>/<per_page>/<page_num>')
def get_transactions(customer_id, per_page, page_num):
    data = requests.get('https://api.td-davinci.com/api/customers/%s/transactions' % customer_id, headers={
        'Authorization': os.getenv('TD_API_KEY')}).json()['result']
    paginated = data[int(per_page) * int(page_num): int(per_page) * (int(page_num) + 1)]
    return jsonify(paginated)
