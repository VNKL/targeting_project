import os
import requests
import warnings
import numpy as np
import pickle

from musicnn.extractor import extractor
from sklearn.preprocessing import StandardScaler

from musictargeting.settings import DEV_PROXY, DEV_VK_TOKEN
from musictargeting.api.vk.vk_framework import VkChart, _generate_random_filename, _open_trackspace, decode_mp3_url


warnings.filterwarnings('ignore')


def update_trackspace():

    trackspace, scaler = _open_trackspace()

    vk = VkChart(token=DEV_VK_TOKEN, rucaptcha_key=DEV_VK_TOKEN, proxy=DEV_PROXY)
    chart = vk.get_chart()

    new_trackspace = trackspace.copy() if trackspace else {}
    features_matrix = [x['features'] for _, x in trackspace.items()] if trackspace else []

    for _, audio in chart.items():
        trackname = f'{audio["artist"]} - {audio["title"]}'
        if trackspace and trackname in trackspace.keys():
            continue
        mp3_url = decode_mp3_url(audio['url'])
        filename = _generate_random_filename()
        _write_mp3_file(mp3_url, filename)
        taggram, _ = extractor(file_name=f'musictargeting/api/vk/temp/{filename}.mp3',
                               model='MSD_musicnn',
                               extract_features=False)
        os.remove(f'musictargeting/api/vk/temp/{filename}.mp3')
        features = list(np.mean(taggram, axis=0))
        domains = [x['domain'] for x in audio['main_artists']]
        if 'featured_artists' in audio.keys():
            domains.extend([x['domain'] for x in audio['featured_artists']])

        new_trackspace[trackname] = {'features': features, 'domains': domains}
        features_matrix.append(features)
        print(trackname)

    scaler = StandardScaler()

    with open('musictargeting/api/vk/trackspace.pkl', 'wb') as file:
        pickle.dump(new_trackspace, file)

    with open('musictargeting/api/vk/scaler.pkl', 'wb') as file:
        pickle.dump(scaler, file)


def _write_mp3_file(mp3_url, filename):
    proxy_dict = {'https': f'https://{DEV_PROXY}'}
    dirs = 'musictargeting/api/vk/temp'

    os.makedirs(dirs, exist_ok=True)
    with open(f'{dirs}/{filename}.mp3', 'wb') as file:
        mp3 = requests.get(mp3_url, proxies=proxy_dict).content
        file.write(mp3)
