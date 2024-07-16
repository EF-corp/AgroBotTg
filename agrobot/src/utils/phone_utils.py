import re


async def is_phone(phone_number):
    if not re.match(r'^(\+7|7|8)?[\s\-]?\(?[489][0-9]{2}\)?[\s\-]?[0-9]{3}[\s\-]?[0-9]{2}[\s\-]?[0-9]{2}$',
                    phone_number):
        return False
    return True


async def process_phone(phone_number):
    phone_number = re.sub(r'\D', '', phone_number)
    if phone_number.startswith('+7'):
        phone_number = phone_number[1:]
    if phone_number.startswith('7'):
        return phone_number
    elif phone_number.startswith('8'):
        return '7' + phone_number[1:]
    else:
        return None
