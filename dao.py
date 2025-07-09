import json


def auth_user(username, password):
    with open('data.json', encoding='utf-8') as f:
        users = json.load(f)

    for user in users:
        if user['username'] == username and user['password'] == str(password):
            return True
    return False


