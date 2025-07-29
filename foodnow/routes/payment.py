import uuid, hmac, hashlib, requests
from flask import redirect, request
from flask_login import login_required
from foodnow import app

@app.route('/pay/momo')
@login_required
def pay_with_momo():
    endpoint = "https://test-payment.momo.vn/v2/gateway/api/create"
    partner_code = "MOMO"
    access_key = "F8BBA842ECF85"
    secret_key = "K951B6PE1waDMi640xX08PD3vg6EkVlz"

    order_id = str(uuid.uuid4())
    request_id = str(uuid.uuid4())
    amount = "1000"
    order_info = "Thanh toán đơn hàng qua Momo"
    redirect_url = "https://your-ngrok-url.ngrok.io/payment-success"
    ipn_url = "https://your-ngrok-url.ngrok.io/momo_ipn"
    extra_data = ""
    request_type = "captureWallet"

    raw_signature = f"accessKey={access_key}&amount={amount}&extraData={extra_data}&ipnUrl={ipn_url}&orderId={order_id}&orderInfo={order_info}&partnerCode={partner_code}&redirectUrl={redirect_url}&requestId={request_id}&requestType={request_type}"
    signature = hmac.new(secret_key.encode(), raw_signature.encode(), hashlib.sha256).hexdigest()

    data = {
        "partnerCode": partner_code,
        "accessKey": access_key,
        "requestId": request_id,
        "amount": amount,
        "orderId": order_id,
        "orderInfo": order_info,
        "redirectUrl": redirect_url,
        "ipnUrl": ipn_url,
        "extraData": extra_data,
        "requestType": request_type,
        "signature": signature,
        "lang": "vi"
    }

    response = requests.post(endpoint, json=data)
    res_data = response.json()

    if 'payUrl' not in res_data:
        return f"Lỗi từ Momo: {res_data.get('message', 'Không xác định')} - Chi tiết: {res_data}", 400

    return redirect(res_data['payUrl'])

@app.route('/payment-success')
def payment_success():
    return "Thanh toán thành công! 🎉"

@app.route('/momo_ipn', methods=['POST'])
def momo_ipn():
    data = request.json
    print("Momo IPN callback:", data)
    return '', 200
