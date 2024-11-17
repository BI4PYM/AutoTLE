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

allTle = open('allTLE.txt', 'w')
temp = open('localTLE.txt', 'r')
allTle.write(str(temp.text))
temp = requests.get('http://asrtu.mqsi.xyz/tle.txt', headers=headers)
allTle.write(str(temp.text))
temp = requests.get('http://www.celestrak.com/NORAD/elements/amateur.txt', headers=headers)
allTle.write(str(temp.text))
temp = requests.get('http://www.celestrak.com/NORAD/elements/cubesat.txt', headers=headers)
allTle.write(str(temp.text))
temp = requests.get('http://celestrak.org/NORAD/elements/gp.php?GROUP=active&FORMAT=tle', headers=headers)
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
temp = requests.get('http://www.celestrak.com/NORAD/elements/geo.txt', headers=headers)
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

satelist = [
    ['25544U','ISS(ZARYA)'],
    ['27607U','SO-50'],
    ['43017U','AO-91(FOX-1B)'],
    ['43678U','PO-101(DIWATA-2B)'],
    ['44909U','RS-44'],
    ['22825U','AO-27'],
    ['40911U','XW-2B'],
    ['07530U','AO-7'],
    ['42761U','CAS-4A'],
    ['43937U','CAS-4B'],
    ['40908U','CAS-3H(LilacSat-2)'],
    ['24278U','FO-29'],
    ['44881U','CAS-6'],
    ['48274U','CSS(TianHe)'],
    ['43803U','JO-97'],
    ['25338U','NOAA-15'],
    ['28654U','NOAA-18'],
    ['33591U','NOAA-19'],
    ['44387U','METEOR-M2'],
    ['50466U','XW-3(HO-113)'],
    ['54216U','CSS(MengTian)'],
    ['54816U','CAS-10(XW-4)'],
    ['54684U','CAS-5A(FO-118)'],
    ['53106U','GreenCube'],
    ['49069U','LEDSAT'],
    ['43700U',"QO-100(Es'hail-2)"],
    ['99130U','ASRTU-1']
]
allTle = open('allTLE.txt', 'r')
allTles = str(allTle.read())
for i in range(len(satelist)):
    temp = [temp for temp in Tles if satelist[i][0] in temp]
    print(satelist[i][1])
    if satelist[i][0] in allTles:
        print(satelist[i][1])
        getTles = satelist[i][1] + '\n' + Tles[Tles.index(temp[0])] + '\n' + Tles[Tles.index(temp[0]) + 1] + '\n'
        Tle.write(getTles)
allTle.close()
Tle.close()
