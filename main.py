import requests
import sys
headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 \
    (KHTML, like Gecko) Chrome/91.0.4472.164 Safari/537.36'}
'''def get_proxy():
    return requests.get("http://127.0.0.1:5010/get/").json()

def delete_proxy(proxy):
    requests.get("http://127.0.0.1:5010/delete/?proxy={}".format(proxy))'''
'''
, proxies={"http": "http://127.0.0.1:10809"}
'''
#proxy = get_proxy().get("proxy")
temp = requests.get('http://www.celestrak.com/NORAD/elements/amateur.txt', headers=headers)
allTle = open('allTLE.txt', 'w')
allTle.write(str(temp.text))
temp = requests.get('http://www.celestrak.com/NORAD/elements/cubesat.txt', headers=headers)
allTle.write(str(temp.text))
temp = requests.get('http://www.celestrak.com/NORAD/elements/dmc.txt', headers=headers)
allTle.write(str(temp.text))
temp = requests.get('http://www.celestrak.com/NORAD/elements/weather.txt', headers=headers)
allTle.write(str(temp.text))
temp = requests.get('http://www.celestrak.com/NORAD/elements/tle-new.txt', headers=headers)
allTle.write(str(temp.text))
temp = requests.get('http://celestrak.org/NORAD/elements/gp.php?GROUP=noaa&FORMAT=tle', headers=headers)
allTle.write(str(temp.text))
temp = requests.get('http://www.celestrak.com/NORAD/elements/stations.txt', headers=headers)
allTle.write(str(temp.text))


allTle = open('allTLE.txt', 'r')
Tles = str(allTle.read())
allTle.close()
if '<' in Tles:
    print('get tles error.')
'''    sys.exit(1)'''
Tle = open('AutoTLE.txt', 'w')
Tles = Tles.splitlines()
Tles = [i for i in Tles if i != '']


satelistNumber = [
    '25544U', '27607U', '43017U', '43137U', '43678U', '44909U', '22825U', '40903U', '40911U', '40907U'
    , '40910U', '07530U', '42761U', '42759U', '40908U', '24278U', '42017U', '44881U',
    '48274U', '43803U', '47438U', '43937U', '25338U', '28654U', '33591U', '44387U', '50466U',
    '54216U','54816U','54684U','53106U',
    '49069U','56211U'
]
satelistName = [
    'ISS(ZARYA)', 'SO-50', 'AO-91(FOX-1B)', 'AO-92(FOX-1D)', 'PO-101(DIWATA-2B)', 'RS-44', 'AO-27', 'XW-2A', 'XW-2B', 'XW-2D',
    'XW-2F', 'AO-7', 'CAS-4A', 'CAS-4B', 'CAS-3H(LilacSat-2)', 'FO-29', 'EO-88', 'CAS-6',
    'CSS(TianHe)', 'JO-97', 'UVSQ-SAT', 'FO-99', 'NOAA-15', 'NOAA-18', 'NOAA-19', 'METEOR-M2', 'XW-3(HO-113)'
    ,'CSS(MengTian)','CAS-10(XW-4)','CAS-5A(FO-118)','GreenCube',
    'LEDSAT','InspireSat-7'
]
allTle = open('allTLE.txt', 'r')
allTles = str(allTle.read())
for i in range(len(satelistNumber)):
    temp = [temp for temp in Tles if satelistNumber[i] in temp]
    print(satelistName[i])
    if satelistNumber[i] in allTles:
        print(satelistNumber[i])
        getTles = satelistName[i] + '\n' + Tles[Tles.index(temp[0])] + '\n' + Tles[Tles.index(temp[0]) + 1] + '\n'
        Tle.write(getTles)
allTle.close()
Tle.close()
