import requests

temp = requests.get('http://www.celestrak.com/NORAD/elements/amateur.txt')
allTle = open('allTLE.txt', 'w')
allTle.write(str(temp.text))
temp = requests.get('http://www.celestrak.com/NORAD/elements/cubesat.txt')
allTle.write(str(temp.text))
temp = requests.get('http://www.celestrak.com/NORAD/elements/dmc.txt')
allTle.write(str(temp.text))
temp = requests.get('http://www.celestrak.com/NORAD/elements/education.txt')
allTle.write(str(temp.text))
temp = requests.get('http://www.celestrak.com/NORAD/elements/engineering.txt')
allTle.write(str(temp.text))
temp = requests.get('http://www.celestrak.com/NORAD/elements/noaa.txt')
allTle.write(str(temp.text))
temp = requests.get('http://www.celestrak.com/NORAD/elements/other.txt')
allTle.write(str(temp.text))
temp = requests.get('http://www.celestrak.com/NORAD/elements/other-comm.txt')
allTle.write(str(temp.text))
temp = requests.get('http://www.celestrak.com/NORAD/elements/stations.txt')
allTle.write(str(temp.text))
temp = requests.get('http://www.celestrak.com/NORAD/elements/tle-new.txt')
allTle.write(str(temp.text))
temp = requests.get('http://www.celestrak.com/NORAD/elements/weather.txt')
allTle.write(str(temp.text))

allTle = open('allTLE.txt', 'r')
Tles = str(allTle.read())
allTle.close()
Tle = open('AutoTLE.txt', 'w')
Tles = Tles.splitlines()
Tles = [i for i in Tles if i != '']

satelistNumber = [
    '25544U','27607U','43017U','43678U','44909U','22825U','40903U','40911U','40907U','40910U'
    ,'07530U','42761U','42759U','40908U','24278U','42017U','44354U','44881U','48274U','43803U','47438U'
    ,'43937U','25338U','28654U','33591U'
]
satelistName = [
    'ISS','SO-50','AO-91(FOX-1B)','PO-101(DIWATA-2B)','RS-44','AO-27','XW-2A','XW-2B','XW-2D',
    'XW-2F','AO-7','CAS-4A','CAS-4B','CAS-3H','FO-29','EO-88','PSAT-2(NO-104)','CAS-6',
    'TIANHE-1','JO-97','UVSQ-SAT','FO-99','NOAA-15','NOAA-18','NOAA-19'
]
for i in range(len(satelistNumber)):
    temp = [temp for temp in Tles if satelistNumber[i] in temp]
    print(satelistName[i])
    getTles = '\n' + satelistName[i] + '\n' + Tles[Tles.index(temp[0])] + '\n' + Tles[Tles.index(temp[0]) + 1]
    Tle.write(getTles)

Tle.close()