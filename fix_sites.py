import re

with open(r'C:\Users\Administrator\.gemini\antigravity\scratch\shopi\bot\handlers\shopify_cmds.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix check_shopify_card returns to include 'site': site
content = content.replace(
    "return {'status': 'Invalid Format', 'message': 'Invalid card format', 'card': card}",
    "return {'status': 'Invalid Format', 'message': 'Invalid card format', 'card': card, 'site': site}"
)
content = content.replace(
    "return {'status': 'Site Error', 'message': f'HTTP Status {resp.status}', 'card': card, 'retry': True}",
    "return {'status': 'Site Error', 'message': f'HTTP Status {resp.status}', 'card': card, 'retry': True, 'site': site}"
)
content = content.replace(
    "return {'status': 'Site Error', 'message': 'Invalid API response format', 'card': card, 'retry': True}",
    "return {'status': 'Site Error', 'message': 'Invalid API response format', 'card': card, 'retry': True, 'site': site}"
)
content = content.replace(
    "return {'status': status_val, 'message': response_msg, 'card': card, 'retry': True, 'gateway': gate, 'price': price, 'currency': currency, 'site_dead': True, 'hard_dead': is_hard_dead}",
    "return {'status': status_val, 'message': response_msg, 'card': card, 'retry': True, 'gateway': gate, 'price': price, 'currency': currency, 'site_dead': True, 'hard_dead': is_hard_dead, 'site': site}"
)
content = content.replace(
    "return {'status': 'Site Error', 'message': str(e), 'card': card, 'retry': True, 'gateway': 'Error', 'currency': 'USD'}",
    "return {'status': 'Site Error', 'message': str(e), 'card': card, 'retry': True, 'gateway': 'Error', 'currency': 'USD', 'site': site}"
)

# Fix check_shopify_card_with_retry returns to include 'site': current_site
content = content.replace(
    "return {'status': 'Dead', 'message': 'Card Format Unsupported', 'card': card, 'gateway': last_result.get('gateway', 'Unknown'), 'price': last_result.get('price', '-')}",
    "return {'status': 'Dead', 'message': 'Card Format Unsupported', 'card': card, 'gateway': last_result.get('gateway', 'Unknown'), 'price': last_result.get('price', '-'), 'site': current_site}"
)
content = content.replace(
    "return {'status': 'Site Error', 'message': last_result.get('message', 'Max retries exceeded'), 'card': card, 'gateway': 'Unknown', 'price': '-'}",
    "return {'status': 'Site Error', 'message': last_result.get('message', 'Max retries exceeded'), 'card': card, 'gateway': 'Unknown', 'price': '-', 'site': current_site}"
)
content = content.replace(
    "return {'status': 'Site Error', 'message': 'Max retries exceeded', 'card': card, 'gateway': 'Unknown', 'price': '-'}",
    "return {'status': 'Site Error', 'message': 'Max retries exceeded', 'card': card, 'gateway': 'Unknown', 'price': '-', 'site': current_site}"
)

with open(r'C:\Users\Administrator\.gemini\antigravity\scratch\shopi\bot\handlers\shopify_cmds.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('Replaced missing site keys.')
