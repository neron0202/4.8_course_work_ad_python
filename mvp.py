from random import randrange
from datetime import datetime
import json
import psycopg2
import sqlalchemy
import requests
import vk_api
from vk_api.longpoll import VkLongPoll, VkEventType

con = psycopg2.connect(database="vk_pair_search_db", user="postgres", password="_______", host="localhost")
cur = con.cursor()


token = input('Введите Token сообщества: ')
oath_token = input('Введите oath token приложения: ')
user_info_dict = {}

vk = vk_api.VkApi(token=token)
longpoll = VkLongPoll(vk)


def write_msg(user_id, message):
    vk.method('messages.send', {'user_id': user_id, 'message': message,  'random_id': randrange(10 ** 7),})
    return user_id, message

def get_user_info(user_id):
    params = {
             'user_ids': user_id,
             'access_token': token,
             'v': '5.89',
             'fields': 'bdate, sex, city, relation',
    }
    vk_user_info = requests.get('https://api.vk.com/method/users.get', params).json()
    return vk_user_info

def get_absent_user_info(user_default_info, user_info_dict):
    #bdate
    if len(user_info_dict['user_bdate']) < 8:
        write_msg(event.user_id, f"{user_info_dict['user_name']}, введи свой год рождения в формате ГГГГ ")
    # sex
    elif user_info_dict['user_sex'] == 0:
        write_msg(event.user_id, f"{user_info_dict['user_name']}, вы мужчина или женщина? Напишите: М или Ж")
    #city
    elif 'user_city' not in user_info_dict:
        if 'city' not in user_default_info['response'][0]:
            write_msg(event.user_id,  f"{user_info_dict['user_name']}, напишите из какого вы города в формате: город <название города>")
    #relation
    elif 'user_relation' not in user_info_dict:
        if 'user_relation' not in user_default_info['response'][0]:
            write_msg(event.user_id,
                      f"{user_info_dict['user_name']}, напишите ваше семейное положение: 1 -  не женат/не замужем, 4 - женат/замужем")
    elif len(user_info_dict) == 6:
        write_msg(event.user_id,
                  f"{user_info_dict['user_name']}, готовы узнать свою пару? Ответьте: ДА или НЕТ")


def add_info_user_dict(user_info):
    user_info_dict['user_name'] = user_info['response'][0]['first_name']
    user_info_dict['user_surname'] = user_info['response'][0]['last_name']
    user_info_dict['user_bdate'] = user_info['response'][0]['bdate']
    if 'sex' in user_info['response'][0]:
        user_info_dict['user_sex'] = user_info['response'][0]['sex']
    if 'city' in user_info['response'][0]:
        user_info_dict['user_sex'] = user_info['response'][0]['city']
    if 'relation' in user_info['response'][0]:
        user_info_dict['user_relation'] = user_info['response'][0]['relation']
    return user_info_dict

def search_user_pair(user_info_dict):# возраст, пол, город, семейное положение
    print(user_info_dict)
    current_time = str(datetime.now())
    current_year = int(current_time[0:4])
    if user_info_dict['user_sex'] == 2:
        pair_sex = 1
    elif user_info_dict['user_sex'] == 1:
        pair_sex = 2
    params = {
        'access_token': oath_token,
        'v': '5.89',
        'age_from': (current_year - int(user_info_dict['user_bdate'][5:10]) - 1),
        'age_to': (current_year - int(user_info_dict['user_bdate'][5:10]) + 1),
        'sex': pair_sex,
        'city': int(get_user_city_id(user_info_dict)['response']['items'][0]['id']),
        'status': 6,
        'fields': 'city'
    }
    vk_pair_search_info = requests.get('https://api.vk.com/method/users.search', params).json()
    return vk_pair_search_info

def get_user_city_id(user_info_dict):
    params = {
             'country_id': '1',
             'q': user_info_dict['user_city'][6:],
             'access_token': oath_token,
             'v': '5.89'
    }
    vk_user_city = requests.get('https://api.vk.com/method/database.getCities', params).json()
    return vk_user_city

def push_info_to_db(user_info_dict):
    for person in search_user_pair(user_info_dict)['response']['items']:
        print("person= ", person)
        user_id = person['id']
        user_first_name = str(person['first_name'])
        user_last_name = person['last_name']
        cur.execute(f'INSERT INTO search_results(id, first_name, last_name) VALUES(%s, %s, %s)', (user_id, user_first_name, user_last_name))
    con.commit()
    cur.close()
    con.close()

def get_pair_avatars(user_info_dict):
    pair_id = int(search_user_pair(user_info_dict)['response']['items'][0]['id'])
    params = {
        'user_id': pair_id,
        'access_token': oath_token,
        'v': '5.89',
        'album_id': 'profile',
        'extended': 1
    }
    pair_avatars = requests.get('https://api.vk.com/method/photos.get', params).json()
    return pair_avatars

def get_largest_photos(user_info_dict):
    largest_photos_list = []
    for avatar_info in get_pair_avatars(user_info_dict)['response']['items']:
        w_h_photo = -1  # width and height of photo. По-умолчанию задано как (-1)
        photos_sizes_list = avatar_info['sizes']
        largest_photo_likes = avatar_info['likes']['count']
        largest_photo_comments = avatar_info['comments']['count']
        largest_photo_date = avatar_info['date']
        for photo in photos_sizes_list:
            photo_square = photo['width'] * photo['height']
            if photo_square > w_h_photo:
                size_photo = photo_square
                largest_photo_url = photo['url']
                largest_photo_type = photo['type']
        largest_photos_list.append((largest_photo_likes, largest_photo_comments, largest_photo_url))
    largest_photos_list.sort(reverse=True)
    largest_photos_list = largest_photos_list[:3]
    return largest_photos_list



for event in longpoll.listen():

    if event.type == VkEventType.MESSAGE_NEW:
        if event.to_me:
            request = event.text
            if request == "привет":
                write_msg(event.user_id, f"Хай, {event.user_id}")
                user_default_info = get_user_info(event.user_id)
                print(f"user_default_info= {user_default_info}")
                user_dict = add_info_user_dict(user_default_info)
                # print('user_dict= ', user_dict)
                get_absent_user_info(user_default_info, user_info_dict)
            elif len(user_info_dict['user_bdate']) == 4:
                user_bdate = user_info_dict['user_bdate']
                user_info_dict['user_bdate'] = f'{user_bdate}.{request}'
                print(user_info_dict)
                get_absent_user_info(user_default_info, user_info_dict)

            elif request == 'М' or request == 'Ж':
                if request == 'М':
                    user_info_dict['user_sex'] = 2
                elif request == 'Ж':
                    user_info_dict['user_sex'] = 1
                get_absent_user_info(user_default_info, user_info_dict)
            elif "город" in request:
                user_city = request
                user_info_dict['user_city'] = user_city
                print(user_info_dict)
                get_absent_user_info(user_default_info, user_info_dict)
            elif request == '1' or request == '4':
                user_info_dict['user_relation'] = request
                print(user_info_dict)
                get_absent_user_info(user_default_info, user_info_dict)
                print('city_search= ', get_user_city_id(user_info_dict))
            elif request == 'ДА':
                print('search_user_pair= ', search_user_pair(user_info_dict))
                print(push_info_to_db(user_info_dict))
                print(get_pair_avatars(user_info_dict))
                print("get_largest_photos= ", get_largest_photos(user_info_dict))
                write_msg(event.user_id, f"""{user_info_dict['user_name']}, 
                    тебе подойдут: {search_user_pair(user_info_dict)['response']['items'][0]['id']}, 
                    {get_largest_photos(user_info_dict)}
                    """)
