import requests
import sys
import json

with open('satelist.json', 'r') as jsonlist:
    satelist=json.load(jsonlist)
headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 \
    (KHTML, like Gecko) Chrome/91.0.4472.164 Safari/537.36'}

proxies={"http": "http://127.0.0.1:13000"}
#proxies={}
localtle = open('localTLE.txt', 'r')
Tles = str(localtle.read())
Tle = open('AutoTLE.txt', 'w')
Tles = Tles.splitlines()
Tles = [i for i in Tles if i != '']
for i in range(len(satelist)):
    try:
        print(satelist[i][0],satelist[i][1],satelist[i][2])
        temp = requests.get("https://celestrak.org/NORAD/elements/gp.php?" + satelist[i][2] + "=" + satelist[i][0] + "&FORMAT=TLE", headers=headers, proxies=proxies)
        if str(temp.text) != "No GP data found":
            allTle.write(str(temp.text))
        else:
            raise ValueError("NOT FOUND")
    except:
        satnogs = requests.get('https://db.satnogs.org/api/tle/?format=3le&norad_cat_id='+satelist[i][0], headers=headers).text
        if len(satnogs) != 0:
            getTles = satelist[i][1] + '\n' + satnogs[satnogs.index(satelist[i][0])-2:]+'\n'
            Tle.write(getTles)
            print("SATNOGS OK.\n")
        else:
            temp = [temp for temp in Tles if satelist[i][0] in temp]
            if satelist[i][0] in Tles:
                getTles = satelist[i][1] + '\n' + Tles[Tles.index(temp[0])] + '\n' + Tles[Tles.index(temp[0]) + 1] + '\n'
                Tle.write(getTles)
                print("LOCAL OK.\n")
            else:
                print("NOT FOUND.\n")
    else:
        getTles = satelist[i][1] + '\n' + Tles[Tles.index(temp[0])] + '\n' + Tles[Tles.index(temp[0]) + 1] + '\n'
        Tle.write(getTles)
        print("CELESTRAK OK.\n")
Tle.close()




"""
import requests
import sys
import json

with open('satelist.json', 'r') as jsonlist:
    satelist=json.load(jsonlist)
headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 \
    (KHTML, like Gecko) Chrome/91.0.4472.164 Safari/537.36'}

proxies={"http": "http://127.0.0.1:13000"}
#proxies={}

allTle = open('allTLE.txt', 'w')
tem = open('localTLE.txt', 'r')
allTle.write(str(tem.read()))

print("GETTING TLE FROM CELESTRAK...")
for i in range(len(satelist)):
    try:
        print(satelist[i][0],satelist[i][1],satelist[i][2])
        temp = requests.get("https://celestrak.org/NORAD/elements/gp.php?" + satelist[i][2] + "=" + satelist[i][0] + "&FORMAT=TLE", headers=headers, proxies=proxies)
        if str(temp.text) != "No GP data found":
            allTle.write(str(temp.text))
        else:
            raise ValueError("NOT FOUND")
    except:
        print("FAIL.")
    else:
        print("OK.")

print("SEARCHING FOR TLE...")
allTle = open('allTLE.txt', 'r')
Tles = str(allTle.read())
allTle.close()
if '<' in Tles:
    print('GET TLE ERROR.')
'''    sys.exit(1)'''
Tle = open('AutoTLE.txt', 'w')
Tles = Tles.splitlines()
Tles = [i for i in Tles if i != '']
allTle = open('allTLE.txt', 'r')
allTles = str(allTle.read())
for i in range(len(satelist)):
    temp = [temp for temp in Tles if satelist[i][0] in temp]
    print(satelist[i][0],satelist[i][1],satelist[i][2])
    satnogs = requests.get('https://db.satnogs.org/api/tle/?format=3le&norad_cat_id='+satelist[i][0], headers=headers).text
    if satelist[i][0] in allTles:
        print("CELESTRAK OK.\n")
        getTles = satelist[i][1] + '\n' + Tles[Tles.index(temp[0])] + '\n' + Tles[Tles.index(temp[0]) + 1] + '\n'
        Tle.write(getTles)
    elif(len(satnogs) != 0):
        print("SATNOGS OK.\n")
        getTles = satelist[i][1] + '\n' + satnogs[satnogs.index(satelist[i][0])-2:]+'\n'
        Tle.write(getTles)
    else:
        print("NOT FOUND.\n")
allTle.close()
Tle.close()
"""






