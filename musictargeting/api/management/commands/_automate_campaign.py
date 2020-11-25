from datetime import datetime, date, timedelta
from time import sleep

from musictargeting.api.models import Campaign, Ad
from musictargeting.api import vk_framework
from musictargeting.settings import DEV_PROXY, DEV_RUCAPTCHA_KEY


def automate_campaign(campaign, target_cost, start_tomorrow, finish_tomorrow):

    # Получение переменных, которые не будут меняться в процессе
    # Там же заодно снимаются лимиты с объявлений и обновляется объект кампании в БД (automate=1)
    ads, ads_for_vk_framework, campaign_pk, vk = _get_automate_constant_objects(campaign)

    # Получение времени старта и остановки автоматизации кампании
    start_time, finish_time = _get_time_params(finish_tomorrow, start_tomorrow)

    # Ожидание наступления времени старта автоматизации
    _waiting_start_time(start_time)

    # Цикл автоматизации до наступления времени остановки
    while datetime.now() < finish_time:
        # Получение обновленных параметров кампании
        ad_stats, ad_statuses, campaign = _get_updated_campaign_params(ads_for_vk_framework, campaign_pk, vk)

        # Если есть стата и кампания все еще автоматизирована
        if ad_stats and campaign.automate:
            start_ads, stop_ads = _update_ad_params_in_vk(ad_stats, ad_statuses, target_cost, vk)
            updated_campaign_stat = _update_ad_objects(ad_stats, ads, start_ads, stop_ads)
            _update_campaign_object(campaign, updated_campaign_stat)

        # Если есть стата, но автоматизацию нужно остановить (обновился параметр у объекта кампании в БД)
        elif ad_stats and not campaign.automate:
            updated_campaign_stat = _update_ad_objects(ad_stats, ads, [], ads_for_vk_framework.keys())
            _update_campaign_object(campaign, updated_campaign_stat)
            break

        # Если ошибка со статой и автоматизацию нужно остановить (обновился параметр у объекта кампании в БД)
        if not campaign.automate:
            break

        # Завершение автоматизации, если всеобъявления в кампании остановлены
        if ad_statuses:
            stopped_ads = [ad_id for ad_id, statuses in ad_statuses.items() if statuses['status'] == 0]
            if len(stopped_ads) == len(ads_for_vk_framework):
                break

        sleep(600)


def _get_updated_campaign_params(ads_for_vk_framework, campaign_pk, vk):
    campaign = Campaign.objects.get(pk=campaign_pk)
    ad_stats = vk.get_full_ads_stat(ads=ads_for_vk_framework)
    ad_statuses = vk.ads.get_ads(campaign_id=campaign.cabinet_vk_id)
    return ad_stats, ad_statuses, campaign


def _get_automate_constant_objects(campaign):
    campaign_pk = campaign.pk
    user = campaign.owner
    ads = Ad.objects.all().filter(campaign_vk_id=campaign.cabinet_vk_id)
    ads_for_vk_framework = {ad.ad_vk_id: ad.playlist_url for ad in list(ads)}
    vk = vk_framework.VkAPI(token=user.vk_token,
                            ads_cabinet_id=campaign.cabinet_vk_id,
                            ads_client_id=campaign.client_vk_id,
                            rucaptcha_key=DEV_RUCAPTCHA_KEY,
                            proxy=DEV_PROXY)

    vk.ads.limit_ads(ad_ids=ads_for_vk_framework, limit=0)
    campaign.automate = 1
    campaign.save()

    return ads, ads_for_vk_framework, campaign_pk, vk


def _update_ad_params_in_vk(ad_stats, ad_statuses, target_cost, vk):
    start_ads, stop_ads, cpm_update = _get_ads_dicisions(ad_stats, ad_statuses, target_cost)
    vk.ads.start_ads(ad_ids=start_ads)
    vk.ads.stop_ads(ad_ids=stop_ads)
    vk.ads.update_cpm(cpm_dict=cpm_update)
    return start_ads, stop_ads


def _update_campaign_object(campaign, updated_campaign_stat):
    campaign.spent = updated_campaign_stat['spent']
    campaign.listens = updated_campaign_stat['listens']
    campaign.listens = updated_campaign_stat['reach']
    campaign.listens = updated_campaign_stat['clicks']
    campaign.listens = updated_campaign_stat['subscribes']

    reach = updated_campaign_stat['reach']

    listens = updated_campaign_stat['listens']

    campaign.cpm = updated_campaign_stat['spent'] / (reach / 1000) if reach else 0
    campaign.cpl = updated_campaign_stat['spent'] / listens if listens else 0

    campaign.save()


def _update_ad_objects(ad_stats, ads, start_ads, stop_ads):
    updated_ad_objects = []
    updated_campaign_stat = {'spent': 0, 'listens': 0, 'reach': 0, 'clicks': 0, 'subscribes': 0}
    for ad in list(ads):
        # Если был охват (если он не ноль)
        if ad_stats[ad.ad_vk_id]['reach']:
            # Обновление статы в объектах объявлений
            ad.spent = ad_stats[ad.ad_vk_id]['spent']
            ad.reach = ad_stats[ad.ad_vk_id]['reach'],
            ad.cpm = ad_stats[ad.ad_vk_id]['cpm'],
            ad.clicks = ad_stats[ad.ad_vk_id]['clicks'],
            ad.subscribes = ad_stats[ad.ad_vk_id]['subscribes'],
            ad.listens = ad_stats[ad.ad_vk_id]['listens']

            # Обновление средней статы кампании
            for param in updated_campaign_stat.keys():
                updated_campaign_stat[param] += ad_stats[ad.ad_vk_id][param]

        # Обновление статусов объявлений
        if ad in start_ads:
            ad.status = 1
        elif ad in stop_ads:
            ad.status = 0

        # Добавление обновленного объекта в лист
        updated_ad_objects.append(ad)

    # Сохранение обновленных объектво объявлений в БД
    Ad.objects.bulk_update(updated_ad_objects, ['spent', 'reach', 'cpm', 'clicks', 'subscribes', 'listens', 'status'])

    # Возврат обновленной средней статы кампании
    return updated_campaign_stat


def _get_ads_dicisions(ads_stats, ad_statuses, target_cost, speed_coef=None):
    # Расчет stop_cost из target_cost
    stop_cost = target_cost * 1.2

    # Если передан коэффициент ускорения кампании
    if speed_coef:
        target_cost *= speed_coef
        stop_cost *= speed_coef

    # Проход по каждому объявлению
    stop_ads, cpm_update = [], {}
    for ad_id, ad_stats in ads_stats.items():
        # Расчет текущей стоимости прослушивания, если есть хотя бы одно прослушивание
        current_cost = ad_stats['spent'] / ad_stats['listens'] if ad_stats['listens'] else None

        # Если кост меньше или равен целевому, а СРМ есть куда увеличивать - увеличиваем
        if current_cost and current_cost <= target_cost and ad_stats['cpm'] <= 115:
            cpm_update[ad_id] = ad_stats['cpm'] + 5.1

        # Если кост выше целевого, но ниже остановочного и СРМ есть куда понижать - понижаем
        elif current_cost and stop_cost > current_cost > target_cost and ad_stats['cpm'] <= 35.1:
            cpm_update[ad_id] = ad_stats['cpm'] - 5.1

        # Если кост выше остановочного - останавливаем
        elif current_cost and current_cost > stop_cost:
            stop_ads.append(ad_id)

    # Получение объявлений для запуска
    start_ads = [x for x in ads_stats.keys() if x not in stop_ads]
    if ad_statuses:
        start_ads = [x for x in start_ads if ad_statuses[x]['approved'] == 2 and ad_statuses[x]['status'] == 0]

    return start_ads, stop_ads, cpm_update


def _get_time_params(finish_tomorrow, start_tomorrow):
    start_time = datetime.combine(date.today(), datetime.min.time())
    if start_tomorrow:
        start_time += timedelta(days=1)
    finish_time = start_time + timedelta(hours=23, minutes=59) if finish_tomorrow else start_time + timedelta(days=365)
    return start_time, finish_time


def _waiting_start_time(start_time):
    while datetime.now() < start_time:
        sleep(60)
