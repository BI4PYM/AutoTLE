import requests
import sys
import json

with open('satelist.json', 'r') as jsonlist:
    satelist=json.load(jsonlist)
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
tem = open('localTLE.txt', 'r')
allTle.write(str(tem.read()))

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
allTle = open('allTLE.txt', 'r')
allTles = str(allTle.read())
for i in range(len(satelist)):
    temp = [temp for temp in Tles if satelist[i][0] in temp]
    print(satelist[i][1])
    satnogs = requests.get('https://db.satnogs.org/api/tle/?format=3le&norad_cat_id='+satelist[i][0].rstrip('U'), headers=headers).text
    if satelist[i][0] in allTles:
        print(satelist[i][0])
        getTles = satelist[i][1] + '\n' + Tles[Tles.index(temp[0])] + '\n' + Tles[Tles.index(temp[0]) + 1] + '\n'
        Tle.write(getTles)
    elif(len(satnogs) != 0):
        print(satelist[i][0])
        getTles = satelist[i][1] + '\n' + satnogs[satnogs.index(satelist[i][0])-2:]+'\n'
        Tle.write(getTles)
allTle.close()
Tle.close()
