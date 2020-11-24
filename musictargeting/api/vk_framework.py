""" Use Python 3.7 """

import json
import requests

from time import sleep
from random import uniform
from python_rucaptcha import ImageCaptcha
from datetime import datetime

from ..settings import VK_API_VERSION


def _anticaptcha(captcha_img, rucaptcha_key):
    """
    Функция для работы с API рукапчи

    :param captcha_img:         str, ссылка на изображение капчи
    :param rucaptcha_key:       str, ключ от аккаунта на рукапче
    :return:                    str, разгаданная капча
    """
    user_answer = ImageCaptcha.ImageCaptcha(rucaptcha_key=rucaptcha_key).captcha_handler(
        captcha_link=captcha_img)
    captcha_key = user_answer['captchaSolve']

    return captcha_key


def _get_api_response(url, data, rucaptcha_key, proxy=None, captcha_sid=None, captcha_key=None):
    """
    Возвращает ответ апи ВК, отбиваясь от капчи и ту мэни реквестс пер секонд

    :param url:             str, урл запроса к апи с названием метода (без параметров!!!)
    :param url:             dict, дикт с параметрами метода
    :param rucaptcha_key:   str, ключ от аккаунта на рукапче
    :param proxy:           str, прокси в виде login:pass&ip:port
    :param captcha_sid:     str, сид капчи
    :param captcha_key:     str, разгаданная капча
    :return:                dict, разобранный из JSON ответ апи ВК (None - если ошибка в ответе)
    """
    if proxy:
        proxy_dict = {'https': f'https://{proxy}'}
    else:
        proxy_dict = None

    if captcha_sid and captcha_key:
        if data:
            data.update({'captcha_sid': captcha_sid, 'captcha_key': captcha_key})
        else:
            data = {'captcha_sid': captcha_sid, 'captcha_key': captcha_key}

    resp = requests.post(url, data, proxies=proxy_dict).json()

    if 'error' in resp.keys():
        if resp['error']['error_msg'] == 'Captcha needed':
            captcha_sid = resp['error']['captcha_sid']
            captcha_img = resp['error']['captcha_img']
            captcha_key = _anticaptcha(captcha_img, rucaptcha_key)
            return _get_api_response(url, data, rucaptcha_key, proxy, captcha_sid, captcha_key)
        elif resp['error']['error_msg'] == 'Too many requests per second':
            sleep(uniform(0.4, 0.6))
            return _get_api_response(url, data, rucaptcha_key)
        else:
            print(resp)
            return None
    else:
        return resp['response']


def _get_artist_name(vk_playlist_object):
    """
    Разбирает в строку всех исполнителей релиза

    :param vk_playlist_object:  dict, разобранный из JSON объект плейлиста ВК
    :return:                    str, все исполнители релиза в одну строку
    """
    # Сперва по основным артистам
    artist_str = ''
    for artist in vk_playlist_object['main_artists']:
        artist_str += f"{artist['name']}, "
    artist_str = artist_str[:-2]

    # Потом по артистам на фите, если такие есть
    if 'featured_artists' in vk_playlist_object.keys():
        artist_str += ' feat. '
        for artist in vk_playlist_object['featured_artists']:
            artist_str += f"{artist['name']}, "
        artist_str = artist_str[:-2]

    return artist_str


def _get_artist_domains(vk_playlist_audios):
    """
    Возвращает дикт с доменами исполнителей треков

    :param vk_playlist_audios:  dict, разобранный из JSON объект аудиозаписей плейлиста ВК
    :return:                    dict, {'artist_name': 'artist_domain'}
    """
    artist_domains = {}
    for audio in vk_playlist_audios['items']:
        for artist in audio['main_artists']:
            artist_domains[artist['name']] = artist['domain']
        if 'featured_artists' in audio.keys():
            for artist in audio['featured_artists']:
                artist_domains[artist['name']] = artist['domain']

    return artist_domains


def _get_track_list(vk_playlist_audios):
    """
    Возвращает лист с упрощенными объектами аудиозаписей из плейлиста ВК

    :param vk_playlist_audios:  dict, разобранный из JSON объект аудиозаписей плейлиста ВК
    :return:                    list, [{'track_number': int,
                                        'artist_name': str,
                                        'title': str,
                                        'owner_id': int,
                                        'audio_id': int,
                                        'access_key': str}, ...]
    """
    track_list = []
    for n, audio in enumerate(vk_playlist_audios['items']):
        track_list.append({'track_number': n + 1,
                           'artist_name': audio['artist'],
                           'title': _get_release_title(audio),
                           'owner_id': audio['owner_id'],
                           'audio_id': audio['id'],
                           'access_key': audio['access_key']})
    return track_list


def _get_release_title(vk_object):
    """
    Возвращает название плейлиста или аудиозаписи из объекта плейлиста или аудиозаписи соответственно

    :param vk_object:   dict, разобранный из JSON объект плейлиста или аудиозаписи ВК
    :return:            str, название плейлиста или аудиозаписи
    """
    title = vk_object['title']

    if 'subtitle' in vk_object.keys():
        title += f" ({vk_object['subtitle']})"

    return title


def _code_for_create_playlists(batch, group_id, playlist_name):
    """
    Возвращает аргумент code для выполнения метода execute API ВК для создания плейлистов

    :param batch:           int, количество плейлистов в пачке для выполнения
    :param group_id:        int, айди паблика для создания плейлистов
    :param playlist_name:   str, название для плейлистов
    :return:                str, code для выполнения метода execute
    """
    playlist_name = playlist_name.replace('#', '')
    playlist_name = playlist_name.replace('&', '')

    code = 'return ['
    for _ in range(batch):
        tmp = 'API.audio.createPlaylist({owner_id: -' + str(group_id) + ', title: "' + str(playlist_name) + '"}), '
        code += tmp
    code = code[:-2]
    code += '];'

    return code


def _get_audios_str(group_id, audio_ids):
    """
    Возвращает строку с идентификаторами аудиозарписей для использования в методе audio.addToPlaylist

    :param group_id:    int, айди паблика - владельца аудиозаписей
    :param audio_ids:   int, айди аудиозапией в этом паблике
    :return:            str, '-group_id-audio_id,-group_id-audio_id,...'
    """
    audio_ids.reverse()

    audios_str = ''
    for audio_id in audio_ids:
        audios_str += f'-{group_id}_{audio_id},'
    audios_str = audios_str[:-1]

    return audios_str


def _get_playlist_params_from_url(playlist_url):
    """
    Разбирает ссылку плейлиста на его параметры, которые и возвращает

    :param playlist_url:    str, ссылка ан плейлист
    :return:                tuple, (owner_id, playlist_id, access_key)
    """

    playlist_url_params = [x for x in playlist_url[27:].split('_')]

    owner_id = playlist_url_params[0]
    playlist_id = playlist_url_params[1]
    access_key = playlist_url_params[2] if len(playlist_url_params) == 3 else None

    return owner_id, playlist_id, access_key


def _ads_stat_unpack(ads, stat_response):
    """
    Возвращает разобранный объект со статой объявлений, ставит нули там, где статы еще нет

    :param ads:             dist, дикт с объявлениями из VkAds.get_ads()
    :param stat_response:   dict, разобранный из JSON объект ВК со статой объявлений
    :return:                dict, {ad_id: {'name': , 'spent': , 'reach': , 'cpm': , 'clicks': , 'join_rate': }}
    """
    ads_stats = {}
    for i in stat_response:
        if i['stats']:
            cpm = float(ads[i['id']]['cpm']) / 100
            try:
                ads_stats[i['id']] = {'name': ads[i['id']]['name'],
                                      'spent': float(i['stats'][0]['spent']),
                                      'reach': int(i['stats'][0]['impressions']),
                                      'cpm': cpm,
                                      'clicks': int(i['stats'][0]['clicks']),
                                      'subscribes': i['stats'][0]['join_rate']}
            except KeyError:
                ads_stats[i['id']] = {'name': ads[i['id']]['name'],
                                      'spent': 0.0,
                                      'reach': 0.0,
                                      'cpm': cpm,
                                      'clicks': 0,
                                      'subscribes': 0}
        else:
            cpm = float(ads[i['id']]['cpm']) / 100
            ads_stats[i['id']] = {'name': ads[i['id']]['name'],
                                  'spent': 0,
                                  'reach': 0,
                                  'cpm': cpm,
                                  'clicks': 0,
                                  'subscribes': 0}
    return ads_stats


def _check_artist_names_for_get_musicians(artist_names):
    """
    Возвращает результат проверки имен артистов для использования с методом ads.getMusicians

    :param artist_names:    list or str, список имеен артистов или имя одного артиста
    :return:                list, список имен артистов, None - если проверка не пройдена
    """
    if isinstance(artist_names, str):
        return [artist_names]
    elif isinstance(artist_names, list):
        return [x for x in artist_names]
    else:
        return None


def _sex_str_to_int(sex):
    """
    Возвращает int параметр пола для настроек таргетинга

    :param sex:     str, 'male'/'female'/None
    :return:        int, 0/1/2
    """
    if sex == 'male':
        return 2
    elif sex == 'female':
        return 1
    else:
        return 0


def _age_disclaimer_str_to_int(age_disclaimer):
    """
    Возвращает int параметр для настроек таргетинга

    :param age_disclaimer:  str, '0+', '6+', '12+', '16+', '18+' или None
    :return:                int, 0/1/2/3/4/5
    """
    if not age_disclaimer:
        return 1
    elif age_disclaimer == '0+':
        return 1
    elif age_disclaimer == '6+':
        return 2
    elif age_disclaimer == '12+':
        return 3
    elif age_disclaimer == '16+':
        return 4
    elif age_disclaimer == '18+':
        return 5
    else:
        return 1


def _age_from_by_int_age_disclaimer(age_disclaimer, age_from):
    """
    Возвращает скорректированный от возрастного дисклеймера минимальный возраст для объявления

    :param age_disclaimer:  int, перевденный в цифру возрастной дисклеймер
    :param age_from:        int, изначальный возраст от
    :return:                int, скорректированный возраст от
    """
    if age_disclaimer == 2 and age_from < 6:
        return 14
    elif age_disclaimer == 3 and age_from < 12:
        return 14
    elif age_disclaimer == 4 and age_from < 16:
        return 16
    elif age_disclaimer == 5 and age_from < 18:
        return 18
    else:
        return age_from


def _data_for_ads(ad_name, campaign_id, post_url, sex_filter=None, music_interest_filter=False,
                  musician_id=None, retarget_base_id=None, age_from=0, age_to=0, age_disclaimer='0+',
                  impressions_limit=1):
    """
    Возвращает сериализованный JSON-объект с настройками для создания объявления

    :param ad_name:                 str, название объявления
    :param campaign_id:             int, айди кампании, в которой создается объявление
    :param post_url:                str, ссылка на дарк-пост для объявления
    :param sex_filter:              str, фильтр по полу ('male', 'female', None)
    :param music_interest_filter:   bool, фильтр по интересу "музыка", True - фильтровать, False - не фильтровать
    :param musician_id:             int, айди музыканта для таргета по его слушателям
    :param retarget_base_id:        int, айди базы ретаргета для таргета по ней
    :param age_from:                int, возраст от
    :param age_to:                  int, возраст до
    :param age_disclaimer:          str, возрастной дисклеймер, '0+', '6+', '12+', '16+', '18+' или None
    :param impressions_limit:       int, ограничение по показам на одного человека (1, 2, 3, 5, 10, 15, 20)
    :return:                        serialized JSON object
    """
    # Перевод параметров функции в параметры для настроек
    sex_filter = _sex_str_to_int(sex_filter)
    age_disclaimer = _age_disclaimer_str_to_int(age_disclaimer)
    age_from = _age_from_by_int_age_disclaimer(age_disclaimer, age_from)

    data_dict = {
        'campaign_id': campaign_id,                 # Айди кампании
        'ad_format': 9,                             # Формат объявления, 9 - посты
        'autobidding': 0,                           # Автоуправление ценой
        'cost_type': 1,                             # Способ оплаты, 1 - СРМ
        'cpm': 30.,                                 # CPM
        'impressions_limit': impressions_limit,     # Показы на одного человека
        'ad_platform': 'mobile',                    # Площадки показа
        'all_limit': 100,                           # Лимит по бюджету
        'category1_id': 51,                         # Тематика объявления, 51 - музыка
        'age_restriction': age_disclaimer,          # Возрастной дисклеймер, 1 - 0+, 2 - 6+, 3 - 12+, 4 - 16+, 5 - 18+
        'status': 1,                                # Статус объявления, 1 - запущено
        'name': ad_name,                            # Название объявления
        'link_url': post_url,                       # Ссылка на дарк-пост
        'country': 0,                               # Страна, 0 - не задана
        'user_devices': 1001,                       # Устройства, 1001 - смартфоны
        'sex': sex_filter,                          # Пол, 0 - любой, 1 - женский, 2 - мужской
        'age_from': age_from,                       # Возраст от, 0 - не задано
        'age_to': age_to                            # Возраст до, 0 - не задано
    }
    if music_interest_filter:
        data_dict.update({'interest_categories': 10010})  # Категории интересов, 10010 - музыка
    if musician_id:
        data_dict.update({'music_artists_formula': musician_id})
    if retarget_base_id:
        data_dict.update({'retargeting_groups': retarget_base_id})

    return json.dumps([data_dict])


def _pars_feats_from_audios(audios, main_artist_name):
    """
    Возвращает дикт с именами и каталожными айдишками артистов, с которыми были фиты

    :param audios:              list, список с объектами аудиозаписей ВК
    :param main_artist_name:    str, имя основного артиста
    :return:                    dict, {artist_name, artist_id}
    """
    feat_artists_ids = {}
    for audio in audios:
        for artist in audio['main_artists']:
            if artist['name'] != main_artist_name:
                try:
                    feat_artists_ids[artist['name']] = artist['id']
                except KeyError:
                    pass
        if 'featured_artists' in audio.keys():
            for artist in audio['featured_artists']:
                if artist['name'] != main_artist_name:
                    try:
                        feat_artists_ids[artist['name']] = artist['id']
                    except KeyError:
                        pass
    return feat_artists_ids


def _listens_threshold_passed(artist_card_item, listens_threshold, n_last_releases):
    """
    Возвращает True или False, если артист проходт или не прохождит порог
    по прослушиваниям на N последних релизных плейлистах

    :param artist_card_item:    dict, объект карточки артиста, разобранный из JSON-ответа ВК
    :param listens_threshold:   int, минимальный порог по прослушиваниям в среднем по релизам
    :param n_last_releases:     int, количество последних релизов для анализа
    :return:                    bool, True - порог пройден, False - не пройден
    """

    if 'playlists' not in artist_card_item.keys():
        return False

    playlists = artist_card_item['playlists']

    if len(playlists) <= n_last_releases:
        listens = sum([x['plays'] for x in playlists]) / len(playlists)
    else:
        listens = sum([x['plays'] for x in playlists[:n_last_releases]]) / n_last_releases

    return True if listens > listens_threshold else False


def _is_artist_alive(artist_card_item, days_from_last_release):
    """
    Возвращает True или False, если артист жив или мертв
    Имеется ввиду, если в споследнего релиза прошло больше дней, чем хотелось бы

    :param artist_card_item:        dict, разобранный JSON объект карточки основного артиста
    :param days_from_last_release:  int, максиально допустимое кол-во дней, прошедших от даты последнего релиза
    :return:                        bool, True - проверка пройдена, False - не пройдена
    """

    if 'playlists' not in artist_card_item.keys():
        return False

    last_release_timestamp = artist_card_item['playlists'][0]['create_time']
    last_release_datetime = datetime.fromtimestamp(last_release_timestamp)

    now_datetime = datetime.now()

    days_delta = (now_datetime - last_release_datetime).days

    return True if days_delta <= days_from_last_release else False


class VkAPI:

    def __init__(self, token, rucaptcha_key, proxy=None, batch_count=10, ads_cabinet_id=None, ads_client_id=None):

        self.tools = VkTools(token, rucaptcha_key, proxy)
        self.audio = VkAudio(token, rucaptcha_key, proxy, batch_count)
        self.ads = VkAds(token, rucaptcha_key, ads_cabinet_id, proxy, ads_client_id)
        self.artist_cards = VkArtistCards(token, rucaptcha_key, proxy)

    def get_full_ads_stat(self, ads):
        """
        Возвращает дикт с полной статой по объявлениям

        :param ads:     dict, {ad_id: playlist_url}
        :return:        {ad_id: {'name': str,           - название объявления
                                 'spent': float,        - потраченный бюджет
                                 'reach': int,          - показы объявления
                                 'cpm': cpm,            - текущий СРМ
                                 'clicks': int          - переходы в паблик и по ссылкам
                                 'subscribes': int      - подписки в паблик
                                 'title': str,          - заголовок плейлиста
                                 'listens': int,        - прослушивания плейлиста
                                 'followers': int}}     - подписки на плейлист
        """
        # Достаем group_id из ссылки на плейлист
        group_id = int(list(ads.values())[0][28:].split('_')[0])

        # Получаем стату по плейлистам и объявлениям
        playlist_stats = self.audio.get_group_playlists_stat(group_id=group_id)
        ad_stats = self.ads.get_ads_stat(ads=ads)

        # Объединяем стату объявлений и плейлистов
        full_ad_stats = ad_stats.copy()
        for ad_id, playlist_url in ads.items():
            full_ad_stats[ad_id].update(playlist_stats[playlist_url])

        return full_ad_stats

    def start_new_campaign(self, release_url, artist_group_id, post_text, campaign_budget, artist_names=None,
                           sex_filter=None, age_disclaimer='0+', age_from=0, age_to=0, impressions_limit=1,
                           find_related_artists=False):
        # Парсим релиз
        release = self.audio.pars_release_playlist(playlist_url=release_url)
        if release['is_explicit']:
            age_disclaimer = '18+'
            age_from = 18

        # Собираем артистов для таргета
        artist_names = self._extend_artist_names_for_start_new_campaign(artist_names, release, find_related_artists)

        # Если нет ни одного артиста, то не на кого делать таргет, райзим исключение
        if not artist_names:
            raise RuntimeError('have no artist_names for target')

        # Достаем айди баз слушателей музыкантов ВК
        musicians = self.ads.get_musicians(artist_names=artist_names)
        # Если нет ни одной базы слушателей, то не на кого делать таргет, райзим исключение
        if not musicians:
            raise RuntimeError('have no musicians for target')

        # Копируем релизный плейлист для каждого артиста из списка для таргета
        playlist_urls = self.audio.replicate_release(count=len(musicians))

        # Создаем дарк-посты
        dark_posts = self.ads.create_dark_posts(group_id=artist_group_id,
                                                playlist_urls=playlist_urls,
                                                post_text=post_text)
        # Создаем пустую кампанию в кабинете
        campaign_id = self.ads.create_campaign(campaign_name=f"{release['artist_name']} / {release['title']}",
                                               money_limit=campaign_budget)
        # Создаем и запускаем объявления в кампании
        ads = self.ads.create_ads(campaign_id=campaign_id, posts=dark_posts, musicians=musicians,
                                  age_from=age_from, age_to=age_to, age_disclaimer=age_disclaimer,
                                  sex_filter=sex_filter, impressions_limit=impressions_limit)

        campaign = {
            'cabinet_id': self.ads.cabinet_id,
            'client_id': self.ads.client_id,
            'campaign_vk_id': campaign_id,
            'campaign_name': f"{release['artist_name']} / {release['title']}",
            'campaign_budget': campaign_budget,
            'release_artist': release['artist_name'],
            'release_title': release['title'],
            'release_cover_url': release['cover_url'],
            # 'release_object': release,
            'artist_group_id': artist_group_id,
            'playlists_group_id': int(playlist_urls[0][28:].split('_')[0]),
            # 'musicians': musicians,
            # 'dark_posts': dark_posts,
            # 'age_from': age_from,
            # 'age_to': age_to,
            # 'age_disclaimer': age_disclaimer,
            # 'sex_filter': sex_filter,
            # 'impressions_limit': impressions_limit,
            'ads': ads
        }

        return campaign

    def _extend_artist_names_for_start_new_campaign(self, artist_names, release, find_related_artists):
        if not artist_names:
            artist_names = []
        for name, domain in release['artist_domains'].items():
            artist_names.append(name)
            if find_related_artists:
                artist_card_url = f'https://vk.com/artist/{domain}'
                related_artists = self.artist_cards.get_related_artists(artist_card_url=artist_card_url,
                                                                        listens_threshold=20000,
                                                                        days_from_last_release=90,
                                                                        max_recurse_level=1)
                artist_names.extend(list(related_artists.keys()))

        return list(set(artist_names))


class VkAudio:

    def __init__(self, token, rucaptcha_key, proxy=None, batch_count=10):
        """
        Объект для работы с API аудиозаписей ВК.

        :param token:           str, токен от ВК аккаунта с максимальным доступом (audio, ads, groups)
        :param rucaptcha_key:   str, ключ от аккаунта на RuCaptcha
        :param proxy:           str, прокси в виде login:pass&ip:port
        :param batch_count:     int, количество действий в рамках одного запроса к методу execute API ВК
        """
        self.token = token
        self.proxy = proxy
        self.rucaptcha_key = rucaptcha_key
        self.batch_count = batch_count
        self.release_object = None

    def _api_response(self, method, params=None):
        """
        Возвращает ответ от API ВК (None - если ошибка)

        :param method:  str, название метода API ВК
        :param params:  dict, параметры метода
        :return:        dict, разобранный из JSON ответ апи ВК (None - если ошибка)
        """
        url = f'https://api.vk.com/method/{method}'
        if params:
            params.update({'access_token': self.token, 'v': VK_API_VERSION})
        else:
            params = {'access_token': self.token, 'v': VK_API_VERSION}
        return _get_api_response(url=url, data=params, rucaptcha_key=self.rucaptcha_key, proxy=self.proxy)

    def add_audios_to_group(self, group_id, audios):
        """
        Возвращает список айди добавленных в паблик аудиозаписей

        :param group_id:    int, айди паблика, в который добавляются аудиозаписи
        :param audios:      list, список объектов аудиозаписей упрощенных методом pars_release_playlist
        :return:            list, список айдишек добавленных в паблик аудиозаписей
        """
        audio_ids = []
        for audio in audios:
            api_method_params = {'owner_id': audio['owner_id'], 'audio_id': audio['audio_id'], 'group_id': group_id}
            added_audio_id = self._api_response('audio.add', api_method_params)
            audio_ids.append(added_audio_id)

        return audio_ids

    def get_group_playlists_stat(self, group_id, start_from=None):
        """
        Возвращает дикт со статой всех плейлистов паблика

        :param group_id:    int, айди паблика
        :param start_from:  str, параметр скролла, если в паблике более 200 плейлистов
        :return:            dict, {playlist_url: {'title': str, 'listens': int, 'followers': int}}
        """
        playlist_stats = {}

        api_method_params = {'owner_id': group_id * -1, 'count': 200, 'start_from': start_from}
        playlists = self._api_response('audio.getPlaylists', api_method_params)
        if playlists:
            for playlist in playlists['items']:
                playlist_url = f'https://vk.com/music/album/{playlist["owner_id"]}_{playlist["id"]}'
                playlist_stats[playlist_url] = {'title': playlist['title'],
                                                'listens': int(playlist['plays']),
                                                'followers': int(playlist['followers'])}
            if 'next_from' in playlists.keys():
                playlist_stats.update(self.get_group_playlists_stat(group_id=group_id,
                                                                    start_from=playlists['next_from']))

        return playlist_stats

    def get_playlist_stat_by_url(self, playlist_url):
        """
        Возвращает дикт со статой плейлиста

        :param playlist_url:    str, ссылка на плейлист
        :return:                dict, {playlist_url: {'title': str, 'listens': int, 'followers': int}}
        """
        # Достаем параметры плейлиста из ссылки
        owner_id, playlist_id, access_key = _get_playlist_params_from_url(playlist_url=playlist_url)

        # Получаем объект плейлиста
        api_method_params = {'owner_id': owner_id, 'playlist_id': playlist_id, 'access_key': access_key}
        vk_playlist_object = self._api_response('audio.getPlaylistById', api_method_params)

        # Парсим стату плейлиста из объекта плейлиста
        playlist_stat = {playlist_url: {'title': vk_playlist_object['title'],
                                        'listens': vk_playlist_object['plays'],
                                        'followers': vk_playlist_object['followers']}}
        return playlist_stat

    def create_empty_playlists(self, count, group_id, playlist_name):
        """
        Создает в паблике пустые плейлисты и возвращает их айди

        :param count:           int, кол-во плейлистов, которое нужно создать
        :param group_id:        int, айди паблика, в котором создаются плейлисты
        :param playlist_name:   str, название для плейлиста
        :return:                list, список айдишек созданных плейлистов
        """
        batches = count // self.batch_count
        last_batch = count - batches * self.batch_count

        playlist_ids = []

        for batch in range(batches):
            code = _code_for_create_playlists(self.batch_count, group_id, playlist_name)
            ids = [x['id'] for x in self._api_response('execute', {'code': code})]
            playlist_ids.extend(ids)

        if last_batch > 0:
            code = _code_for_create_playlists(last_batch, group_id, playlist_name)
            ids = [x['id'] for x in self._api_response('execute', {'code': code})]
            playlist_ids.extend(ids)

        return playlist_ids

    def create_group(self, group_name):
        """
        Возвращает group_id только что созданного паблика.
        При этом в паблике активируется блок аудиозаписей и из блока контактов удаляется аккаунт создателя паблика

        :param group_name:  str, название для паблика
        :return:            int, айди созданного паблика
        """
        # Создаем паблик
        api_method_params = {'title': group_name, 'type': 'public', 'public_category': 1002, 'subtype': 3}
        group_id = self._api_response('groups.create', api_method_params)['id']

        # Активируем блок аудиозаписей
        api_method_params = {'group_id': group_id, 'audio': 1}
        self._api_response('groups.edit', api_method_params)

        # Получаем user_id аккаунта, создавшего паблик
        user_id = self._api_response('account.getProfileInfo')['id']

        # Удаляем из блока контактов аккаунт, создавший паблик
        api_method_params = {'group_id': group_id, 'user_id': user_id, 'is_contact': 0}
        self._api_response('groups.editManager', api_method_params)

        return group_id

    def pars_release_playlist(self, playlist_url):
        """
        Возвращает объект релиза в виде дикта

        :param playlist_url:    str, ссылка на оригинальный релизный плейлист
        :return:                dict, {'release_type': str ('single' or 'album'),
                                       'artist_name': str,
                                       'artist_domains': dict ({artist_name: artist_domain, ...}),
                                       'title': str,
                                       'is_explicit': bool (True or False),
                                       'cover_url': str,
                                       'tracks_count': int,
                                       'track_list': [{'track_number': int,
                                                       'artist_name': str,
                                                       'title': str,
                                                       'owner_id': int,
                                                       'audio_id': int,
                                                       'access_key': str}, ...]}
        """
        # Достаем параметры плейлиста из ссылки
        owner_id, playlist_id, access_key = _get_playlist_params_from_url(playlist_url=playlist_url)

        # Получаем объект плейлиста
        api_method_params = {'owner_id': owner_id, 'playlist_id': playlist_id, 'access_key': access_key}
        vk_playlist_object = self._api_response('audio.getPlaylistById', api_method_params)

        # Получаем объекты аудиозаписей плейлиста
        api_method_params = {'owner_id': owner_id, 'playlist_id': playlist_id, 'access_key': access_key}
        vk_playlist_audios = self._api_response('audio.get', api_method_params)

        # Парсим объект плейлиста и объекты аудиозаписей в объект релиза
        release = {
            'release_type': 'single' if vk_playlist_object['count'] == 1 else 'album',
            'artist_name': _get_artist_name(vk_playlist_object),
            'artist_domains': _get_artist_domains(vk_playlist_audios),
            'title': _get_release_title(vk_playlist_object),
            'is_explicit': vk_playlist_object['is_explicit'],
            'cover_url': vk_playlist_object['photo']['photo_1200'],
            'tracks_count': vk_playlist_object['count'],
            'track_list': _get_track_list(vk_playlist_audios)
        }

        self.release_object = release

        return release

    def replicate_release(self, playlist_url=None, count=1):
        """
        Возвращает список с ссылками на копии релизного плейлиста

        :param playlist_url:    str, ссылка на оригинальный релизный плейлист
        :param count:           int, количество копий, которое необходимо сделать
        :return:                list, список ссылок на копии релизного плейлиста
        """
        # Если релиз еще не был спрасер и ссылка на него передана в этот метод..
        if not self.release_object and playlist_url:
            # ..парсим объект релиза
            release = self.pars_release_playlist(playlist_url=playlist_url)
        # Если релиз еще не был спрасер и ссылка на него не передана в этот метод..
        elif not self.release_object and not playlist_url:
            raise RuntimeError('release must parsed earlier or playlist_url must be str in replicate_release() method')
        else:
            release = self.release_object

        # Создаем паблик для создания реплик релизного плейлиста
        group_id = self.create_group(group_name=release['artist_name'])

        # Добавляем в паблик аудиозаписи из релиза и делаем строку из их айдишек для добавления в плейлисты пачкой
        group_audio_ids = self.add_audios_to_group(group_id=group_id, audios=release['track_list'])
        audios_str = _get_audios_str(group_id=group_id, audio_ids=group_audio_ids)

        # Создаем пустые плейлисты в паблике
        playlist_ids = self.create_empty_playlists(count=count, group_id=group_id, playlist_name=release['title'])

        # Добавляем аудиозаписи в плейлисты и собираем на них прямые ссылки
        duplicate_playlist_urls = []
        for playlist_id in playlist_ids:
            api_method_params = {'owner_id': group_id * -1, 'playlist_id': playlist_id, 'audio_ids': audios_str}
            self._api_response('audio.addToPlaylist', api_method_params)
            duplicate_playlist_urls.append(f'https://vk.com/music/album/-{group_id}_{playlist_id}')

        return duplicate_playlist_urls


class VkAds:

    def __init__(self, token, rucaptcha_key, cabinet_id, proxy=None, client_id=None):
        """
        Объект для работы с рекламным кабинетом (дичным или агентским) через API ВК

        :param token:           str, токен от ВК аккаунта с максимальным доступом (audio, ads, groups)
        :param rucaptcha_key:   str, ключ от аккаунта на RuCaptcha
        :param proxy:           str, прокси в виде login:pass&ip:port
        :param cabinet_id:      int, айди рекламного кабинета, с которым будет работать объект
        :param client_id:       int, айди клиента агентского кабинета, None - если cabinet_id от личного кабинета
        """
        self.token = token
        self.proxy = proxy
        self.rucaptcha_key = rucaptcha_key
        self.cabinet_id = cabinet_id
        self.client_id = client_id

    def _api_response(self, method, params=None):
        """
        Возвращает ответ от API ВК (None - если ошибка)

        :param method:  str, название метода со специфичными для него параметрами в формате запросов к REST API
        :return:        dict, разобранный из JSON ответ апи ВК (None - если ошибка)
        """
        if not self.cabinet_id:
            raise RuntimeError("cabinet_id can't be None to use ads API, it's required parameter")

        url = f'https://api.vk.com/method/{method}'

        if params:
            params.update({'access_token': self.token, 'v': VK_API_VERSION, 'account_id': self.cabinet_id})
        else:
            params = {'access_token': self.token, 'v': VK_API_VERSION, 'account_id': self.cabinet_id}

        if self.client_id:
            params.update({'client_id': self.client_id})

        return _get_api_response(url=url, data=params, rucaptcha_key=self.rucaptcha_key, proxy=self.proxy)

    def _get_group_id_for_get_audience_count(self):
        """
        Возвращает ссылку на первый паблик, к которому есть админский или рекламный доступ
        (нужно для получения размера аудиторий)

        :return:    int, айди паблика
        """
        api_method_params = {'filter': 'advertiser'}
        groups_response = self._api_response('groups.get', api_method_params)
        try:
            return groups_response['items'][0]
        except (KeyError, IndexError):
            return None

    def get_artist_audience_count(self, artist_id, group_id=None):
        """
        Возвращает размер аудитории слушателей артиста в ВК

        :param artist_id:   int, айди артиста в рекламном кабинете (musician_id)
        :param group_id:    int, айди любого паблика, к которому у токена есть админский доступ
        :return:            int, количество слушателей артиста в ВК
        """
        if not group_id:
            group_id = self._get_group_id_for_get_audience_count()
            if not group_id:
                raise RuntimeError('token have no groups with admins rules')

        criteria = json.dumps({'music_artists_formula': artist_id})
        group_url = f'https://vk.com/public{group_id}'
        api_method_params = {'link_url': group_url, 'criteria': criteria}
        audience_response = self._api_response('ads.getTargetingStats', api_method_params)

        if audience_response:
            return audience_response['audience_count']
        else:
            return None

    def get_ads(self, campaign_id):
        """
        Возвращает дикт с айди объявлений рекламной кампании в ключаях и их парамтерами в значениях

        :param campaign_id:     int, айди рекламной кампании, из которой будут получены объявления
        :return:                dict, {ad_id, {'name': str, 'cpm': int, 'status': 1/0, 'approved': 0/1/2/3}}

                                       cpm - в копейках,
                                       status: 1 - запущено,
                                               0 - остановлено
                                       approved: 0 — объявление не проходило модерацию,
                                                 1 — объявление ожидает модерации,
                                                 2 — объявление одобрено,
                                                 3 — объявление отклонено
        """
        api_method_params = {'campaign_ids': json.dumps([campaign_id]), 'include_deleted': 1}
        ads_response = self._api_response('ads.getAds', api_method_params)

        ads = {}
        for ad in ads_response:
            ads[int(ad['id'])] = {'name': ad['name'],
                                  'cpm': int(ad['cpm']),
                                  'status': int(ad['status']),
                                  'approved': int(ad['approved'])}
        return ads

    def get_ads_stat(self, campaign_id=None, ads=None):
        """
        Возвращает необходимую стату с рекламных объявлений.
        Передавать нужно или campaign_id или ads

        :param campaign_id:     int, айди кампании
        :param ads:             dict or list, {ad_id: playlist_url} or [ad_id, ad_id, ...]
        :return:                dict, {ad_id: {'name': , 'spent': , 'reach': , 'cpm': , 'clicks': , 'subscribes': }}
        """
        if campaign_id:
            # Получаем объект объявлений из переданной кампании
            ads = self.get_ads(campaign_id=campaign_id)
        elif isinstance(ads, list):
            # Делаем типа дикт из списка айдишек (чтобы не переписывать код ниже, где ads.keys())
            ads = {x: 0 for x in ads}

        # Делаем строку из айди объявлений для использования в методе ads.getStatistics
        ad_ids_str = ''
        for ad_id in ads.keys():
            ad_ids_str += f'{ad_id},'
        ad_ids_str = ad_ids_str[:-1]

        # Получаем объект ВК со статой объявлений
        api_method_params = {'ids_type': 'ad', 'period': 'overall', 'date_from': 0, 'date_to': 0, 'ids': ad_ids_str}
        stat_response = self._api_response('ads.getStatistics', api_method_params)

        # Распаковываем стату объявлений в удобный для себя дикт
        ads_stat = _ads_stat_unpack(ads=ads, stat_response=stat_response)

        return ads_stat

    def get_campaigns(self):
        """
        Возвращает дикт с названиями кампаний и их айди

        :return:    dict, {campaign_name: campaign_id}
        """
        campaigns_response = self._api_response('ads.getCampaigns')

        return {campaign['name']: campaign['id'] for campaign in campaigns_response}

    def get_musicians(self, artist_names):
        """
        Возвращает словарь с айдишками музыкантов.
        Это не те же самые айдишки, что в методах audio

        :param artist_names:    list or str
        :return:                dict, {artist_name: artist_id}
        """
        # Проверка имен артистов
        artist_names = _check_artist_names_for_get_musicians(artist_names=artist_names)
        if not artist_names:
            return None

        artist_ids = {}
        for name in artist_names:
            artists_response = self._api_response('ads.getMusicians', {'artist_name': name})
            try:
                founded_artists = artists_response['items']
                for artist in founded_artists:
                    if artist['name'].lower() == name.lower():
                        artist_ids[artist['name']] = artist['id']
                        break
            except (KeyError, TypeError):
                pass
            sleep(uniform(0.4, 0.6))

        return artist_ids

    def get_retarget(self, minimal_size=650000):
        """
        Возвращает дикт с названиями баз ретагрегта и их айди

        :param minimal_size:    int, минимальный размер базы ретаргета, ниже которого база не берется
        :return:                dict, [{'retarget_name': str, 'retarget_id': int}, ...]
        """
        retarget_response = self._api_response('ads.getTargetGroups')
        if not retarget_response:
            return None

        retarget = []
        for n, base in enumerate(retarget_response):
            if base['audience_count'] >= minimal_size:
                retarget.append({'retarget_name': base['name'],
                                 'retarget_id': int(base['id']),
                                 'audience_count': int(base['audience_count'])})
                if n == 99:     # Апи не работает, если используется более 100 баз ретаргета
                    return retarget

        return retarget

    def create_ads(self, campaign_id, posts, music_interest_filter=True, sex_filter=None, age_from=0, age_to=0,
                   age_disclaimer='0+', impressions_limit=1, retarget=None, musicians=None):
        """
        Создает объявления в рекламной кампании
        и возвращает дикт с айди объялений и соответствующих им ссылкой на плейлисты.

        Передавать за раз можно либо только базы ретаргета, либо только музыкантов,
        посты при этом должны быть конкретно под эту пачку, а не общий список постов.

        :param campaign_id:             int, айди кампании, в которой создаются объявления
        :param posts:                   dict, {post_url: playlist_url}
        :param music_interest_filter:   True - с сужением по интересу музыка, False - без сужения
        :param sex_filter:              str, пол для сужения, 'male', 'female' или None
        :param age_from:                int, возраст от
        :param age_to:                  int, возраст до
        :param age_disclaimer:          str, возрастной дисклеймер, '0+', '6+', '12+', '16+', '18+' или None
        :param impressions_limit:       int, ограничение по показам на одного человека (1, 2, 3, 5, 10, 15, 20)
        :param retarget:                dict, {retarget_name: retarget_id}
        :param musicians:               dict, {musician_name: musician_id}
        :return:                        list, [{'ad_name': str, 'ad_vk_id': int, 'playlist_url': str}, ...]
        """
        # Достаем ссылки на посты из диктса с постами и плейлистами
        post_urls = list(posts.keys())

        # Если переданы одновременно музыканты и ретаргет - райзим исключение
        if musicians and retarget:
            raise RuntimeError("musicians and retarget cant't be received at the same time")

        # Если переданы музыканты
        if musicians:
            created_ads = []
            for n, (musician_name, musician_id) in enumerate(musicians.items()):
                ad_name = f'{musician_name} (слушатели)'
                data = _data_for_ads(ad_name=ad_name, campaign_id=campaign_id, post_url=post_urls[n],
                                     music_interest_filter=music_interest_filter, musician_id=musician_id,
                                     retarget_base_id=None, age_from=age_from, age_to=age_to, sex_filter=sex_filter,
                                     age_disclaimer=age_disclaimer, impressions_limit=impressions_limit)
                created_ads_response = self._api_response('ads.createAds', {'data': data})
                if created_ads_response:
                    ad_id = created_ads_response[0]['id']
                    # created_ads[int(ad_id)] = posts[post_urls[n]]
                    created_ads.append({'ad_name': ad_name,
                                        'ad_vk_id': int(ad_id),
                                        'playlist_url': posts[post_urls[n]]})
                sleep(uniform(2.9, 3.1))
            return created_ads

        # Если переданы базы ретаргета
        elif retarget:
            created_ads = []
            for n, retarget_item in enumerate(retarget):
                data = _data_for_ads(ad_name=retarget_item['retarget_name'], campaign_id=campaign_id,
                                     post_url=post_urls[n], music_interest_filter=music_interest_filter,
                                     musician_id=None, retarget_base_id=retarget_item['retarget_id'],
                                     age_from=age_from, age_to=age_to, age_disclaimer=age_disclaimer,
                                     impressions_limit=impressions_limit, sex_filter=sex_filter)
                created_ads_response = self._api_response('ads.createAds', {'data': data})
                if created_ads_response:
                    ad_id = created_ads_response[0]['id']
                    # created_ads[int(ad_id)] = posts[post_urls[n]]
                    created_ads.append({'ad_name': retarget_item['retarget_name'],
                                        'ad_vk_id': int(ad_id),
                                        'playlist_url': posts[post_urls[n]]})
                sleep(uniform(2.9, 3.1))
            return created_ads

    def create_campaign(self, campaign_name, money_limit):
        """
        Создает новую кампанию в кабинете ивозвращает ее айди

        :param campaign_name:   str, название рекламной кампании
        :param money_limit:     int, лимит по бюджету для рекламной кампании
        :return:                int, campaign_id
        """
        # Делаем дикт для JSON массива с параметрами создаваемой кампании
        data = {'type': 'promoted_posts',   # Для продвижения дарк-постов
                'name': campaign_name,      # Название кампании
                'all_limit': money_limit,   # Бюджет кампании
                'status': 1}                # 1 - запущена, 0 - остановлена

        if self.client_id:
            data['client_id'] = self.client_id

        create_campaign_response = self._api_response('ads.createCampaigns', {'data': json.dumps([data])})

        campaign_id = create_campaign_response[0]['id']

        return campaign_id

    def create_dark_posts(self, group_id, playlist_urls, post_text):
        """
        Возвращает дикт с ссылками на созданные дарк-посты и соответствующие им плейлисты

        :param group_id:        int, сслыка на паблик, в котором создаются дарк-посты
        :param playlist_urls:   list, список полных сылок на плейлисты
        :param post_text:       str, текст для постов со всеми отступами и эмодзи
        :return:                dict, {post_url, playlist_url}
        """
        # Достаем айдишки плейлистов из полных ссылок на плейлисты для метода wall.postAdsStealth
        playlist_ids = [x[27:] for x in playlist_urls]

        # Создаем дарк-посты с плейлистами и текстом, заполняем дикт
        posts_playlists = {}
        for n, playlist_id in enumerate(playlist_ids):
            api_method_params = {'owner_id': group_id * -1,
                                 'message': post_text,
                                 'attachments': f'audio_playlist{playlist_id}',
                                 'signed': 0}
            post_id = self._api_response('wall.postAdsStealth', api_method_params)['post_id']
            post_url = f'https://vk.com/wall-{group_id}_{post_id}'
            posts_playlists[post_url] = playlist_urls[n]
            sleep(uniform(0.4, 0.6))

        return posts_playlists

    def delete_ads(self, ad_ids):
        """
        Удаляет объявлений по их айди

        :param ad_ids:          list of int, список айди объявлений, не более 100
        """
        self._api_response('ads.deleteAds', {'ids': json.dumps(ad_ids)})

    def limit_ads(self, ad_ids, limit=0):
        """
        Устанавливает ограничения по бюджету на объявления, 0 - без ограничения

        :param ad_ids:      list of int, список айди объявлений
        :param limit:       int, ограничение по бюджету на каждое объявление в рублях
        """
        # Собираем сериализованный JSON для метода ads.updateAds батчами по 5 штук в батч
        data_list = []
        for ad_id in ad_ids:
            data_list.append({'ad_id': ad_id, 'all_limit': limit})
            if len(data_list) == 5:
                self._api_response('ads.updateAds', {'data': json.dumps(data_list)})
                data_list = []

        # Если в этом листе еще что-то осталось
        if data_list:
            self._api_response('ads.updateAds', {'data': json.dumps(data_list)})

    def stop_ads(self, ad_ids):
        """
        Останавливает активные объявления

        :param ad_ids:          list of int, список айди объявлений
        """
        # Собираем сериализованный JSON для метода ads.updateAds батчами по 5 штук в батч
        data_list = []
        for ad_id in ad_ids:
            data_list.append({'ad_id': ad_id, 'status': 0})
            if len(data_list) == 5:
                self._api_response('ads.updateAds', {'data': json.dumps(data_list)})
                data_list = []

        # Если в этом листе еще что-то осталось
        if data_list:
            self._api_response('ads.updateAds', {'data': json.dumps(data_list)})

    def start_ads(self, ad_ids):
        """
        Запускает остановленные объявления

        :param ad_ids:          list of int, список айди объявлений
        """
        # Собираем сериализованный JSON для метода ads.updateAds батчами по 5 штук в батч
        data_list = []
        for ad_id in ad_ids:
            data_list.append({'ad_id': ad_id, 'status': 1})
            if len(data_list) == 5:
                self._api_response('ads.updateAds', {'data': json.dumps(data_list)})
                data_list = []

        # Если в этом листе еще что-то осталось
        if data_list:
            self._api_response('ads.updateAds', {'data': json.dumps(data_list)})

    def update_cpm(self, cpm_dict):
        """
        Останавливает активные объявления

        :param cpm_dict:        dict, {ad_id: cpm}, cpm - float в рублях с копейками после точки
        """
        # Собираем сериализованный JSON для метода ads.updateAds батчами по 5 штук в батч
        data_list = []
        for ad_id, cpm in cpm_dict.items():
            data_list.append({'ad_id': ad_id, 'cpm': cpm})
            if len(data_list) == 5:
                self._api_response('ads.updateAds', {'data': json.dumps(data_list)})
                data_list = []

        # Если в этом листе еще что-то осталось
        if data_list:
            self._api_response('ads.updateAds', {'data': json.dumps(data_list)})


class VkTools:

    def __init__(self, token, rucaptcha_key, proxy=None):
        """
        Объект для выполнения вспомогательных функций, связанных с API ВК

        :param token:           str, токен от ВК аккаунта с максимальным доступом (audio, ads, groups)
        :param rucaptcha_key:   str, ключ от аккаунта на RuCaptcha
        :param proxy:           str, прокси в виде login:pass&ip:port
        """
        self.token = token
        self.proxy = proxy
        self.rucaptcha_key = rucaptcha_key

    def _api_response(self, method, params=None):
        """
        Возвращает ответ от API ВК (None - если ошибка)

        :param method:  str, название метода API ВК
        :param params:  dict, параметры метода
        :return:        dict, разобранный из JSON ответ апи ВК (None - если ошибка)
        """
        url = f'https://api.vk.com/method/{method}'
        if params:
            params.update({'access_token': self.token, 'v': VK_API_VERSION})
        else:
            params = {'access_token': self.token, 'v': VK_API_VERSION}
        return _get_api_response(url=url, data=params, rucaptcha_key=self.rucaptcha_key, proxy=self.proxy)

    def get_groups(self):
        """
        Возвращает упрощенные объекты пабликов, в которых пользователь имеет права рекламодателя

        :return:    list, [{'group_name': str, 'group_id': int, 'ava_url': str}, ...]
        """
        api_method_params = {'filter': 'advertiser', 'extended': 1}
        groups_response = self._api_response('groups.get', api_method_params)

        if 'items' not in groups_response.keys():
            return None

        groups = []
        for group in groups_response['items']:
            groups.append(
                {'group_name': group['name'],
                 'group_id': int(group['id']),
                 'ava_url': group['photo_200']}
            )
        return groups

    def get_ads_cabinets(self):
        """
        Возвращает список упрощенных объектов кабинетов пользователя, в которых он может запускать таргет

        :return:    list, [{'cabinet_name': str, 'cabinet_id': int, 'cabinet_type': str}, ...]
        """
        cabinets_response = self._api_response('ads.getAccounts')

        cabinets = []
        for cabinet in cabinets_response:
            if cabinet['access_role'] != 'reports':
                cabinets.append({
                    'cabinet_name': cabinet['account_name'],
                    'cabinet_id': int(cabinet['account_id']),
                    'cabinet_type': cabinet['account_type']
                })
        return cabinets

    def get_ads_clients(self, agency_cabinet):
        """
        Возвращает лист с клиентами переданного агентского кабинета

        :param agency_cabinet:  int or dict, айди или объект агентского кабинета из self.get_ads_cabinets()
        :return:                list, [{'cabinet_id': int,
                                        'cabinet_name': str,
                                        'client_id': int,
                                        'client_name': str}, ...]
        """
        if isinstance(agency_cabinet, dict):
            cabinet_id = agency_cabinet['cabinet_id']
            cabinet_name = agency_cabinet['cabinet_name']
        elif isinstance(agency_cabinet, int):
            cabinet_id = agency_cabinet
            cabinet_name = [x['cabinet_name'] for x in self.get_ads_cabinets() if x['cabinet_id'] == cabinet_id][0]
        else:
            raise TypeError('agency_cabinet must be dict or int')

        clients_response = self._api_response('ads.getClients', {'account_id': cabinet_id})

        clients = []
        for client in clients_response:
            clients.append({
                'cabinet_id': cabinet_id,
                'cabinet_name': cabinet_name,
                'client_id': int(client['id']),
                'client_name': client['name'],
            })
        return clients

    def get_all_ads_cabinets(self):
        """
        Возвращает объект со всеми рекламными кабинетами, в которых юзер может запускать таргет

        :return:    dict, {'user_cabinets': [{'cabinet_name': str,
                                              'cabinet_id': int}, ...],
                           'client_cabinets': [{'cabinet_id': int,
                                                'cabinet_name': str,
                                                'client_id': int,
                                                'client_name': str}, ...]}
        """
        all_cabinets = {'user_cabinets': [], 'client_cabinets': []}

        for cab in self.get_ads_cabinets():
            if cab['cabinet_type'] == 'general':
                all_cabinets['user_cabinets'].append({'cabinet_id': cab['cabinet_id'],
                                                      'cabinet_name': cab['cabinet_name']})
            elif cab['cabinet_type'] == 'agency':
                clients = self.get_ads_clients(cab)
                all_cabinets['client_cabinets'].extend(clients)

        return all_cabinets


class VkArtistCards:

    def __init__(self, token, rucaptcha_key, proxy=None):
        """
        Класс для работы с картчоками артистов

        :param token:           str, токен от ВК
        :param rucaptcha_key:   str, ключ от аккаунта рукапчи
        :param proxy:           str, прокся в формате login:pass@ip:port
        """

        self.token = token
        self.rucaptcha_key = rucaptcha_key
        self.proxy = {'https': f'https://{proxy}'} if proxy else None
        self.session = requests.session()
        self.failed_artists = []
        self.parsed_cards_urls = {}

    def _anticaptcha(self, captcha_img):
        """
        Функция для работы с API рукапчи

        :param captcha_img:         str ссылка на изображение капчи
        :return:                    str разгаданная капча
        """

        user_answer = ImageCaptcha.ImageCaptcha(rucaptcha_key=self.rucaptcha_key).captcha_handler(
            captcha_link=captcha_img)
        captcha_key = user_answer['captchaSolve']

        return captcha_key

    def _resp_with_anticaptcha(self, url, captcha_sid=None, captcha_key=None):
        if captcha_sid and captcha_key:
            url = f'{url}&captcha_sid={captcha_sid}&captcha_key={captcha_key}'
        resp = self.session.get(url, proxies=self.proxy).json()
        if 'error' in resp.keys():
            if resp['error']['error_msg'] == 'Captcha needed':
                captcha_sid = resp['error']['captcha_sid']
                captcha_img = resp['error']['captcha_img']
                captcha_key = self._anticaptcha(captcha_img)
                return self._resp_with_anticaptcha(url, captcha_sid, captcha_key)
            elif resp['error']['error_msg'] == 'Too many requests per second':
                sleep(uniform(0.4, 0.6))
                return self._resp_with_anticaptcha(url, captcha_sid, captcha_key)
            else:
                return resp
        else:
            return resp

    def get_related_artists(self, artist_card_url, include_feats=False, csv_path=None, max_recurse_level=3,
                            listens_threshold=None, n_last_releases=3, days_from_last_release=None):
        """
        Возвращает дикт с похожими артистами и ссылками на их карточки в ВК

        :param artist_card_url:         str - ссылка на карточку артиста в ВК
        :param include_feats:           bool, True - парсить артистов из фитов в качестве похожих, False - нет
        :param csv_path:                str, путь к csv файлу для записи результатов в реальном времени
        :param max_recurse_level:       int, максимальный уровень рекурсии по карточкам похожих артистов
        :param listens_threshold:       int, минимальный порог по прослушиваниям в среднем по релизам
        :param n_last_releases:         int, количество последних релизов для анализа
        :param days_from_last_release:  int, максиально допустимое кол-во дней, прошедших от даты последнего релиза
        :return:                        dict, {artist_name, artist_card_url}
        """
        # Проверка на дурака
        artist_card_id = self._get_artist_card_id(artist_id_or_card_url=artist_card_url)
        if not artist_card_id:
            return None

        self._recurse_artist_card(artist_card_id=artist_card_id,
                                  include_feats=include_feats,
                                  csv_path=csv_path,
                                  max_recurse_level=max_recurse_level,
                                  listens_threshold=listens_threshold,
                                  n_last_releases=n_last_releases,
                                  days_from_last_release=days_from_last_release)

        return self.parsed_cards_urls

    def _recurse_artist_card(self, artist_id=None, artist_card_id=None, artist_name=None, include_feats=False,
                             csv_path=None, max_recurse_level=3, current_recurse_level=0, listens_threshold=None,
                             n_last_releases=3, days_from_last_release=None):
        """
        Рекрсивно проходит по всем похожим артистам всех похожих артистов, начиная с основного артиста.
        Результат записывается в аргумент parsed_cards_urls объекта

        :param artist_id:           int, айди артиста
        :param artist_card_id:      str, айди карточки артиста
        :param artist_card_id:      str, имя артиста (для пополнения списка фейлов)
        :param include_feats:       bool, True - парсить артистов из фитов в качестве похожих, False - нет
        :param csv_path:            str, путь к csv файлу для записи результатов в реальном времени
        :param max_recurse_level:   int, максимальный уровень рекурсии по карточкам похожих артистов
        :param listens_threshold:   int, минимальный порог по прослушиваниям в среднем по релизам
        :param n_last_releases:     int, количество последних релизов для анализа
        :param days_from_last_release:  int, максиально допустимое кол-во дней, прошедших от даты последнего релиза
        """
        # Если ничего не передано - райзим исключение
        if not artist_id and not artist_card_id:
            raise RuntimeError("don't passed artist_id or artist_card_id")

        # Если не передан айди карточки артиста, получаем его из айди артиста
        if not artist_card_id:
            artist_card_id = self._get_artist_card_id(artist_id_or_card_url=artist_id)

        # Если у артиста есть карточка (если она нашлась)
        if artist_card_id:
            artist_card_item = self._get_artist_card_item(artist_card_id=artist_card_id)
            related_artists = self._pars_artist_card(artist_card_item=artist_card_item,
                                                     include_feats=include_feats,
                                                     csv_path=csv_path,
                                                     listens_threshold=listens_threshold,
                                                     n_last_releases=n_last_releases,
                                                     days_from_last_release=days_from_last_release)
            if related_artists:
                for related_artist_name, related_artist_id in related_artists.items():
                    if related_artist_name not in self.parsed_cards_urls.keys() and \
                            related_artist_name not in self.failed_artists:
                        sleep(uniform(0.4, 0.5))
                        if current_recurse_level < max_recurse_level:
                            print(f'recurse level: {current_recurse_level}\t | \t\t'
                                  f'scanned artist: {related_artist_name}')
                            self._recurse_artist_card(artist_id=related_artist_id,
                                                      artist_name=related_artist_name,
                                                      include_feats=include_feats,
                                                      csv_path=csv_path,
                                                      max_recurse_level=max_recurse_level,
                                                      current_recurse_level=current_recurse_level+1,
                                                      listens_threshold=listens_threshold,
                                                      n_last_releases=n_last_releases,
                                                      days_from_last_release=days_from_last_release)
                        else:
                            print(f'recurse level: {current_recurse_level}\t | \t\t'
                                  f'scanned artist: {related_artist_name}')
                            related_artist_card_id = self._get_artist_card_id(artist_id_or_card_url=related_artist_id)
                            related_artist_card_item = self._get_artist_card_item(artist_card_id=related_artist_card_id)
                            self._pars_artist_card(artist_card_item=related_artist_card_item,
                                                   include_feats=include_feats,
                                                   csv_path=csv_path,
                                                   listens_threshold=listens_threshold,
                                                   n_last_releases=n_last_releases,
                                                   days_from_last_release=days_from_last_release)
        else:
            self.failed_artists.append(artist_name)

    def _pars_artist_card(self, artist_card_item, include_feats=False, csv_path=None, listens_threshold=None,
                          n_last_releases=3, days_from_last_release=None):
        """
        Возвращает дикт с похожими артистами и их айдишками.
        Артисты берутся из фитов и блока с похожими артистами в карточке основного артиста.
        Обновляет аргумент parsed_cards_urls объекта

        :param artist_card_item:        dict, разобранный JSON объект карточки основного артиста
        :param include_feats:           bool, True - парсить артистов из фитов в качестве похожих, False - нет
        :param csv_path:                str, путь к csv файлу для записи результатов в реальном времени
        :param listens_threshold:       int, минимальный порог по прослушиваниям в среднем по релизам
        :param n_last_releases:         int, количество последних релизов для анализа
        :param days_from_last_release:  int, максиально допустимое кол-во дней, прошедших от даты последнего релиза
        :return:                        dict, {artist_name, artist_id (or artist_card_url)}
        """
        # Если такого ключа нет, то нет карточки артиста
        if 'artists' not in artist_card_item.keys():
            return None

        # Достаем инфу об основном артисте переданной карточки артиста
        card_artist_name = artist_card_item['artists'][0]['name']
        card_url = artist_card_item['section']['url']
        finded_artists = {card_artist_name: card_url}

        # Проверка на повторы
        if card_artist_name in self.parsed_cards_urls.keys():
            return None

        # Проверка на прохождение всех переданных фильтров
        self._artist_parameters_filter(artist_card_item, card_artist_name, card_url, csv_path, days_from_last_release,
                                       listens_threshold, n_last_releases)

        if include_feats:
            finded_artists.update(_pars_feats_from_audios(audios=artist_card_item['audios'],
                                                          main_artist_name=card_artist_name))

        # Поиск блока с похожими артистами (его может не быть)
        related_artists_block_id = None
        for block in artist_card_item['section']['blocks']:
            if 'url' in block.keys() and 'related' in block['url']:
                related_artists_block_id = block['id']

        if related_artists_block_id:
            finded_artists.update(self._pars_related_artists_block(related_artists_block_id=related_artists_block_id))

        return finded_artists

    def _artist_parameters_filter(self, artist_card_item, card_artist_name, card_url, csv_path, days_from_last_release,
                                  listens_threshold, n_last_releases):
        """
        Проверяет карточку артиста на прохождение всех переданных фильтров, а именно:
            - среднее кол-во прослушиваний на N последних релизных плейлистах
            - дата последнего релиза

        Записывает артиста в соответствующие аргументы объекта осле прохождения всех фильтров

        """
        # Если переданы порог прослушиваний и дни от последнего релиза
        if listens_threshold and days_from_last_release:
            if _listens_threshold_passed(artist_card_item=artist_card_item,
                                         listens_threshold=listens_threshold,
                                         n_last_releases=n_last_releases):
                if _is_artist_alive(artist_card_item=artist_card_item,
                                    days_from_last_release=days_from_last_release):
                    self.parsed_cards_urls[card_artist_name] = card_url
                    if csv_path:
                        with open(csv_path, 'a', encoding='utf-16') as file:
                            file.write(f'{card_artist_name}\t{card_url}\n')
                else:
                    self.failed_artists.append(card_artist_name)
            else:
                self.failed_artists.append(card_artist_name)

        # Если передан только порог по прослушивнаиям
        elif listens_threshold:
            if _listens_threshold_passed(artist_card_item=artist_card_item,
                                         listens_threshold=listens_threshold,
                                         n_last_releases=n_last_releases):
                self.parsed_cards_urls[card_artist_name] = card_url
                if csv_path:
                    with open(csv_path, 'a', encoding='utf-16') as file:
                        file.write(f'{card_artist_name}\t{card_url}\n')
            else:
                self.failed_artists.append(card_artist_name)

        # Если переданы только дни от последнего релиза
        elif days_from_last_release:
            if _is_artist_alive(artist_card_item=artist_card_item,
                                days_from_last_release=days_from_last_release):
                self.parsed_cards_urls[card_artist_name] = card_url
                if csv_path:
                    with open(csv_path, 'a', encoding='utf-16') as file:
                        file.write(f'{card_artist_name}\t{card_url}\n')
            else:
                self.failed_artists.append(card_artist_name)

        # Если ничего не передано
        else:
            self.parsed_cards_urls[card_artist_name] = card_url
            if csv_path:
                with open(csv_path, 'a', encoding='utf-16') as file:
                    file.write(f'{card_artist_name}\t{card_url}\n')

    def _pars_related_artists_block(self, related_artists_block_id):
        """
        Возвращает дикт с именами и каталожными айдишками артистов из блока похожих артистов в карточке артиста

        :param related_artists_block_id:    str, айди блока похожих артистов
        :return:                            dict, {artist_name, artist_card_url}
        """
        url = f'https://api.vk.com/method/catalog.getBlockItems?v=5.96&access_token={self.token}&' \
              f'block_id={related_artists_block_id}'
        resp = self._resp_with_anticaptcha(url)

        try:
            related_artists_ids = {artist['title']: artist['url'] for artist in resp['response']['links']}
        except KeyError:
            sleep(uniform(0.4, 0.5))
            return self._pars_related_artists_block(related_artists_block_id=related_artists_block_id)

        if 'next_from' in resp['response']['block'].keys():
            url += f"&start_from={resp['response']['block']['next_from']}"
            resp = self._resp_with_anticaptcha(url)
            # По некст фрому может ничего не вернуться, точнее в таком сулчае вернется error
            if 'response' in resp.keys():
                related_artists_ids.update({artist['title']: artist['url'] for artist in resp['response']['links']})

        return related_artists_ids

    def _get_artist_card_item(self, artist_card_id):
        """
        Возвращает декодированный в дикт JSON-объект карточки артиста

        :param artist_card_id:  str, айди карточки артиста
        :return:                dict, объект карточки артиста
        """
        url = f'https://api.vk.com/method/catalog.getSection?v=5.96&access_token={self.token}&' \
              f'section_id={artist_card_id}'
        resp = self._resp_with_anticaptcha(url)
        return resp['response']

    def _get_artist_card_id(self, artist_id_or_card_url):
        """
        Возвращает айди карточки артиста по ссылке на эту карточку или айдишке артсита.
        Либо возвращает None, если карточка не найдена

        :param artist_id_or_card_url:       str or int, ссылка на карточку артиста в ВК
        :return:                            str or None
        """
        # Проверка на тип переменной и выбор соответствующего параметра для метода API
        if 'vk.com' in artist_id_or_card_url:
            url = f'https://api.vk.com/method/catalog.getAudioArtist?v=5.96&access_token={self.token}&' \
                  f'url={artist_id_or_card_url}'
        else:
            url = f'https://api.vk.com/method/catalog.getAudioArtist?v=5.96&access_token={self.token}&' \
                  f'artist_id={artist_id_or_card_url}'

        resp = self._resp_with_anticaptcha(url)
        try:
            if '{artist_name}' in resp['response']['catalog']['sections'][0]['title']:
                return None
            return resp['response']['catalog']['sections'][0]['id']
        except KeyError:
            print(resp)
            return None
